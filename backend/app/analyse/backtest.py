"""Backtesting de stratégies long seulement sur des bougies journalières, sans regard sur le futur (décision D26).

Convention d'exécution : le signal est calculé avec la clôture du jour t ; la position change À L'OUVERTURE du jour t+1.
Le rendement du jour t+1 se décompose donc en deux morceaux :
    - nuit (clôture t -> ouverture t+1), avec la position détenue la veille ;
    - séance (ouverture t+1 -> clôture t+1), avec la nouvelle position.
Chaque changement de position paie des frais (`cout_bps` par côté, frais de courtage plus demi-écart acheteur-vendeur).
Les rendements sont relatifs à la valeur absolue du prix précédent (le WTI a connu un prix négatif, D7) et un jour ne peut pas
faire perdre plus de 100 % du capital investi.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicateurs as ind

JOURS_AN = 365.25


@dataclass(frozen=True)
class Strategie:
    nom: str
    libelle: str
    description: str
    parametres: dict[str, float]


CATALOGUE: dict[str, Strategie] = {s.nom: s for s in [
    Strategie("achat_conservation", "Achat et conservation", "On achète au début et on ne vend jamais : la référence à battre.", {}),
    Strategie("croisement_sma", "Croisement de moyennes mobiles",
              "On est investi tant que la moyenne mobile courte est au-dessus de la longue (tendance haussière), sinon on est en liquidités.",
              {"courte": 20, "longue": 50}),
    Strategie("rsi", "RSI : rebond après une chute",
              "On achète quand le RSI passe sous le seuil bas (actif très baissier), on vend quand il dépasse le seuil haut.",
              {"periode": 14, "bas": 30, "haut": 70}),
    Strategie("macd", "MACD : croisement avec le signal",
              "On est investi tant que la ligne MACD est au-dessus de sa ligne de signal (la hausse s'accélère).",
              {"rapide": 12, "lente": 26, "signal": 9}),
    Strategie("bollinger", "Bollinger : retour à la moyenne",
              "On achète quand la clôture passe sous la bande basse, on vend quand elle revient à la moyenne.",
              {"periode": 20, "ecarts": 2.0}),
    Strategie("momentum", "Momentum : suivre la tendance longue",
              "On est investi tant que le prix est au-dessus de son niveau d'il y a N jours.",
              {"jours": 120}),
]}


def _bornes(nom: str, p: dict[str, float]) -> None:
    """Valide les paramètres (messages en français affichables tels quels)."""
    def entier(cle, mini, maxi):
        v = p[cle]
        if not (isinstance(v, (int, float)) and math.isfinite(v) and mini <= v <= maxi):
            raise ValueError(f"{CATALOGUE[nom].libelle} : « {cle} » doit être compris entre {mini} et {maxi}")
    if nom == "croisement_sma":
        entier("courte", 2, 200); entier("longue", 3, 400)
        if p["courte"] >= p["longue"]:
            raise ValueError("Croisement de moyennes mobiles : la moyenne courte doit être plus courte que la longue")
    elif nom == "rsi":
        entier("periode", 2, 100); entier("bas", 1, 49); entier("haut", 51, 99)
    elif nom == "macd":
        entier("rapide", 2, 100); entier("lente", 3, 300); entier("signal", 2, 100)
        if p["rapide"] >= p["lente"]:
            raise ValueError("MACD : la moyenne rapide doit être plus courte que la lente")
    elif nom == "bollinger":
        entier("periode", 3, 200); entier("ecarts", 0.5, 4)
    elif nom == "momentum":
        entier("jours", 5, 500)


def signaux(nom: str, params: dict[str, float], df: pd.DataFrame) -> np.ndarray:
    """Position cible (0 ou 1) décidée à la clôture de chaque jour. Ne lit que le passé : la valeur du jour t n'utilise que les jours <= t."""
    if nom not in CATALOGUE:
        raise ValueError(f"stratégie inconnue : {nom}")
    p = {**CATALOGUE[nom].parametres, **(params or {})}
    _bornes(nom, p)
    c = df["close"].to_numpy(dtype=float)
    n = len(c)
    pos = np.zeros(n)
    if nom == "achat_conservation":
        pos[:] = 1.0
    elif nom == "croisement_sma":
        a, b = ind.sma(c, int(p["courte"])), ind.sma(c, int(p["longue"]))
        pos = np.where(~np.isnan(a) & ~np.isnan(b) & (a > b), 1.0, 0.0)
    elif nom == "macd":
        ligne, sig, _ = ind.macd(c, int(p["rapide"]), int(p["lente"]), int(p["signal"]))
        pos = np.where(~np.isnan(ligne) & ~np.isnan(sig) & (ligne > sig), 1.0, 0.0)
    elif nom == "momentum":
        k = int(p["jours"])
        if n > k:
            pos[k:] = np.where(c[k:] > c[:-k], 1.0, 0.0)
    elif nom == "rsi":
        r = ind.rsi(c, int(p["periode"]))
        etat = 0.0
        for i in range(n):
            if not np.isnan(r[i]):
                if etat == 0.0 and r[i] < p["bas"]:
                    etat = 1.0
                elif etat == 1.0 and r[i] > p["haut"]:
                    etat = 0.0
            pos[i] = etat
    elif nom == "bollinger":
        milieu, _haute, basse = ind.bollinger(c, int(p["periode"]), float(p["ecarts"]))
        etat = 0.0
        for i in range(n):
            if not np.isnan(basse[i]):
                if etat == 0.0 and c[i] < basse[i]:
                    etat = 1.0
                elif etat == 1.0 and c[i] > milieu[i]:
                    etat = 0.0
            pos[i] = etat
    return pos


def _rendement(p1: float, p0: float) -> float:
    return (p1 - p0) / abs(p0) if p0 else 0.0


def simuler(df: pd.DataFrame, positions: np.ndarray, cout_bps: float, debut: int = 0
            ) -> tuple[np.ndarray, int, np.ndarray, np.ndarray]:
    """Rendements journaliers nets de la stratégie à partir de l'indice `debut` (>= 1), nombre d'entrées en position, et pour
    chaque jour la position visée (`cibles`) et la position gardée la veille (`detenues`).
    `positions[i]` est la cible décidée à la clôture du jour i, appliquée à l'ouverture du jour i+1. On part en liquidités."""
    o, c = df["open"].to_numpy(dtype=float), df["close"].to_numpy(dtype=float)
    n = len(c)
    m = max(n - debut, 0)
    rend, cibles, detenues = np.zeros(m), np.zeros(m), np.zeros(m)
    detenue, entrees = 0.0, 0
    for k, i in enumerate(range(debut, n)):
        cible = float(positions[i - 1])
        nuit = detenue * _rendement(o[i], c[i - 1])
        seance = cible * _rendement(c[i], o[i])
        frais = abs(cible - detenue) * cout_bps / 1e4
        if cible > detenue:
            entrees += 1
        rend[k] = max((1 + nuit) * (1 + seance) - 1 - frais, -1.0)      # on ne perd pas plus que ce qu'on a investi
        cibles[k], detenues[k] = cible, detenue
        detenue = cible
    return rend, entrees, cibles, detenues


def _trades(rend: np.ndarray, cibles: np.ndarray, detenues: np.ndarray) -> list[float]:
    """Rendement de chaque aller-retour (de l'achat à la vente), pour le taux de réussite. Frais compris."""
    sorties, courant = [], None
    for r, cible, detenue in zip(rend, cibles, detenues):
        if cible > 0 and detenue == 0:                       # une entrée : on ferme d'abord un éventuel trade resté ouvert
            if courant is not None:
                sorties.append(courant - 1)
            courant = 1 + r
        elif cible > 0 or detenue > 0:
            courant = (1 + r) if courant is None else courant * (1 + r)
            if cible == 0:                                   # la sortie a lieu ce jour-là : le trade est terminé
                sorties.append(courant - 1)
                courant = None
    if courant is not None:
        sorties.append(courant - 1)
    return sorties


def metriques(rend: np.ndarray, dates: pd.DatetimeIndex, cibles: np.ndarray | None = None,
              detenues: np.ndarray | None = None) -> dict:
    """Indicateurs de performance et de risque d'une série de rendements journaliers (taux sans risque nul)."""
    n = len(rend)
    vide = {"jours": n, "rendement_total": None, "rendement_annuel": None, "volatilite": None, "sharpe": None, "sortino": None,
            "drawdown_max": None, "calmar": None, "taux_reussite": None, "temps_investi": None, "aller_retours": 0}
    if n < 2:
        return vide
    cibles = np.ones(n) if cibles is None else cibles
    detenues = np.concatenate([[0.0], cibles[:-1]]) if detenues is None else detenues
    equity = np.cumprod(1 + rend)
    ans = max((dates[-1] - dates[0]).days / JOURS_AN, 1e-9)
    total = float(equity[-1] - 1)
    annuel = float(equity[-1] ** (1 / ans) - 1) if equity[-1] > 0 else -1.0
    pas_par_an = n / ans
    vol = float(np.std(rend, ddof=1) * math.sqrt(pas_par_an))
    baisse = np.minimum(rend, 0.0)
    semi = float(math.sqrt(np.mean(baisse ** 2)) * math.sqrt(pas_par_an))
    sommets = np.maximum.accumulate(np.concatenate([[1.0], equity]))[1:]
    dd = float(np.max(1 - equity / sommets))
    trades = _trades(rend, cibles, detenues)
    return {
        "jours": n, "rendement_total": total, "rendement_annuel": annuel, "volatilite": vol,
        "sharpe": annuel / vol if vol > 1e-12 else None, "sortino": annuel / semi if semi > 1e-12 else None,
        "drawdown_max": dd, "calmar": annuel / dd if dd > 1e-12 else None,
        "taux_reussite": (sum(1 for t in trades if t > 0) / len(trades)) if trades else None,
        "temps_investi": float(np.mean(cibles > 0)), "aller_retours": len(trades),
    }


def executer(df: pd.DataFrame, nom: str, params: dict[str, float] | None, cout_bps: float, debut: pd.Timestamp | None = None) -> dict:
    """Backtest d'une stratégie sur `df` (bougies terminées). Retourne métriques (période entière et chaque moitié) et courbe."""
    if len(df) < 30:
        raise ValueError("historique trop court pour un backtest (moins de 30 séances)")
    pos = signaux(nom, params or {}, df)
    i0 = int(df.index.searchsorted(debut)) if debut is not None else 1
    i0 = min(max(i0, 1), len(df) - 2)
    rend, entrees, cibles, detenues = simuler(df, pos, cout_bps, i0)
    dates = df.index[i0:]
    milieu = len(rend) // 2
    equity = np.cumprod(1 + rend)
    pas = max(1, len(equity) // 1500)                                                  # courbe allégée pour l'affichage
    return {
        "metriques": metriques(rend, dates, cibles, detenues),
        "premiere_moitie": metriques(rend[:milieu], dates[:milieu], cibles[:milieu], detenues[:milieu]),
        "seconde_moitie": metriques(rend[milieu:], dates[milieu:], cibles[milieu:], detenues[milieu:]),
        "courbe": {"dates": [d.date().isoformat() for d in dates[::pas]], "valeurs": [float(v) for v in equity[::pas]]},
        "entrees": entrees,
        "signal_actuel": float(pos[-1]),
    }
