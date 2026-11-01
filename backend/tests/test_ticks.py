from datetime import date

import numpy as np
import pytest

from app.marche.ticks import barre_partielle, generer_ticks, graine_barre, prix_a_fraction

BARRES = [
    (100.0, 105.0, 98.0, 103.0),     # haussière
    (100.0, 104.0, 95.0, 96.0),      # baissière
    (100.0, 100.0, 90.0, 100.0),     # ouverture = clôture = haut
    (50.0, 50.5, 49.5, 50.0),
    (18.27, 20.0, -40.0, -37.63),    # type WTI du 20 avril 2020 : prix négatif
    (-5.0, -3.0, -9.0, -4.0),        # entièrement négative
]


@pytest.mark.parametrize("o,h,l,c", BARRES)
@pytest.mark.parametrize("graine", [0, 1, 42, 12345])
def test_le_chemin_respecte_exactement_la_bougie(o, h, l, c, graine):
    chemin = generer_ticks(o, h, l, c, n=96, graine=graine)
    assert len(chemin) == 96
    assert chemin[0] == o and chemin[-1] == c
    assert chemin.max() == pytest.approx(h) and chemin.min() == pytest.approx(l)
    assert (chemin >= l - 1e-12).all() and (chemin <= h + 1e-12).all()


def test_deterministe_et_graine_differente_donne_chemin_different():
    a = generer_ticks(100, 105, 98, 103, graine=7)
    b = generer_ticks(100, 105, 98, 103, graine=7)
    c = generer_ticks(100, 105, 98, 103, graine=8)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_bougie_plate():
    assert (generer_ticks(10, 10, 10, 10, n=20) == 10).all()


def test_n_trop_petit():
    with pytest.raises(ValueError):
        generer_ticks(1, 2, 0, 1, n=3)


def test_donnees_incoherentes_sont_bornees_par_les_quatre_prix():
    # high < close : le chemin utilise max/min des quatre prix
    chemin = generer_ticks(100, 101, 99, 110, n=50, graine=3)
    assert chemin.max() == pytest.approx(110) and chemin[-1] == 110


def test_graine_stable_et_dependante_du_jour_et_du_symbole():
    assert graine_barre("AAPL", date(2020, 3, 9)) == graine_barre("AAPL", date(2020, 3, 9))
    assert graine_barre("AAPL", date(2020, 3, 9)) != graine_barre("AAPL", date(2020, 3, 10))
    assert graine_barre("AAPL", date(2020, 3, 9)) != graine_barre("MSFT", date(2020, 3, 9))
    # valeur de référence : détecte tout changement involontaire de l'algorithme de graine
    assert graine_barre("AAPL", date(2020, 3, 9)) == 3579398445


def test_barre_partielle_ne_revele_pas_le_futur():
    o, h, l, c = 100.0, 110.0, 90.0, 105.0
    chemin = generer_ticks(o, h, l, c, n=96, graine=5)
    debut = barre_partielle(chemin, 0.0)
    assert debut["open"] == debut["high"] == debut["low"] == debut["close"] == o

    hauts, bas = [], []
    for f in np.linspace(0, 1, 41):
        b = barre_partielle(chemin, float(f))
        hauts.append(b["high"])
        bas.append(b["low"])
        assert b["low"] <= b["close"] <= b["high"]
    assert all(x <= y + 1e-12 for x, y in zip(hauts, hauts[1:]))    # le plus haut ne peut que monter
    assert all(x >= y - 1e-12 for x, y in zip(bas, bas[1:]))        # le plus bas ne peut que descendre

    fin = barre_partielle(chemin, 1.0)
    assert (fin["open"], fin["high"], fin["low"], fin["close"]) == pytest.approx((o, h, l, c))


def test_prix_a_fraction_bornes():
    chemin = generer_ticks(100, 105, 98, 103)
    assert prix_a_fraction(chemin, -1) == chemin[0]
    assert prix_a_fraction(chemin, 2) == chemin[-1]
