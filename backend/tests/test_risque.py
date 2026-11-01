"""Indicateurs de risque : vérifiés sur des valeurs calculables à la main."""
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.risque import indicateurs as ind


def courbe(rendements, dt_jours=1.0, depart=100.0):
    t, v, pts = datetime(2020, 1, 1), depart, []
    pts.append((t, v))
    for r in rendements:
        t, v = t + timedelta(days=dt_jours), v * (1 + r)
        pts.append((t, v))
    return pts


def test_rendements_relatifs_et_prix_negatif():
    assert ind.rendements_relatifs([100, 110, 99]) == pytest.approx([0.10, -0.10])
    assert ind.rendements_relatifs([-10, -5]) == pytest.approx([0.5])      # base en valeur absolue
    assert ind.rendements_relatifs([0, 5]) == []                           # division par zéro évitée


def test_drawdown():
    d = ind.drawdown([100, 120, 90, 95])
    assert d["max"] == pytest.approx(0.25) and d["courant"] == pytest.approx(25 / 120)
    assert ind.drawdown([100, 101, 105]) == {"max": 0.0, "courant": 0.0}
    assert ind.drawdown([]) == {"max": 0.0, "courant": 0.0}


def test_statistiques_courbe_valeur_connue():
    s = ind.statistiques_courbe(courbe([0.01, -0.01] * 6))                  # 13 points, 12 rendements
    ecart_type = math.sqrt(12 * 1e-4 / 11)
    assert s["volatilite_annuelle"] == pytest.approx(ecart_type * math.sqrt(365), rel=1e-6)
    assert s["rendement_annuel"] == pytest.approx(0.0, abs=1e-12) and s["sharpe"] == pytest.approx(0.0, abs=1e-9)


def test_statistiques_tiennent_compte_de_la_duree_entre_deux_points():
    un = ind.statistiques_courbe(courbe([0.01, -0.01] * 6, dt_jours=1))
    deux = ind.statistiques_courbe(courbe([0.01, -0.01] * 6, dt_jours=2))
    assert deux["volatilite_annuelle"] == pytest.approx(un["volatilite_annuelle"] / math.sqrt(2), rel=1e-9)


def test_croissance_reguliere_sans_volatilite_donne_sharpe_indefini():
    s = ind.statistiques_courbe(courbe([0.01] * 15))
    assert s["volatilite_annuelle"] == pytest.approx(0.0, abs=1e-9) and s["sharpe"] is None and s["sortino"] is None
    assert s["rendement_annuel"] == pytest.approx(0.01 * 365)


def test_pas_assez_de_points():
    assert ind.statistiques_courbe(courbe([0.01] * 5)) is None


def test_sortino_ne_penalise_que_les_baisses():
    haussier = ind.statistiques_courbe(courbe([0.02, 0.01] * 6))            # aucune baisse
    assert haussier["sortino"] is None                                        # pas de risque à la baisse mesurable
    mixte = ind.statistiques_courbe(courbe([0.03, -0.01] * 6))
    assert mixte["sortino"] is not None and mixte["sortino"] > mixte["sharpe"]


def test_var_et_cvar_historiques():
    r = [0.01] * 90 + [-0.05] * 10
    v = ind.var_cvar(r, 0.95)
    assert v["var"] == pytest.approx(0.05) and v["cvar"] == pytest.approx(0.05) and v["jours"] == 100
    r2 = [0.01] * 94 + [-0.02, -0.04, -0.06, -0.08, -0.10, -0.12]
    v2 = ind.var_cvar(r2, 0.95)
    assert v2["cvar"] >= v2["var"] > 0                                       # la CVaR est la perte moyenne au-delà de la VaR


def test_var_sans_assez_de_jours_ou_sans_perte():
    assert ind.var_cvar([0.01] * 29) is None
    assert ind.var_cvar([0.01] * 40)["var"] == 0.0                           # jamais négative


def test_rendements_portefeuille_poids_constants():
    idx = pd.date_range("2020-01-01", periods=40)
    a = pd.Series(100 * 1.01 ** np.arange(40), index=idx)
    b = pd.Series(100 * 0.99 ** np.arange(40), index=idx)
    retours = ind.rendements_actifs({"A": a, "B": b})
    assert len(retours) == 39
    port = ind.rendements_portefeuille({"A": 0.5, "B": 0.5}, retours)
    assert port.abs().max() < 1e-12                                          # +1 % et -1 % se compensent
    assert ind.rendements_portefeuille({"A": 1.0}, retours).mean() == pytest.approx(0.01)


def test_rendements_actifs_alignes_sur_les_jours_communs():
    a = pd.Series([1.0, 2, 3, 4], index=pd.date_range("2020-01-01", periods=4))
    b = pd.Series([1.0, 2, 3], index=pd.date_range("2020-01-02", periods=3))
    assert len(ind.rendements_actifs({"A": a, "B": b})) == 2


def test_concentration_et_diversification():
    assert ind.concentration({}) is None
    c = ind.concentration({"A": 50, "B": 50})
    assert c["hhi"] == pytest.approx(0.5) and c["nb_effectif"] == pytest.approx(2)
    assert ind.concentration({"A": 100})["hhi"] == pytest.approx(1.0)
    assert ind.concentration({"A": 90, "B": 10})["plus_grosse_position"]["symbole"] == "A"
    assert ind.score_diversification(1.0, 1) == 0
    assert ind.score_diversification(0.1, 3) == 90
    assert ind.score_diversification(0.5, 2) == 43


def test_comparaison_au_profil_de_risque():
    profil = {"categorie": "équilibré", "perte_max_toleree_pct": 10.0}
    assert ind.comparer_profil(profil, 0.05, 0.02)["statut"] == "ok"
    assert ind.comparer_profil(profil, 0.08, None)["statut"] == "proche"
    d = ind.comparer_profil(profil, 0.12, 0.03)
    assert d["statut"] == "depasse" and d["utilisation"] == pytest.approx(1.2) and d["var_sur_tolerance"] == pytest.approx(0.3)
    assert ind.comparer_profil(None, 0.5, None) == {"statut": "profil_absent"}
