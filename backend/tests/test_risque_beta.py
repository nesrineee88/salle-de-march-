"""Écart-type, bêta, covariance et distribution des rendements (cahier des charges, section 5)."""
import math

import numpy as np
import pandas as pd
import pytest

from app.risque import indicateurs as ind
from app.risque.analyse import analyser


def test_ecart_type_exemple_a_la_main():
    # moyenne 0 ; carrés : 1e-4 + 1e-4 + 9e-4 + 9e-4 = 2e-3 ; / (4 − 1) = 6,667e-4 ; racine = 0,025820
    assert ind.ecart_type([0.01, -0.01, 0.03, -0.03]) == pytest.approx(0.0258199, rel=1e-5)


def test_ecart_type_trop_court_ou_vide():
    assert ind.ecart_type([0.01]) is None
    assert ind.ecart_type([]) is None
    assert ind.ecart_type([0.01, float("nan"), 0.02]) == pytest.approx(math.sqrt(0.00005))   # le NaN est ignoré : 2 points


def test_beta_exemple_a_la_main():
    # marché : moyenne 0, variance (1 + 1 + 4 + 4)e-4 / 3 = 3,333e-4
    # portefeuille : moyenne 0, covariance (2e-4 + 0 + 2e-4 + 6e-4) / 3 = 3,333e-4  → bêta = 1,0
    # variance du portefeuille (4 + 0 + 1 + 9)e-4 / 3 = 4,667e-4 → corrélation = 3,333e-4 / √(4,667e-4 × 3,333e-4) = 0,8452
    r = ind.beta([0.02, 0.0, 0.01, -0.03], [0.01, -0.01, 0.02, -0.02], min_jours=4)
    assert r["beta"] == pytest.approx(1.0)
    assert r["covariance"] == pytest.approx(3.3333e-4, rel=1e-4)
    assert r["variance_marche"] == pytest.approx(3.3333e-4, rel=1e-4)
    assert r["correlation"] == pytest.approx(0.8452, rel=1e-3)
    assert r["jours"] == 4


def test_beta_deux_fois_le_marche():
    m = [0.01, -0.02, 0.03, 0.0]
    p = [2 * x + 0.001 for x in m]                 # même mouvement, deux fois plus fort, décalé d'une constante
    r = ind.beta(p, m, min_jours=4)
    assert r["beta"] == pytest.approx(2.0) and r["correlation"] == pytest.approx(1.0)
    assert r["alpha_jour"] == pytest.approx(0.001)


def test_beta_cas_limites():
    assert ind.beta([0.01] * 40, [0.0] * 40) is None               # marché immobile : variance nulle, division impossible
    assert ind.beta([0.01, 0.02], [0.01, 0.02]) is None              # historique trop court (< 30 jours par défaut)
    with pytest.raises(ValueError):
        ind.beta([0.01, 0.02, 0.03], [0.01, 0.02])                  # séries non alignées


def test_histogramme():
    h = ind.histogramme([-0.02, -0.01, 0.0, 0.0, 0.01, 0.03], nb=5)
    assert sum(h["effectifs"]) == 6 and len(h["bornes"]) == 6
    assert h["bornes"][0] == pytest.approx(-0.02) and h["bornes"][-1] == pytest.approx(0.03)
    assert ind.histogramme([]) is None
    plat = ind.histogramme([0.0, 0.0, 0.0])
    assert sum(plat["effectifs"]) == 3                               # série constante : une classe, pas de division par zéro


def _series(n=80, graine=3):
    rng = np.random.default_rng(graine)
    dates = pd.bdate_range("2020-01-01", periods=n)
    marche = 100 * np.cumprod(1 + rng.normal(0, 0.01, n))
    a = 50 * np.cumprod(1 + 1.5 * (marche / np.roll(marche, 1) - 1) + rng.normal(0, 0.002, n))
    a[0] = 50
    b = 20 * np.cumprod(1 + rng.normal(0, 0.02, n))
    return pd.Series(marche, dates), pd.Series(a, dates), pd.Series(b, dates)


def test_analyser_expose_beta_covariance_et_distribution():
    marche, a, b = _series()
    valo = {"instant": "2020-04-20T17:00:00", "equity": 10_000.0, "cash": 0.0, "capital_initial": 10_000.0,
            "positions": [{"symbole": "A", "valeur": 5_000.0, "quantite": 100, "prix_moyen": 50, "pnl_latent": 0.0},
                          {"symbole": "B", "valeur": 5_000.0, "quantite": 250, "prix_moyen": 20, "pnl_latent": 0.0}]}
    r = analyser(valo, [], {"A": a, "B": b}, {"A": ("action", "Tech"), "B": ("action", "Santé")}, None, benchmark=marche)
    risque = r["risque"]
    assert risque["ecart_type_jour"] > 0
    assert risque["volatilite_annuelle_seances"] == pytest.approx(risque["ecart_type_jour"] * math.sqrt(252))
    # A suit 1,5 fois le marché, B est indépendant : le bêta d'un portefeuille 50/50 est proche de 0,75
    assert 0.5 < r["beta"]["beta"] < 1.0 and r["beta"]["indice"] == "S&P 500"
    assert len(r["beta"]["points"]) == r["beta"]["jours"]
    cov = r["covariances"]
    assert cov["symboles"] == ["A", "B"] and cov["matrice"][0][1] == pytest.approx(cov["matrice"][1][0])
    assert cov["matrice"][0][0] > 0
    assert sum(risque["distribution"]["effectifs"]) == risque["jours"]


def test_analyser_sans_indice_de_reference():
    marche, a, _b = _series()
    valo = {"instant": "2020-04-20T17:00:00", "equity": 5_000.0, "cash": 0.0, "capital_initial": 5_000.0,
            "positions": [{"symbole": "A", "valeur": 5_000.0, "quantite": 100, "prix_moyen": 50, "pnl_latent": 0.0}]}
    r = analyser(valo, [], {"A": a}, {"A": ("action", "Tech")}, None)
    assert r["beta"] is None and r["covariances"] is None             # une seule position : pas de matrice
