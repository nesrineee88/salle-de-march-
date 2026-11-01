"""Backtesting : chiffres vérifiables à la main, absence de fuite du futur, validations."""
import numpy as np
import pandas as pd
import pytest

from app.analyse import backtest as bt


def barres(opens, closes, debut="2020-01-01"):
    idx = pd.bdate_range(debut, periods=len(closes))
    o, c = np.asarray(opens, float), np.asarray(closes, float)
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.1, "low": np.minimum(o, c) - 0.1, "close": c}, index=idx)


def sans_gap(closes):
    return barres(np.concatenate([[closes[0]], closes[:-1]]), closes)


# ------------------------------------------------------------------ simulation
def test_achat_conservation_sans_frais_vaut_le_prix_final_sur_le_prix_d_entree():
    df = sans_gap([100, 110, 121, 133.1, 146.41])
    pos = bt.signaux("achat_conservation", {}, df)
    rend, entrees, cibles, detenues = bt.simuler(df, pos, 0.0, debut=1)
    assert entrees == 1 and np.prod(1 + rend) - 1 == pytest.approx(146.41 / 100 - 1)        # entrée à l'ouverture du jour 1 = clôture du jour 0
    assert list(cibles) == [1, 1, 1, 1] and list(detenues) == [0, 1, 1, 1]


def test_les_frais_se_paient_a_chaque_changement_de_position():
    df = sans_gap([100, 100, 100, 100, 100])
    pos = np.array([1.0, 1.0, 0.0, 0.0, 0.0])                      # on entre à l'ouverture du jour 1, on sort à celle du jour 3
    rend, entrees, _, _ = bt.simuler(df, pos, 10.0, debut=1)       # 10 points de base par côté
    assert entrees == 1 and np.prod(1 + rend) == pytest.approx((1 - 0.001) ** 2)


def test_un_gap_touche_la_position_detenue_pas_celle_qu_on_prend_a_l_ouverture():
    # clôtures 100, 100, 100 ; le jour 2 s'ouvre à 90 et clôture à 90 : un gap baissier de 10 %
    df = barres([100, 100, 90], [100, 100, 90])
    detenue_avant = np.array([1.0, 1.0, 1.0])                      # déjà investi : on subit le gap
    rend, *_ = bt.simuler(df, detenue_avant, 0.0, debut=1)
    assert np.prod(1 + rend) - 1 == pytest.approx(-0.10)
    entree_apres = np.array([0.0, 1.0, 1.0])                       # on décide d'entrer à la clôture du jour 1 : achat à 90, pas de perte
    rend, *_ = bt.simuler(df, entree_apres, 0.0, debut=1)
    assert np.prod(1 + rend) - 1 == pytest.approx(0.0)


def test_une_perte_ne_depasse_pas_cent_pour_cent_meme_avec_un_prix_negatif():
    df = barres([20, 18, -37], [20, 15, -37])                      # le pétrole WTI du 20 avril 2020
    pos = np.array([1.0, 1.0, 1.0])
    rend, *_ = bt.simuler(df, pos, 0.0, debut=1)
    assert rend.min() >= -1.0 and np.prod(1 + rend) >= 0.0


def test_aller_retours_et_taux_de_reussite():
    df = sans_gap([100, 110, 99, 99, 120, 108, 108])
    pos = np.array([1.0, 1.0, 0.0, 1.0, 1.0, 0.0, 0.0])           # deux allers-retours : un gagnant, un perdant
    rend, entrees, cibles, detenues = bt.simuler(df, pos, 0.0, debut=1)
    m = bt.metriques(rend, df.index[1:], cibles, detenues)
    assert entrees == 2 and m["aller_retours"] == 2 and m["taux_reussite"] == pytest.approx(0.5)


# ------------------------------------------------------------------ pas de fuite du futur
@pytest.mark.parametrize("nom", list(bt.CATALOGUE))
def test_le_signal_d_un_jour_ne_depend_que_du_passe(nom):
    rng = np.random.default_rng(5)
    c = 100 + np.cumsum(rng.normal(0, 1, 260))
    df = barres(np.concatenate([[100], c[:-1]]), c)
    complet = bt.signaux(nom, {}, df)
    for k in (80, 150, 230):
        assert np.array_equal(bt.signaux(nom, {}, df.iloc[:k]), complet[:k]), f"{nom} regarde le futur autour du jour {k}"


def test_modifier_le_futur_ne_change_pas_le_passe_du_backtest():
    rng = np.random.default_rng(6)
    c = 100 + np.cumsum(rng.normal(0, 1, 200))
    df = barres(np.concatenate([[100], c[:-1]]), c)
    futur = df.copy()
    futur.iloc[150:, futur.columns.get_indexer(["open", "high", "low", "close"])] *= 3.0      # le futur change du tout au tout
    a = bt.executer(df.iloc[:150], "croisement_sma", None, 7.5)
    b = bt.executer(futur.iloc[:150], "croisement_sma", None, 7.5)
    assert a["metriques"] == b["metriques"]


# ------------------------------------------------------------------ métriques et validations
def test_metriques_d_un_gain_regulier():
    idx = pd.bdate_range("2020-01-01", periods=252)
    m = bt.metriques(np.full(252, 0.001), idx)
    assert m["rendement_total"] == pytest.approx(1.001 ** 252 - 1) and m["drawdown_max"] == pytest.approx(0.0)
    assert m["sharpe"] is None                                      # volatilité nulle : pas de ratio inventé


def test_drawdown_maximal():
    idx = pd.bdate_range("2020-01-01", periods=4)
    m = bt.metriques(np.array([0.10, -0.20, -0.10, 0.30]), idx)      # 1,1 -> 0,88 -> 0,792 : baisse de 28 % depuis le sommet 1,1
    assert m["drawdown_max"] == pytest.approx(1 - 0.792 / 1.1)


@pytest.mark.parametrize("nom,params,message", [
    ("inconnue", {}, "stratégie inconnue"), ("croisement_sma", {"courte": 50, "longue": 20}, "plus courte"),
    ("rsi", {"bas": 60}, "entre 1 et 49"), ("macd", {"rapide": 30, "lente": 20}, "plus courte"),
    ("bollinger", {"ecarts": 10}, "entre 0.5 et 4"), ("momentum", {"jours": 2}, "entre 5 et 500"),
])
def test_parametres_invalides(nom, params, message):
    df = sans_gap(list(100 + np.arange(80.0)))
    with pytest.raises(ValueError, match=message):
        bt.signaux(nom, params, df)


def test_historique_trop_court():
    with pytest.raises(ValueError, match="trop court"):
        bt.executer(sans_gap(list(range(100, 110))), "achat_conservation", None, 5.0)


def test_la_strategie_croisement_est_en_liquidites_pendant_l_echauffement():
    c = 100 + np.arange(120.0)
    df = sans_gap(list(c))
    pos = bt.signaux("croisement_sma", {"courte": 5, "longue": 20}, df)
    assert pos[:19].sum() == 0 and pos[-1] == 1                     # la moyenne longue n'existe qu'à partir du 20e jour


# ------------------------------------------------------------------ API
def aller(client, u, instant):
    assert client.post("/api/v1/horloge/aller-a", json={"instant": instant}, headers=u.h).status_code == 200


def test_api_liste_et_backtest(client, utilisateur):
    u = utilisateur()
    assert client.get("/api/v1/backtest/strategies").status_code == 401
    assert {s["nom"] for s in client.get("/api/v1/backtest/strategies", headers=u.h).json()} == set(bt.CATALOGUE)
    aller(client, u, "2020-03-20T17:00:00")
    r = client.post("/api/v1/backtest", json={"symbole": "TST", "strategies": [{"nom": "croisement_sma", "parametres": {"courte": 5, "longue": 15}}, {"nom": "rsi"}]}, headers=u.h)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["reference"] == "achat_conservation" and [s["nom"] for s in c["strategies"]] == ["achat_conservation", "croisement_sma", "rsi"]
    assert c["cout_bps"] == pytest.approx(5 + 2.5) and c["strategies"][1]["parametres"]["courte"] == 5
    assert c["strategies"][0]["metriques"]["temps_investi"] == 1.0 and len(c["strategies"][0]["courbe"]["dates"]) == len(c["strategies"][0]["courbe"]["valeurs"])
    assert c["fin"] <= "2020-03-20"                                                  # jamais au-delà de la date simulée
    assert any("passé ne prédit pas" in a for a in c["avertissements"]) and any("moins d'un an" in a for a in c["avertissements"])


def test_api_backtest_ne_voit_pas_le_futur(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-02-20T17:00:00")
    avant = client.post("/api/v1/backtest", json={"symbole": "TST", "strategies": [{"nom": "macd"}]}, headers=u.h).json()
    aller(client, u, "2020-03-20T17:00:00")
    apres = client.post("/api/v1/backtest", json={"symbole": "TST", "strategies": [{"nom": "macd"}]}, headers=u.h).json()
    assert avant["fin"] < apres["fin"] <= "2020-03-20"
    commun = {d: v for d, v in zip(avant["strategies"][1]["courbe"]["dates"], avant["strategies"][1]["courbe"]["valeurs"])}
    nouveau = {d: v for d, v in zip(apres["strategies"][1]["courbe"]["dates"], apres["strategies"][1]["courbe"]["valeurs"])}
    for d, v in commun.items():
        assert nouveau[d] == pytest.approx(v)                                       # le passé ne change pas quand le temps avance


def test_api_backtest_erreurs(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-20T17:00:00")
    def essai(corps):
        return client.post("/api/v1/backtest", json=corps, headers=u.h)
    assert essai({"symbole": "TST", "strategies": [{"nom": "x"}]}).status_code == 422
    assert essai({"symbole": "TST", "strategies": []}).status_code == 422
    assert essai({"symbole": "NOPE", "strategies": [{"nom": "macd"}]}).status_code == 404
    assert essai({"symbole": "VIDE", "strategies": [{"nom": "macd"}]}).status_code == 503
    assert essai({"symbole": "TST", "strategies": [{"nom": "macd"}, {"nom": "macd"}]}).status_code == 422
    assert essai({"symbole": "TST", "strategies": [{"nom": "rsi", "parametres": {"bas": 80}}]}).status_code == 422
    assert essai({"symbole": "TST", "strategies": [{"nom": "macd"}], "debut": "2021-01-01"}).status_code == 422
    assert essai({"symbole": "TST", "strategies": [{"nom": "macd"}], "cout_bps": -1}).status_code == 422
    assert client.post("/api/v1/backtest", json={"symbole": "TST", "strategies": [{"nom": "macd"}]}).status_code == 401
