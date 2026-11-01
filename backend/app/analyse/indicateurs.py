"""Indicateurs techniques classiques : SMA, EMA, bandes de Bollinger, RSI, MACD, ATR.

Fonctions pures sur des tableaux numpy. La valeur à la date t n'utilise que les données jusqu'à t : rien ne regarde
le futur. Les premières valeurs, tant que l'historique est trop court, valent NaN (jamais une valeur inventée).
Conventions (décision D22) :
- EMA : première valeur = moyenne simple des n premières clôtures, puis coefficient 2 / (n + 1).
- RSI et ATR : lissage de Wilder (première valeur = moyenne simple des n premières, puis coefficient 1 / n).
- Bollinger : moyenne mobile sur n jours, écart-type de la population (ddof = 0), bandes à k écarts-types.
- RSI d'une série plate (ni hausse ni baisse) : 50 ; sans aucune baisse : 100.
Les prix négatifs (pétrole WTI du 20 avril 2020) ne posent pas de problème : aucun logarithme n'est utilisé.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PARAMETRES = {
    "sma_courte": 20, "sma_longue": 50, "ema": 20,
    "bollinger": {"n": 20, "k": 2.0}, "rsi": 14,
    "macd": {"rapide": 12, "lente": 26, "signal": 9}, "atr": 14,
}


def _premier_valide(x: np.ndarray) -> int | None:
    valides = np.flatnonzero(~np.isnan(x))
    return int(valides[0]) if valides.size else None


def _lisser(x: np.ndarray, n: int, alpha: float) -> np.ndarray:
    """Moyenne mobile exponentielle amorcée par une moyenne simple. Ignore les NaN du début."""
    sortie = np.full(len(x), np.nan)
    debut = _premier_valide(x)
    if debut is None or len(x) - debut < n:
        return sortie
    sortie[debut + n - 1] = x[debut:debut + n].mean()
    for i in range(debut + n, len(x)):
        sortie[i] = alpha * x[i] + (1.0 - alpha) * sortie[i - 1]
    return sortie


def sma(cloture, n: int) -> np.ndarray:
    return pd.Series(np.asarray(cloture, dtype=float)).rolling(n).mean().to_numpy()


def ema(valeurs, n: int) -> np.ndarray:
    return _lisser(np.asarray(valeurs, dtype=float), n, 2.0 / (n + 1))


def bollinger(cloture, n: int = 20, k: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(moyenne, bande haute, bande basse)."""
    s = pd.Series(np.asarray(cloture, dtype=float))
    milieu = s.rolling(n).mean()
    ecart = s.rolling(n).std(ddof=0)
    return milieu.to_numpy(), (milieu + k * ecart).to_numpy(), (milieu - k * ecart).to_numpy()


def rsi(cloture, n: int = 14) -> np.ndarray:
    c = np.asarray(cloture, dtype=float)
    sortie = np.full(len(c), np.nan)
    if len(c) <= n:
        return sortie
    delta = np.diff(c, prepend=np.nan)
    hausses = np.where(delta > 0, delta, 0.0)
    baisses = np.where(delta < 0, -delta, 0.0)
    hausses[0] = baisses[0] = np.nan
    moy_h, moy_b = _lisser(hausses, n, 1.0 / n), _lisser(baisses, n, 1.0 / n)
    for i in range(len(c)):
        if np.isnan(moy_h[i]):
            continue
        if moy_b[i] == 0:
            sortie[i] = 100.0 if moy_h[i] > 0 else 50.0
        else:
            sortie[i] = 100.0 - 100.0 / (1.0 + moy_h[i] / moy_b[i])
    return sortie


def macd(cloture, rapide: int = 12, lente: int = 26, signal: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(ligne MACD, ligne de signal, histogramme)."""
    ligne = ema(cloture, rapide) - ema(cloture, lente)
    ligne_signal = ema(ligne, signal)
    return ligne, ligne_signal, ligne - ligne_signal


def atr(haut, bas, cloture, n: int = 14) -> np.ndarray:
    """Amplitude moyenne vraie : la fourchette de prix habituelle d'une journée, écarts d'ouverture compris."""
    h, b, c = (np.asarray(x, dtype=float) for x in (haut, bas, cloture))
    vraie = h - b
    if len(c) > 1:
        vraie[1:] = np.maximum.reduce([h[1:] - b[1:], np.abs(h[1:] - c[:-1]), np.abs(b[1:] - c[:-1])])
    return _lisser(vraie, n, 1.0 / n)


def _liste(x: np.ndarray) -> list[float | None]:
    return [None if np.isnan(v) else float(v) for v in x]


def calculer_tout(barres: list[dict]) -> dict[str, list[float | None]]:
    """Tous les indicateurs d'une liste de bougies {open, high, low, close}, alignés sur ces bougies."""
    p = PARAMETRES
    haut = np.array([b["high"] for b in barres], dtype=float)
    bas = np.array([b["low"] for b in barres], dtype=float)
    cloture = np.array([b["close"] for b in barres], dtype=float)
    milieu, haute, basse = bollinger(cloture, p["bollinger"]["n"], p["bollinger"]["k"])
    ligne, signal, histo = macd(cloture, **p["macd"])
    return {
        "sma_courte": _liste(sma(cloture, p["sma_courte"])),
        "sma_longue": _liste(sma(cloture, p["sma_longue"])),
        "ema": _liste(ema(cloture, p["ema"])),
        "bollinger_milieu": _liste(milieu), "bollinger_haute": _liste(haute), "bollinger_basse": _liste(basse),
        "rsi": _liste(rsi(cloture, p["rsi"])),
        "macd": _liste(ligne), "macd_signal": _liste(signal), "macd_histogramme": _liste(histo),
        "atr": _liste(atr(haut, bas, cloture, p["atr"])),
    }
