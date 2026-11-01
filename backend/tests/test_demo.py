import pandas as pd

from app import config
from app.marche.catalogue import charger_univers
from pipeline.demo import generer_demo, serie_demo


def test_demo_ecrit_toutes_les_series_et_le_marqueur(tmp_path):
    u = charger_univers(config.UNIVERS_YAML)
    marqueur = tmp_path / "DONNEES_SYNTHETIQUES.txt"
    assert generer_demo(u, tmp_path, marqueur) == 43
    assert marqueur.exists() and "PAS des prix réels" in marqueur.read_text(encoding="utf-8")
    df = pd.read_csv(tmp_path / "CL_F.csv", index_col="date", parse_dates=["date"])
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all() and (df["low"] <= df[["open", "close"]].min(axis=1)).all()
    assert (df["low"] > 0).all() and df.index.is_monotonic_increasing


def test_demo_est_reproductible_et_respecte_les_calendriers():
    a = serie_demo("AAPL", "action", "semaine", "2018-01-01", "2018-03-01", 1)
    b = serie_demo("AAPL", "action", "semaine", "2018-01-01", "2018-03-01", 1)
    assert a.equals(b) and a.index.dayofweek.max() < 5
    c = serie_demo("BTC-USD", "crypto", "continu", "2018-01-01", "2018-01-14", 1)
    assert len(c) == 14


def test_instantane_signale_les_donnees_synthetiques(client, utilisateur, monkeypatch, tmp_path):
    u = utilisateur()
    assert client.get("/api/v1/marche/instantane", headers=u.h).json()["synthetiques"] is False
    marqueur = tmp_path / "m.txt"
    marqueur.write_text("x")
    monkeypatch.setattr(config, "MARQUEUR_SYNTHETIQUE", marqueur)
    assert client.get("/api/v1/marche/instantane", headers=u.h).json()["synthetiques"] is True
