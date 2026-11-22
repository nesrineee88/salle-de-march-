"""Lecture technique et sentiment : états corrects, test « le signal a-t-il servi ? », rien après la date simulée."""
import numpy as np
import pandas as pd
import pytest

from app.analyse import lecture, routes_lecture


def bougies(closes, debut="2016-01-04"):
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": np.full(len(c), 1000.0)},
                        index=pd.bdate_range(debut, periods=len(c)))


def test_tendance_et_rsi_sur_une_hausse_reguliere():
    r = lecture.lire(bougies(100 * 1.002 ** np.arange(400)))
    etats = {s["cle"]: s["etat"] for s in r["signaux"]}
    assert etats["tendance"] == "au-dessus" and etats["croisement"] == "50 au-dessus" and etats["rsi"] == "surachat"
    assert r["signaux"][0]["valeurs"]["prix"] > r["signaux"][0]["valeurs"]["moyenne_200"]


def test_un_signal_qui_marche_vraiment_est_reconnu():
    rng = np.random.default_rng(2)
    etats = rng.choice(np.array(["a", "b"]), 2000)
    futur = np.where(etats == "a", rng.normal(0.02, 0.01, 2000), rng.normal(-0.005, 0.02, 2000))
    t = lecture._test(etats, futur, "a", 20)
    assert t["verdict"] == "plus_souvent_hausse" and t["taux"] - t["base"] > t["marge"]
    assert lecture._test(etats, futur, "b", 20)["verdict"] == "plus_souvent_baisse"


def test_le_hasard_reste_dans_le_bruit():
    rng = np.random.default_rng(7)
    r = lecture.lire(bougies(100 * np.cumprod(1 + rng.normal(0.0003, 0.01, 1500))))
    assert all(s["test"]["verdict"] in ("bruit", "trop_peu") for s in r["signaux"])


def test_historique_trop_court():
    with pytest.raises(ValueError, match="220"):
        lecture.lire(bougies(np.linspace(100, 110, 150)))


def test_la_lecture_ne_depend_pas_des_seances_suivantes():
    rng = np.random.default_rng(3)
    df = bougies(100 * np.cumprod(1 + rng.normal(0, 0.01, 800)))
    a = lecture.lire(df.iloc[:600])
    b = lecture.lire(df.iloc[:600].copy())
    assert a == b and a["date"] == df.index[599].date().isoformat()


def test_sentiment_reconnait_une_presse_qui_annonce_la_baisse():
    rng = np.random.default_rng(5)
    n = 1600
    rend = rng.normal(0, 0.01, n)
    df = bougies(100 * np.cumprod(1 + rend))
    futur = pd.Series(df["close"]).shift(-5) / df["close"] - 1
    tons = pd.Series((futur.fillna(0) * 40 + rng.normal(0, 0.05, n)).to_numpy(), index=df.index)
    r = lecture.sentiment(df, tons.iloc[:-5])
    assert r["test"]["verdict"] == "plus_souvent_baisse" and r["test"]["correlation"] > 0.5
    assert len(r["serie"]) == 250 and r["serie"][-1]["date"] <= r["prix"][-1]["date"]


def test_api_lecture(client, utilisateur, tmp_path, monkeypatch):
    u = utilisateur()
    assert client.get("/api/v1/lecture/technique/TST").status_code == 401
    r = client.get("/api/v1/lecture/technique/TST", headers=u.h)
    assert r.status_code == 422 and "220" in r.json()["detail"]            # séries de test : 60 séances
    assert client.get("/api/v1/lecture/technique/INCONNU", headers=u.h).status_code == 404
    monkeypatch.setattr(routes_lecture, "fichier_sentiment", lambda: tmp_path / "absent.csv")
    assert client.get("/api/v1/lecture/sentiment/TST", headers=u.h).status_code == 422


def test_le_sentiment_s_arrete_la_veille_de_la_date_simulee(client, utilisateur, tmp_path, monkeypatch):
    f = tmp_path / "s.csv"
    jours = pd.date_range("2020-01-01", "2020-12-31")
    pd.DataFrame({"symbole": "TST", "date": jours.strftime("%Y-%m-%d"), "ton": 0.5, "requete": '"Test"', "collecte": "2026-11-22"}).to_csv(f, index=False)
    monkeypatch.setattr(routes_lecture, "fichier_sentiment", lambda: f)
    tons, requete = routes_lecture.tons_du_symbole("TST", pd.Timestamp("2020-03-20").date())
    assert tons.index.max() == pd.Timestamp("2020-03-19") and requete == '"Test"'
