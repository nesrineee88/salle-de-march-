from datetime import date, datetime

import pandas as pd
import pytest

from app.marche.moteur import MoteurMarche
from app.marche.stockage import DonneeIndisponible, Magasin


@pytest.fixture
def moteur(magasin_test, univers_test):
    return MoteurMarche(magasin_test, univers_test, nb_ticks=96)


def jour_ouvre(magasin, symbole="TST", rang=10):
    return magasin._series[symbole].index[rang].date()


def test_barres_terminees_strictement_avant_le_jour(magasin_test):
    j = jour_ouvre(magasin_test)
    passe = magasin_test.barres_terminees("TST", j)
    assert passe.index.max() < pd.Timestamp(j)
    assert len(magasin_test.barres_terminees("TST", j, n=3)) == 3


def test_action_pendant_la_seance_prix_dans_la_bougie_du_jour(moteur, magasin_test):
    j = jour_ouvre(magasin_test)
    barre = magasin_test.barre_du_jour("TST", j)
    c = moteur.cotation("TST", datetime(j.year, j.month, j.day, 17, 0))
    assert c.statut == "ouvert" and c.origine == "tick_simule"
    assert barre["low"] - 1e-9 <= c.prix <= barre["high"] + 1e-9
    f = c.barre_en_formation
    assert f["low"] <= c.prix <= f["high"] and f["open"] == pytest.approx(barre["open"])


def test_pas_de_fuite_du_futur_avant_et_apres_la_seance(moteur, magasin_test):
    j = jour_ouvre(magasin_test)
    barre = magasin_test.barre_du_jour("TST", j)
    veille = magasin_test.derniere_cloture_avant("TST", j)

    avant = moteur.cotation("TST", datetime(j.year, j.month, j.day, 9, 0))
    assert avant.statut == "ferme" and avant.prix == veille and avant.barre_en_formation is None

    apres = moteur.cotation("TST", datetime(j.year, j.month, j.day, 22, 0))
    assert apres.statut == "ferme" and apres.origine == "cloture" and apres.prix == pytest.approx(barre["close"])


def test_la_bougie_en_formation_croit_sans_depasser_la_bougie_finale(moteur, magasin_test):
    j = jour_ouvre(magasin_test)
    barre = magasin_test.barre_du_jour("TST", j)
    hauts = []
    for heure in range(15, 21):
        c = moteur.cotation("TST", datetime(j.year, j.month, j.day, heure, 0))
        hauts.append(c.barre_en_formation["high"])
        assert c.barre_en_formation["high"] <= barre["high"] + 1e-9
    assert hauts == sorted(hauts)


def test_cotation_deterministe(moteur, magasin_test):
    j = jour_ouvre(magasin_test)
    t = datetime(j.year, j.month, j.day, 16, 20)
    assert moteur.cotation("TST", t).prix == moteur.cotation("TST", t).prix


def test_weekend_marche_ferme_au_dernier_prix(moteur, magasin_test):
    samedi = datetime(2020, 1, 4, 12, 0)
    c = moteur.cotation("TST", samedi)
    assert c.statut == "ferme" and c.origine == "cloture_precedente"
    assert c.prix == magasin_test.derniere_cloture_avant("TST", samedi.date())


def test_crypto_cote_le_weekend_toute_la_journee(moteur):
    c = moteur.cotation("CRY", datetime(2020, 1, 4, 12, 0))
    assert c.statut == "ouvert" and c.origine == "tick_simule"


def test_avant_la_premiere_cotation(moteur):
    with pytest.raises(DonneeIndisponible):
        moteur.cotation("TST", datetime(2019, 6, 1, 12, 0))


def test_actif_inconnu_et_sans_donnees(moteur):
    with pytest.raises(KeyError):
        moteur.cotation("XXX", datetime(2020, 1, 6, 12, 0))
    with pytest.raises(DonneeIndisponible):
        moteur.cotation("VIDE", datetime(2020, 1, 6, 12, 0))


def test_historique_sans_futur_et_barre_du_jour_marquee(moteur, magasin_test):
    j = jour_ouvre(magasin_test)
    t = datetime(j.year, j.month, j.day, 17, 0)
    h = moteur.historique("TST", t, barres=20)
    assert h[-1]["date"] == j.isoformat() and h[-1]["en_formation"] and h[-1]["volume"] is None
    assert all(not b["en_formation"] for b in h[:-1])
    assert all(b["date"] < j.isoformat() for b in h[:-1])
    assert len(h) <= 20


def test_historique_avant_la_seance_sans_barre_du_jour(moteur, magasin_test):
    j = jour_ouvre(magasin_test)
    h = moteur.historique("TST", datetime(j.year, j.month, j.day, 8, 0), barres=5)
    assert all(b["date"] < j.isoformat() for b in h)


def test_prix_negatif_traverse_le_moteur(univers_test):
    idx = pd.DatetimeIndex(["2020-04-17", "2020-04-20"], name="date")
    df = pd.DataFrame(
        {"open": [18.5, 17.7], "high": [19.0, 18.0], "low": [17.0, -40.3], "close": [18.27, -37.63],
         "volume": [1.0, 2.0], "corrige": False}, index=idx)
    m = MoteurMarche(Magasin({"WTI": df}), univers_test)
    # Le lendemain à minuit, plus de barre : on affiche la dernière clôture connue, négative.
    lendemain = m.cotation("WTI", datetime(2020, 4, 21, 0, 0))
    assert lendemain.prix == pytest.approx(-37.63) and lendemain.origine == "cloture_precedente"
    # Pendant la journée du 20 avril, le prix reste dans la bougie (qui descend à -40.3).
    milieu = m.cotation("WTI", datetime(2020, 4, 20, 12, 0))
    assert -40.3 - 1e-9 <= milieu.prix <= 18.0 + 1e-9
    assert milieu.derniere_cloture == pytest.approx(18.27)


def test_variation_d_un_marche_ferme_utilise_la_seance_precedente(moteur, magasin_test):
    samedi = datetime(2020, 1, 4, 12, 0)
    c = moteur.cotation("TST", samedi)
    avant = magasin_test.barres_terminees("TST", samedi.date())["close"]
    assert c.statut == "ferme" and c.prix == pytest.approx(avant.iloc[-1])
    assert c.reference_variation == pytest.approx(avant.iloc[-2]) and c.reference_variation != c.prix
    j = jour_ouvre(magasin_test)
    ouvert = moteur.cotation("TST", datetime(j.year, j.month, j.day, 17, 0))
    assert ouvert.reference_variation == pytest.approx(ouvert.derniere_cloture)
    apres = moteur.cotation("TST", datetime(j.year, j.month, j.day, 22, 0))
    assert apres.reference_variation == pytest.approx(apres.derniere_cloture)
