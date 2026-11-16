"""Supports, résistances, cassures, tendances et Fibonacci : exemples construits à la main."""
import pytest

from app.analyse.niveaux import cassures, fibonacci, lignes_tendance, pivots, supports_resistances


def _b(hauts, bas, clotures=None):
    clotures = clotures or [(h + l) / 2 for h, l in zip(hauts, bas)]
    return [{"t": 1000 * i, "open": c, "high": h, "low": l, "close": c} for i, (h, l, c) in enumerate(zip(hauts, bas, clotures))]


# Le prix bute deux fois sur 110 (indices 3 et 9) et rebondit deux fois sur 100 (indices 6 et 12).
HAUTS = [104, 106, 108, 110, 108, 104, 102, 105, 108, 110, 107, 104, 102, 104, 106, 107]
BAS = [102, 104, 106, 108, 104, 101, 100, 102, 106, 108, 103, 101, 100, 102, 104, 105]


def test_pivots_confirmes_seulement():
    sommets, creux = pivots(_b(HAUTS, BAS), k=2)
    assert sommets == [3, 9] and creux == [6, 12]
    # Sans les 2 bougies suivantes, le creux d'indice 12 n'est pas encore confirmé (pas de regard sur le futur).
    assert pivots(_b(HAUTS[:14], BAS[:14]), k=2)[1] == [6]


def test_supports_resistances():
    n = supports_resistances(_b(HAUTS, BAS), k=2)
    par_type = {x["type"]: x for x in n}
    assert par_type["resistance"]["niveau"] == pytest.approx(110) and par_type["resistance"]["touches"] == 2
    assert par_type["support"]["niveau"] == pytest.approx(100) and par_type["support"]["touches"] == 2
    assert supports_resistances(_b([1, 2], [0, 1])) == []                       # historique trop court


def test_cassure_haussiere_et_mouvement_apres():
    hauts = HAUTS + [109, 113, 115]
    bas = BAS + [106, 110, 112]
    clotures = [(h + l) / 2 for h, l in zip(HAUTS, BAS)] + [108, 112, 114]      # 108 → 112 : la clôture franchit 110
    b = _b(hauts, bas, clotures)
    c = cassures(b, [{"niveau": 110.0, "dernier_indice": 9}], k=2)
    assert len(c) == 1 and c[0]["sens"] == "haussiere" and c[0]["prix"] == 112
    assert c[0]["bougies_depuis"] == 1 and c[0]["variation_depuis"] == pytest.approx(114 / 112 - 1)


def test_tendance_haussiere_par_deux_creux_montants():
    hauts = [12, 11, 10, 11, 12, 14, 13, 12, 13, 15, 16]
    bas = [10, 9, 8, 9, 10, 12, 11, 10, 11, 13, 14]                            # creux 8 (indice 2) puis 10 (indice 7)
    (t,) = [x for x in lignes_tendance(_b(hauts, bas), k=2) if x["sens"] == "haussiere"]
    assert (t["p1"], t["t1"]) == (8, 2000)
    assert t["p2"] == pytest.approx(8 + (10 - 8) / 5 * 8)                        # prolongée jusqu'à l'indice 10 : 11,2


def test_fibonacci_a_la_main():
    # Mouvement haussier de 100 (indice 0) à 200 (indice 2) : 61,8 % de retracement = 200 − 0,618 × 100 = 138,2
    f = fibonacci(_b([110, 150, 200, 190], [100, 140, 180, 170]))
    assert f["sens"] == "haussier" and f["haut"] == 200 and f["bas"] == 100
    assert {n["ratio"]: n["prix"] for n in f["niveaux"]}[0.618] == pytest.approx(138.2)
    baisse = fibonacci(_b([200, 150, 110], [190, 140, 100]))
    assert baisse["sens"] == "baissier" and {n["ratio"]: n["prix"] for n in baisse["niveaux"]}[0.382] == pytest.approx(138.2)
    assert fibonacci(_b([5], [5])) is None
