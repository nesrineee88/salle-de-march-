"""Mode Direct (bêta) : flux de prix récents, horloge à l'heure réelle. Le flux est un faux : Yahoo n'est jamais appelé."""
import sys
from datetime import date, datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app import config
from app.direct import fournisseur, routes
from app.direct.fournisseur import FournisseurDirect, telechargeur_yahoo

MAINTENANT = datetime(2020, 3, 26, 16, 0, 0)          # un jeudi, pendant la séance américaine (14:30 à 21:00 UTC)


def barres(jours, dernier=123.45):
    idx = pd.DatetimeIndex(jours)
    n = len(idx)
    close = np.linspace(100.0, dernier, n)
    return pd.DataFrame({"open": close - 1, "high": close + 2, "low": close - 3, "close": close, "volume": [1000.0] * n}, index=idx)


def faux_flux(extra=None):
    def telecharger(symboles):
        sortie = {"TST": barres(["2020-03-20", "2020-03-25", "2020-03-26"]), "CRY": barres(["2020-03-31", "2020-04-01"], 55.0)}
        sortie.update(extra or {})
        return {s: df for s, df in sortie.items() if s in symboles}
    return telecharger


@pytest.fixture
def flux(monkeypatch):
    monkeypatch.setattr(routes, "telechargeur_actuel", faux_flux())
    monkeypatch.setattr("app.contexte.maintenant_utc", lambda: MAINTENANT)


# ------------------------------------------------------------------ magasin et moteur
def test_seules_les_dates_apres_l_instantane_sont_ajoutees(magasin_test, univers_test):
    fin_base = magasin_test.series_origine()["TST"].index[-1].date()
    avant = magasin_test.barre_du_jour("TST", date(2020, 3, 20))
    magasin_test.poser_direct({"TST": barres(["2020-03-20", "2020-03-25", "2020-03-26"]), "INCONNU": barres(["2020-03-26"])})
    assert magasin_test.a_du_direct() and fin_base == date(2020, 3, 24)
    assert magasin_test.barre_du_jour("TST", date(2020, 3, 20)) == avant                # l'historique n'est jamais remplacé
    live = magasin_test.barre_du_jour("TST", date(2020, 3, 26))
    assert live["direct"] is True and live["close"] == pytest.approx(123.45)
    assert "direct" not in magasin_test.barre_du_jour("TST", date(2020, 3, 24))
    assert magasin_test.derniere_cloture_avant("TST", date(2020, 3, 26)) == pytest.approx(barres(["2020-03-20", "2020-03-25", "2020-03-26"]).loc["2020-03-25", "close"])
    assert not magasin_test.a_des_donnees("INCONNU")


def test_les_crises_ne_touchent_pas_les_barres_directes(magasin_test):
    serie = magasin_test.series_origine()["TST"]
    magasin_test.appliquer_scenarios({"TST": pd.Series(0.5, index=serie.index)})
    magasin_test.poser_direct({"TST": barres(["2020-03-25", "2020-03-26"])})
    assert magasin_test.barre_du_jour("TST", date(2020, 3, 26))["close"] == pytest.approx(123.45)
    assert magasin_test.barre_du_jour("TST", date(2020, 3, 10))["close"] == pytest.approx(serie.loc["2020-03-10", "close"] * 0.5)


def test_cotation_directe_selon_la_seance(ctx_test):
    ctx_test.magasin.poser_direct({"TST": barres(["2020-03-25", "2020-03-26"])})
    m = ctx_test.moteur
    c = m.cotation("TST", datetime(2020, 3, 26, 16, 0))
    assert (c.prix, c.statut, c.origine) == (pytest.approx(123.45), "ouvert", "direct")      # le dernier prix, pas un tick simulé
    assert c.barre_en_formation["close"] == pytest.approx(123.45)
    avant = m.cotation("TST", datetime(2020, 3, 26, 13, 0))
    assert avant.statut == "ferme" and avant.origine == "cloture_precedente"
    apres = m.cotation("TST", datetime(2020, 3, 26, 22, 0))
    assert apres.statut == "ferme" and apres.origine == "cloture" and apres.prix == pytest.approx(123.45)
    h = m.historique("TST", datetime(2020, 3, 26, 16, 0), 5)
    assert h[-1]["date"] == "2020-03-26" and h[-1]["en_formation"] is True and h[-2]["date"] == "2020-03-25"


# ------------------------------------------------------------------ fournisseur
def test_un_echec_du_flux_garde_les_derniers_prix(ctx_test):
    etat = {"ok": True}

    def telechargeur(symboles):
        if not etat["ok"]:
            raise ConnectionError("réseau coupé")
        return faux_flux()(symboles)

    f = FournisseurDirect(ctx_test.magasin, ctx_test.moteur, ctx_test.univers, telechargeur)
    assert f.rafraichir() and f.erreur is None and f.derniere_maj is not None
    etat["ok"] = False
    assert f.rafraichir() is False and "réseau coupé" in f.erreur
    assert ctx_test.magasin.a_du_direct()                                       # les prix déjà reçus restent servis
    assert f.etat()["erreur"] and f.etat()["age_secondes"] >= 0


def test_flux_vide_est_une_erreur(ctx_test):
    f = FournisseurDirect(ctx_test.magasin, ctx_test.moteur, ctx_test.univers, lambda s: {})
    assert f.rafraichir() is False and "aucune donnée" in f.erreur and not ctx_test.magasin.a_du_direct()


def test_analyse_de_la_reponse_yahoo(monkeypatch):
    idx = pd.DatetimeIndex(pd.to_datetime(["2026-11-02", "2026-11-03"])).tz_localize("America/New_York")
    cols = pd.MultiIndex.from_product([["AAPL", "VIDE"], ["Open", "High", "Low", "Close", "Volume"]])
    brut = pd.DataFrame(np.nan, index=idx, columns=cols)
    brut[("AAPL", "Open")], brut[("AAPL", "High")], brut[("AAPL", "Low")] = [10, 11], [12, 13], [9, 10]
    brut[("AAPL", "Close")], brut[("AAPL", "Volume")] = [11, 12], [5, 6]
    appels = []
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=lambda *a, **k: appels.append((a, k)) or brut))
    sortie = telechargeur_yahoo(["AAPL", "VIDE", "ABSENT"])
    assert set(sortie) == {"AAPL"}                                              # tout NaN ou absent : ignoré
    df = sortie["AAPL"]
    assert list(df.columns) == ["open", "high", "low", "close", "volume"] and df.index.tz is None
    assert df["close"].tolist() == [11, 12] and df.index[0] == pd.Timestamp("2026-11-02")
    assert appels[0][1]["interval"] == "1d" and appels[0][1]["auto_adjust"] is True


# ------------------------------------------------------------------ API
def test_activation_horloge_et_trading_en_direct(client, utilisateur, flux, ctx_test):
    bob = utilisateur("bob@example.com", "Bob")
    r = client.get("/api/v1/direct/etat", headers=bob.h).json()
    assert r["disponible"] and r["beta"] and r["actif"] is False and len(r["avertissements"]) >= 4

    r = client.post("/api/v1/direct/activer", headers=bob.h)
    assert r.status_code == 200 and r.json()["actif"] and r.json()["flux"]["erreur"] is None
    inst = client.get("/api/v1/marche/instantane", headers=bob.h).json()
    assert inst["direct"] is True and inst["termine"] is False and inst["direct_flux"]["nb_symboles"] == 2
    assert inst["instant"].startswith("2020-03-26T16:0")                          # l'heure réelle (patchée), pas la période rejouée
    tst = next(c for c in inst["cotations"] if c["symbole"] == "TST")
    assert tst["origine"] == "direct" and tst["prix"] == pytest.approx(123.45)

    for chemin, corps in [("/api/v1/horloge/pause", None), ("/api/v1/horloge/reprendre", None),
                          ("/api/v1/horloge/facteur", {"facteur": 10}), ("/api/v1/horloge/aller-a", {"instant": "2020-02-10T10:00:00"})]:
        r = client.post(chemin, json=corps, headers=bob.h) if corps else client.post(chemin, headers=bob.h)
        assert r.status_code == 409 and "Direct" in r.json()["detail"], chemin

    o = client.post("/api/v1/ordres", json={"symbole": "TST", "sens": "achat", "quantite": 10, "type": "marche"}, headers=bob.h)
    assert o.status_code == 201 and o.json()["statut"] == "execute"
    pos = client.get("/api/v1/portefeuille", headers=bob.h).json()["positions"][0]
    assert pos["prix_marche"] == pytest.approx(123.45, rel=1e-3) and pos["prix_moyen"] == pytest.approx(123.45, rel=0.01)   # écart acheteur-vendeur de quelques points de base

    q = client.post("/api/v1/direct/quitter", headers=bob.h)
    assert q.status_code == 200 and q.json()["actif"] is False
    inst = client.get("/api/v1/marche/instantane", headers=bob.h).json()
    assert inst["direct"] is False and inst["horloge"]["en_pause"] is True and inst["instant"].startswith("2020-12-31")
    assert client.post("/api/v1/horloge/aller-a", json={"instant": "2020-02-10T10:00:00"}, headers=bob.h).status_code == 200


def test_activation_refusee_quand_le_flux_est_indisponible(client, utilisateur, monkeypatch, ctx_test):
    def echec(symboles):
        raise ConnectionError("pas d'Internet")
    monkeypatch.setattr(routes, "telechargeur_actuel", echec)
    bob = utilisateur("bob@example.com", "Bob")
    r = client.post("/api/v1/direct/activer", headers=bob.h)
    assert r.status_code == 503 and "indisponibles" in r.json()["detail"] and "pas d'Internet" in r.json()["detail"]
    assert client.get("/api/v1/direct/etat", headers=bob.h).json()["actif"] is False
    assert client.get("/api/v1/marche/instantane", headers=bob.h).json()["direct"] is False


def test_mode_direct_desactive_par_configuration(client, utilisateur, flux, monkeypatch):
    monkeypatch.setattr(config, "DIRECT_ACTIF", False)
    bob = utilisateur("bob@example.com", "Bob")
    assert client.post("/api/v1/direct/activer", headers=bob.h).status_code == 403
    assert client.get("/api/v1/direct/etat", headers=bob.h).json()["disponible"] is False


def test_direct_reserve_aux_utilisateurs_connectes(client):
    assert client.get("/api/v1/direct/etat").status_code == 401
    assert client.post("/api/v1/direct/activer").status_code == 401


def test_chaque_utilisateur_a_sa_propre_horloge(client, utilisateur, flux):
    bob, alice = utilisateur("bob@example.com", "Bob"), utilisateur("alice@example.com", "Alice")
    client.post("/api/v1/direct/activer", headers=bob.h)
    assert client.get("/api/v1/marche/instantane", headers=alice.h).json()["direct"] is False
    assert client.post("/api/v1/horloge/aller-a", json={"instant": "2020-02-10T10:00:00"}, headers=alice.h).status_code == 200


def test_flux_de_demonstration_est_signale_et_prolonge_l_instantane(client, utilisateur, monkeypatch, ctx_test):
    monkeypatch.setattr(config, "DIRECT_DEMO", True)
    monkeypatch.setattr("app.contexte.maintenant_utc", lambda: MAINTENANT)
    f = fournisseur.flux_demonstration(ctx_test.magasin)
    sortie = f(["TST", "CRY", "XXX"])
    assert set(sortie) == {"TST", "CRY"}                                          # inconnu ignoré
    assert sortie["TST"].index[0] == pd.Timestamp("2020-03-25") and (sortie["TST"]["high"] >= sortie["TST"]["low"]).all()
    bob = utilisateur("bob@example.com", "Bob")
    e = client.get("/api/v1/direct/etat", headers=bob.h).json()
    assert e["demo"] is True and "DÉMONSTRATION" in e["avertissements"][0]
