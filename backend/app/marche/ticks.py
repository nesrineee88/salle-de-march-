"""Ticks intraday SYNTHÉTIQUES cohérents avec une bougie journalière (OHLC).

Pourquoi : les données sont journalières, mais l'horloge de simulation avance en continu.
Pour que le prix bouge en direct, que les stop-loss se déclenchent et que le carnet d'ordres ait
un sens, on reconstruit un chemin de prix qui respecte exactement la bougie :
    départ = ouverture, arrivée = clôture, maximum = plus haut, minimum = plus bas.

Ce ne sont PAS des prix réels : l'interface doit l'indiquer (« tick simulé »).

Propriétés garanties (testées) :
- déterministe : même bougie + même graine -> même chemin, sur toutes les machines ;
- le chemin reste dans [bas, haut] ; fonctionne avec des prix négatifs (bruit additif, pas de log) ;
- la bougie en formation n'expose jamais le futur : à l'instant t, haut/bas = extrêmes déjà atteints.
"""
from __future__ import annotations

import math
import zlib
from datetime import date

import numpy as np

NB_TICKS_MIN = 8


def graine_barre(symbole: str, jour: date) -> int:
    """Graine stable (CRC32, indépendante du hash() de Python qui varie d'un lancement à l'autre)."""
    return zlib.crc32(f"{symbole}|{jour.isoformat()}".encode("utf-8"))


def _pont(a: float, b: float, m: int, amplitude: float, rng: np.random.Generator) -> np.ndarray:
    """m+1 points de a à b (inclus) : droite + pont brownien (bruit qui revient à 0 aux deux bouts)."""
    t = np.linspace(0.0, 1.0, m + 1)
    ligne = a + (b - a) * t
    if m <= 1 or amplitude == 0:
        return ligne
    marche = np.concatenate([[0.0], np.cumsum(rng.standard_normal(m))])
    pont = marche - t * marche[-1]
    return ligne + pont * (amplitude / math.sqrt(m))


def generer_ticks(
    ouverture: float, haut: float, bas: float, cloture: float, n: int = 96, graine: int = 0
) -> np.ndarray:
    """Chemin de n prix (indices 0..n-1) pour une bougie, du premier tick (ouverture) au dernier (clôture)."""
    if n < NB_TICKS_MIN:
        raise ValueError(f"n doit valoir au moins {NB_TICKS_MIN}")
    hi = max(ouverture, haut, bas, cloture)
    lo = min(ouverture, haut, bas, cloture)
    if hi == lo:
        return np.full(n, float(ouverture))

    rng = np.random.default_rng(graine)
    # Une bougie haussière visite plus souvent son plus bas d'abord (et inversement) : simple vraisemblance.
    bas_d_abord = rng.random() < (0.65 if cloture >= ouverture else 0.35)
    e1, e2 = (lo, hi) if bas_d_abord else (hi, lo)

    dernier = n - 1
    i1 = int(rng.integers(max(1, int(0.10 * dernier)), int(0.50 * dernier) + 1))
    i2 = int(rng.integers(i1 + max(1, int(0.15 * dernier)), int(0.90 * dernier) + 1))
    points = [(0, ouverture), (i1, e1), (i2, e2), (dernier, cloture)]

    amplitude = 0.25 * (hi - lo)
    morceaux = []
    for (ia, va), (ib, vb) in zip(points[:-1], points[1:]):
        segment = _pont(va, vb, ib - ia, amplitude, rng)
        morceaux.append(segment if not morceaux else segment[1:])    # évite de doubler le point de jonction
    chemin = np.clip(np.concatenate(morceaux), lo, hi)

    for i, v in points:                                             # les points clés restent exacts
        chemin[i] = v
    return chemin


def prix_a_fraction(chemin: np.ndarray, fraction: float) -> float:
    """Prix à une fraction f dans [0, 1] de la séance (interpolation linéaire entre ticks)."""
    f = min(max(fraction, 0.0), 1.0)
    return float(np.interp(f * (len(chemin) - 1), np.arange(len(chemin)), chemin))


def barre_partielle(chemin: np.ndarray, fraction: float) -> dict:
    """Bougie en formation à la fraction f : ouverture, extrêmes DÉJÀ atteints, prix courant."""
    f = min(max(fraction, 0.0), 1.0)
    pos = f * (len(chemin) - 1)
    k = int(math.floor(pos))
    courant = prix_a_fraction(chemin, f)
    vus = np.append(chemin[: k + 1], courant)
    return {
        "open": float(chemin[0]),
        "high": float(vus.max()),
        "low": float(vus.min()),
        "close": float(courant),
    }
