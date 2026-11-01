"""Indicateurs de risque et de performance : fonctions pures, sans base de données ni réseau.

Conventions (documentées dans docs/DECISIONS.md, D19) :
- les rendements sont relatifs : (b - a) / |a| (valable même si un prix est négatif) ;
- taux sans risque = 0 ;
- les statistiques de la courbe de valeur tiennent compte de la durée réelle entre deux points
  (le temps simulé avance par sauts irréguliers) ; l'annualisation se fait sur 365 jours ;
- la VaR et la CVaR sont historiques (aucune loi supposée), exprimées en perte positive.
"""
from __future__ import annotations

import math
from datetime import datetime

import numpy as np
import pandas as pd

JOURS_AN = 365.0
MIN_POINTS_COURBE = 10
MIN_JOURS_VAR = 30


def rendements_relatifs(valeurs) -> list[float]:
    v = list(valeurs)
    return [(b - a) / abs(a) for a, b in zip(v, v[1:]) if a != 0]


def drawdown(valeurs) -> dict:
    """Perte maximale depuis un plus haut (drawdown max) et perte actuelle depuis le dernier plus haut, en fractions."""
    pic, maxi, courant = None, 0.0, 0.0
    for v in valeurs:
        pic = v if pic is None else max(pic, v)
        courant = (pic - v) / pic if pic and pic > 0 else 0.0
        maxi = max(maxi, courant)
    return {"max": maxi, "courant": courant}


def statistiques_courbe(points: list[tuple[datetime, float]]) -> dict | None:
    """Volatilité, rendement annualisé, Sharpe et Sortino d'une courbe de valeur irrégulièrement espacée."""
    if len(points) < MIN_POINTS_COURBE:
        return None
    rendements, durees = [], []
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        dt = (t1 - t0).total_seconds() / 86400.0
        if dt > 0 and v0 > 0:
            rendements.append((v1 - v0) / v0)
            durees.append(dt)
    if len(rendements) < MIN_POINTS_COURBE - 1:
        return None
    r, d = np.array(rendements), np.array(durees)
    normalises = r / np.sqrt(d)                          # rendement « par racine de jour »
    vol_an = float(np.std(normalises, ddof=1) * math.sqrt(JOURS_AN))
    rend_an = float(r.sum() / d.sum() * JOURS_AN)
    baisse = np.minimum(normalises, 0.0)
    semi = float(math.sqrt(np.mean(baisse ** 2)) * math.sqrt(JOURS_AN))
    return {
        "volatilite_annuelle": vol_an,
        "rendement_annuel": rend_an,
        "sharpe": rend_an / vol_an if vol_an > 1e-12 else None,
        "sortino": rend_an / semi if semi > 1e-12 else None,
    }


def var_cvar(rendements, niveau: float = 0.95) -> dict | None:
    """VaR et CVaR historiques d'un jour, en pertes positives (0,03 = perte de 3 %)."""
    r = np.asarray(list(rendements), dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < MIN_JOURS_VAR:
        return None
    pertes = -r
    var = float(max(np.quantile(pertes, niveau), 0.0))
    queue = pertes[pertes >= var]
    cvar = float(max(queue.mean(), 0.0)) if len(queue) else var
    return {"var": var, "cvar": cvar, "jours": int(len(r)), "niveau": niveau}


def rendements_actifs(series_prix: dict[str, pd.Series]) -> pd.DataFrame:
    """Rendements journaliers alignés sur les jours où tous les actifs cotent."""
    cols = {}
    for symbole, s in series_prix.items():
        s = s.astype(float)
        cols[symbole] = (s - s.shift(1)) / s.shift(1).abs()
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).replace([np.inf, -np.inf], np.nan).dropna()


def rendements_portefeuille(poids: dict[str, float], rendements: pd.DataFrame) -> pd.Series:
    """Rendements historiques qu'aurait eus le portefeuille ACTUEL (poids constants) sur la période passée."""
    cols = [s for s in poids if s in rendements.columns]
    if not cols:
        return pd.Series(dtype=float)
    w = np.array([poids[s] for s in cols])
    return pd.Series(rendements[cols].to_numpy() @ w, index=rendements.index)


def concentration(poids_investis: dict[str, float]) -> dict | None:
    """Indice de Herfindahl (somme des carrés des parts) et nombre effectif de positions."""
    total = sum(abs(w) for w in poids_investis.values())
    if total <= 0:
        return None
    parts = {s: abs(w) / total for s, w in poids_investis.items()}
    hhi = sum(p * p for p in parts.values())
    plus_grosse = max(parts, key=parts.get)
    return {"hhi": hhi, "nb_effectif": 1.0 / hhi, "plus_grosse_position": {"symbole": plus_grosse, "part": parts[plus_grosse]}}


def score_diversification(hhi: float, nb_marches: int) -> int:
    """Note pédagogique de 0 à 100 : 100 x (1 - HHI) x (0,6 + 0,4 x marchés investis / 3).
    Une seule position donne 0 ; dix positions égales réparties sur trois marchés donnent 90."""
    return int(round(100 * (1 - hhi) * (0.6 + 0.4 * min(nb_marches, 3) / 3)))


def comparer_profil(profil: dict | None, drawdown_courant: float | None, var95: float | None) -> dict:
    """Compare la perte tolérée déclarée à la perte actuelle depuis le plus haut (et à la VaR d'un jour)."""
    if not profil:
        return {"statut": "profil_absent"}
    tolerance = profil["perte_max_toleree_pct"] / 100.0
    courant = drawdown_courant or 0.0
    statut = "depasse" if courant > tolerance else "proche" if courant > 0.75 * tolerance else "ok"
    return {
        "statut": statut, "categorie": profil["categorie"], "perte_tolerance": tolerance,
        "perte_actuelle": courant, "utilisation": courant / tolerance if tolerance else None,
        "var95_jour": var95, "var_sur_tolerance": (var95 / tolerance) if (var95 is not None and tolerance) else None,
    }
