"""Bougies en unités de temps de 1 minute à 1 jour, construites à partir des ticks SIMULÉS du moteur de cotation.

Les données sont journalières. Le moteur reconstruit pour chaque séance un chemin de ticks (96 par défaut) qui respecte la
bougie du jour, et le prix entre deux ticks est interpolé linéairement : c'est ce prix que voient l'interface et le moteur
d'exécution des ordres. Les bougies intrajournalières sont donc lues sur cette même fonction de prix, sans rien inventer :
 - ouverture = prix au début de l'intervalle, clôture = prix à la fin (ou à l'instant simulé si l'intervalle est en cours) ;
 - plus haut / plus bas = extrêmes de ces deux prix et des ticks situés à l'intérieur (exact pour un chemin linéaire par morceaux).
Les intervalles sont alignés sur l'heure UTC (une bougie d'une heure couvre 14:00-15:00 même si la séance ouvre à 14:30).
Volume intrajournalier : absent des données, renvoyé à None (jamais réparti artificiellement).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np

UNITES = {"1min": 60, "5min": 300, "15min": 900, "1h": 3600, "1j": 86400}
EPOQUE = datetime(1970, 1, 1)


def secondes(d: datetime) -> float:
    return (d - EPOQUE).total_seconds()


def bougies_seance(debut: datetime, fin: datetime, chemin: np.ndarray, jusqu_a: datetime, unite_s: int) -> list[dict]:
    """Bougies d'une séance [debut, fin] (UTC sans fuseau) dont le chemin de ticks est réparti uniformément,
    tronquées à l'instant simulé `jusqu_a` (rien après lui n'est lu)."""
    if jusqu_a <= debut or len(chemin) < 2:
        return []
    duree = (fin - debut).total_seconds()
    fin_lue = min(duree, (jusqu_a - debut).total_seconds())             # secondes depuis l'ouverture
    temps = np.linspace(0.0, duree, len(chemin))                         # instant de chaque tick
    prix = lambda s: float(np.interp(s, temps, chemin))                  # noqa: E731  (même interpolation que le moteur)
    zero = secondes(debut)
    a = math.floor(zero / unite_s) * unite_s                             # début de la première bougie, aligné UTC
    sortie = []
    while a - zero < fin_lue:
        s_a, s_b = max(a - zero, 0.0), min(a + unite_s - zero, fin_lue)
        interieurs = chemin[(temps > s_a) & (temps < s_b)]
        points = [prix(s_a), *map(float, interieurs), prix(s_b)]
        sortie.append({"t": int(a), "open": points[0], "high": max(points), "low": min(points), "close": points[-1],
                       "volume": None, "en_formation": a + unite_s - zero > fin_lue and fin_lue < duree})
        a += unite_s
    return sortie


def bougies_intraday(moteur, symbole: str, jours: list, t: datetime, unite_s: int, n: int) -> list[dict]:
    """Les `n` dernières bougies jusqu'à l'instant t, en parcourant les séances `jours` (dates croissantes, jour de t inclus)."""
    sortie: list[dict] = []
    for jour in reversed(jours):
        seance = moteur.chemin_seance(symbole, jour)
        if seance is None:
            continue
        debut, fin, chemin = seance
        sortie[:0] = bougies_seance(debut, fin, chemin, t, unite_s)
        if len(sortie) >= n:
            break
    return sortie[-n:]


def nb_seances_utiles(unite_s: int, n: int, duree_seance_s: float) -> int:
    """Nombre de séances à lire pour obtenir n bougies (avec une marge pour les séances partielles)."""
    return min(1000, math.ceil(n * unite_s / max(duree_seance_s, 1.0)) + 3)


def duree_seance(session_utc) -> float:
    if session_utc is None:
        return 86400.0
    d, f = session_utc
    return (timedelta(hours=f.hour, minutes=f.minute) - timedelta(hours=d.hour, minutes=d.minute)).total_seconds()
