"""Analyses IA sur les prix passés : prédiction en marche avant, anomalies, régimes, optimiseur, agent."""
import numpy as np
import pandas as pd
import pytest

from app.ia import analyses

pytest.importorskip("sklearn")


def serie(n=900, graine=1, derive=0.0004, vol=0.01, tendance_persistante=False):
    rng = np.random.default_rng(graine)
    r = rng.normal(derive, vol, n)
    if tendance_persistante:                                                 # des rendements qui se suivent : un modèle devrait en profiter
        for i in range(1, n):
            r[i] += 0.35 * r[i - 1]
    close = 100 * np.cumprod(1 + r)
    idx = pd.bdate_range("2017-01-02", periods=n)
    v = rng.integers(900, 1100, n).astype(float)
    return pd.DataFrame({"open": close, "high": close * 1.005, "low": close * 0.995, "close": close, "volume": v}, index=idx)


# ------------------------------------------------------------------ prédiction
def test_predire_sur_du_bruit_ne_pretend_pas_battre_le_hasard():
    r = analyses.predire(serie(800))
    assert r["n_test"] > 400 and {x["cle"] for x in r["resultats"]} == {"logistique", "boost", "toujours_hausse", "veille"}
    assert all(0 <= x["precision"] <= 1 and x["marge"] > 0 for x in r["resultats"])
    assert r["dans_le_bruit"] is True and "hasard" in r["conclusion"]
    assert 0 < r["proba_hausse"] < 1
    s = r["intercept"] + sum(c["contribution"] for c in r["contributions"])
    assert 1 / (1 + np.exp(-s)) == pytest.approx(r["proba_hausse"])                       # la prédiction du jour s'explique exactement


def test_predire_detecte_une_vraie_regularite():
    r = analyses.predire(serie(1200, tendance_persistante=True, derive=0.0, vol=0.012))
    veille = next(x for x in r["resultats"] if x["cle"] == "veille")
    assert veille["precision"] > 0.6                                                       # la référence « comme la veille » marche sur ce jeu construit exprès
    logi = next(x for x in r["resultats"] if x["cle"] == "logistique")
    assert logi["precision"] > 0.58


def test_predire_marche_avant_n_utilise_pas_le_futur():
    df = serie(700)
    a = analyses.predire(df)
    df2 = df.copy()
    df2.iloc[-1, df2.columns.get_loc("close")] *= 1.5                                      # on change seulement la dernière clôture (le « futur » de l'avant-dernier jour)
    b = analyses.predire(df2)
    ra = {x["cle"]: x["precision"] for x in a["resultats"]}
    rb = {x["cle"]: x["precision"] for x in b["resultats"]}
    assert a["n_test"] == b["n_test"] or abs(a["n_test"] - b["n_test"]) <= 1
    assert abs(ra["toujours_hausse"] - rb["toujours_hausse"]) < 0.01


def test_predire_historique_insuffisant():
    with pytest.raises(ValueError, match="Pas assez"):
        analyses.predire(serie(200))


# ------------------------------------------------------------------ anomalies
def test_anomalies_trouvent_le_krach_injecte():
    df = serie(400)
    i = 380
    df.iloc[i:, df.columns.get_indexer(["open", "high", "low", "close"])] *= 0.8                  # −20 % en une séance
    df.iloc[i, df.columns.get_loc("volume")] = 30_000
    r = analyses.anomalies(df)
    assert r["anomalies"][0]["jour"] == df.index[i].date().isoformat() and r["anomalies"][0]["type"] == "rendement et volume"
    assert r["anomalies"][0]["rendement"] == pytest.approx(-0.2, abs=0.01)
    assert r["nb"] < 10 and "ni un signal d'achat" in r["note"]


def test_anomalies_serie_calme():
    r = analyses.anomalies(serie(400, vol=0.002))
    assert r["nb"] <= 5


# ------------------------------------------------------------------ régimes
def test_regimes_separent_calme_et_crise():
    calme1, crise, calme2 = serie(300, 1, 0.0008, 0.005), serie(150, 2, -0.002, 0.03), serie(300, 3, 0.0008, 0.005)
    c = np.concatenate([calme1["close"], calme1["close"].iloc[-1] * crise["close"] / 100,
                        calme1["close"].iloc[-1] * crise["close"].iloc[-1] / 100 * calme2["close"] / 100])
    df = pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": 1000.0}, index=pd.bdate_range("2017-01-02", periods=len(c)))
    r = analyses.regimes(df)
    noms = {x["regime"] for x in r["regimes"]}
    assert "Agité" in noms and len(r["regimes"]) == 3 and abs(sum(x["part"] for x in r["regimes"]) - 1) < 1e-9
    assert r["regimes"][0]["regime"] == "Agité" and r["regimes"][0]["volatilite_annualisee"] > r["regimes"][-1]["volatilite_annualisee"] * 2
    assert r["regime_actuel"] != "Agité" and r["depuis_jours"] >= 1                         # la série finit par une période calme


# ------------------------------------------------------------------ optimiseur
def test_optimiseur_corrige_un_portefeuille_dominé_par_un_actif_risque():
    rng = np.random.default_rng(0)
    r = pd.DataFrame({"CALME": rng.normal(0.0003, 0.005, 400), "AGITE": rng.normal(0.0003, 0.03, 400), "MOYEN": rng.normal(0.0003, 0.012, 400)})
    o = analyses.optimiser(r, {"CALME": 0.2, "AGITE": 0.5, "MOYEN": 0.3})
    ligne = {x["symbole"]: x for x in o["lignes"]}
    assert o["lignes"][0]["symbole"] == "AGITE" and ligne["AGITE"]["contribution_risque"] > 0.8        # 50 % du capital, plus de 80 % du risque
    assert sum(x["poids_variance_minimale"] for x in o["lignes"]) == pytest.approx(1) and sum(x["poids_parite_risque"] for x in o["lignes"]) == pytest.approx(1)
    assert ligne["CALME"]["poids_variance_minimale"] > 0.7                                            # la variance minimale se réfugie dans l'actif calme
    assert o["volatilite_variance_minimale"] < o["volatilite_parite_risque"] < o["volatilite_actuelle"]
    assert ligne["AGITE"]["poids_parite_risque"] < ligne["CALME"]["poids_parite_risque"] and "pas un conseil" in o["note"] and "AGITE" in o["recommandations"][0]


def test_optimiseur_refus():
    with pytest.raises(ValueError, match="au moins deux"):
        analyses.optimiser(pd.DataFrame({"A": np.zeros(100)}), {"A": 1})
    with pytest.raises(ValueError, match="Pas assez"):
        analyses.optimiser(pd.DataFrame(np.random.default_rng(0).normal(size=(30, 2)), columns=["A", "B"]), {})


# ------------------------------------------------------------------ agent
def test_agent_est_juge_hors_echantillon_et_reproductible():
    df = serie(1000, 4, 0.0005, 0.012)
    a, b = analyses.agent(df, graine=1), analyses.agent(df, graine=1)
    assert a["agent"] == b["agent"] and len(a["politique"]) == 9
    assert a["entrainement"]["fin"] < a["test"]["debut"] and a["test"]["jours"] / (a["test"]["jours"] + a["entrainement"]["jours"]) == pytest.approx(0.3, abs=0.02)
    assert abs(a["achat_conservation"]["jours"] - a["test"]["jours"]) <= 1
    assert "jamais vu" in a["note"] and 0 <= a["agent"]["temps_investi"] <= 1


def test_agent_historique_insuffisant():
    with pytest.raises(ValueError, match="Pas assez"):
        analyses.agent(serie(250))


# ------------------------------------------------------------------ API
def test_api_ia(client, utilisateur):
    appr = utilisateur()
    assert client.get("/api/v1/ia/regimes/TST", headers=appr.h).status_code == 403                  # réservé aux rôles avancés
    t = utilisateur("t@example.com", "Trader", role="trader")
    client.post("/api/v1/horloge/aller-a", json={"instant": "2020-03-20T17:00:00"}, headers=t.h)
    r = client.get("/api/v1/ia/anomalies/TST", headers=t.h)
    assert r.status_code == 422 and "60" in r.json()["detail"]                                      # 60 séances de passé dans les données de test : trop peu
    assert client.get("/api/v1/ia/predire/TST", headers=t.h).status_code == 422
    assert client.get("/api/v1/ia/predire/NOPE", headers=t.h).status_code == 404
    assert client.get("/api/v1/ia/optimiser", headers=t.h).status_code == 422
    assert client.get("/api/v1/ia/predire/TST").status_code == 401
