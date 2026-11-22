"""Lecture d'un actif : ce que disent les indicateurs aujourd'hui, et si ce signal a vraiment servi sur cet actif. Fonctions pures.

Pour chaque indicateur, on regarde son état à la dernière séance terminée, puis toutes les séances passées où il était dans le
même état : le prix était-il plus haut HORIZON séances plus tard, plus souvent que d'habitude ?
    marge = 1,96 × √(p × (1 − p) / n_indépendantes), avec n_indépendantes = séances du même état / HORIZON (elles se chevauchent)
Écart inférieur à la marge : « dans le bruit ». Tout est calculé sur des séances terminées, avant la date simulée.

Le sentiment vient du ton quotidien de la presse (GDELT). Même test : après les jours de presse la plus négative (20 % les plus bas),
le prix monte-t-il moins souvent sur 5 séances ?
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .indicateurs import bollinger, macd, rsi, sma

HORIZON = 20
HORIZON_SENTIMENT = 5
MIN_OBSERVATIONS = 30
POINTS_GRAPHIQUE = 120


def _test(etats: np.ndarray, futur: np.ndarray, actuel: str, horizon: int) -> dict:
    valide = ~np.isnan(futur) & (etats != "")
    hausse = futur[valide] > 0
    if valide.sum() < MIN_OBSERVATIONS:
        return {"n": int(valide.sum()), "verdict": "trop_peu"}
    p0 = float(hausse.mean())
    meme = valide & (etats == actuel)
    n = int(meme.sum())
    if n < MIN_OBSERVATIONS:
        return {"n": n, "base": p0, "verdict": "trop_peu"}
    p = float((futur[meme] > 0).mean())
    marge = 1.96 * math.sqrt(p0 * (1 - p0) / max(1.0, n / horizon))
    verdict = "bruit" if abs(p - p0) <= marge else "plus_souvent_hausse" if p > p0 else "plus_souvent_baisse"
    return {"n": n, "n_independantes": round(n / horizon, 1), "taux": p, "base": p0, "marge": marge,
            "moyenne": float(np.mean(futur[meme])), "moyenne_base": float(np.mean(futur[valide])), "verdict": verdict}


def _futur(c: np.ndarray, h: int) -> np.ndarray:
    f = np.full(len(c), np.nan)
    if len(c) > h:
        avant, apres = c[:-h], c[h:]
        ok = (avant > 0) & (apres > 0)                    # le WTI négatif d'avril 2020 n'a pas de rendement
        f[:-h] = np.where(ok, apres / np.where(ok, avant, 1) - 1, np.nan)
    return f


def lire(df: pd.DataFrame) -> dict:
    """`df` : séances terminées (open, high, low, close, volume), la plus récente en dernier."""
    c = df["close"].to_numpy(dtype=float)
    n = len(c)
    if n < 220:
        raise ValueError(f"Il faut au moins 220 séances d'historique, cet actif en a {n}.")
    futur = _futur(c, HORIZON)
    s50, s200, r = sma(c, 50), sma(c, 200), rsi(c, 14)
    ligne, signal, _ = macd(c)
    _, haute, basse = bollinger(c, 20, 2.0)
    v = df["volume"].to_numpy(dtype=float) if "volume" in df else np.full(n, np.nan)
    v20 = pd.Series(v).rolling(20).mean().shift(1).to_numpy()

    def etat(cond_ok, choix):
        return np.where(cond_ok, choix, "")

    familles = [
        ("tendance", "Tendance longue", "Prix et moyenne des 200 dernières séances",
         etat(~np.isnan(s200), np.where(c > s200, "au-dessus", "en dessous")),
         {"au-dessus": "Le prix est au-dessus de sa moyenne de 200 séances : la tendance longue monte.",
          "en dessous": "Le prix est sous sa moyenne de 200 séances : la tendance longue baisse."},
         lambda i: {"prix": c[i], "moyenne_200": s200[i]}),
        ("croisement", "Moyennes 50 et 200", "Moyenne des 50 dernières séances contre celle des 200",
         etat(~np.isnan(s200) & ~np.isnan(s50), np.where(s50 > s200, "50 au-dessus", "50 en dessous")),
         {"50 au-dessus": "La moyenne courte est au-dessus de la longue : le mouvement récent est plus fort que le long terme.",
          "50 en dessous": "La moyenne courte est sous la longue : le mouvement récent faiblit."},
         lambda i: {"moyenne_50": s50[i], "moyenne_200": s200[i]}),
        ("rsi", "RSI 14", "Force des hausses contre les baisses, de 0 à 100",
         etat(~np.isnan(r), np.where(r < 30, "survente", np.where(r > 70, "surachat", "neutre"))),
         {"survente": "RSI sous 30 : les baisses récentes ont dominé (« survente »).",
          "surachat": "RSI au-dessus de 70 : les hausses récentes ont dominé (« surachat »).",
          "neutre": "RSI entre 30 et 70 : ni excès de hausse, ni excès de baisse."},
         lambda i: {"rsi": r[i]}),
        ("macd", "MACD", "Écart de deux moyennes exponentielles (12 et 26) contre sa moyenne (9)",
         etat(~np.isnan(signal), np.where(ligne > signal, "élan haussier", "élan baissier")),
         {"élan haussier": "Le MACD est au-dessus de sa ligne de signal : le mouvement accélère vers le haut.",
          "élan baissier": "Le MACD est sous sa ligne de signal : le mouvement accélère vers le bas."},
         lambda i: {"macd": ligne[i], "signal": signal[i]}),
        ("bollinger", "Bandes de Bollinger", "Moyenne de 20 séances plus ou moins deux écarts-types",
         etat(~np.isnan(haute), np.where(c > haute, "au-dessus", np.where(c < basse, "en dessous", "dedans"))),
         {"au-dessus": "Le prix sort par le haut des bandes : mouvement inhabituel vers le haut.",
          "en dessous": "Le prix sort par le bas des bandes : mouvement inhabituel vers le bas.",
          "dedans": "Le prix reste dans ses bandes : agitation habituelle."},
         lambda i: {"bande_haute": haute[i], "bande_basse": basse[i], "prix": c[i]}),
    ]
    if np.isfinite(v[-1]) and np.isfinite(v20[-1]) and v20[-1] > 0:
        familles.append(("volume", "Volume", "Volume de la séance contre la moyenne des 20 précédentes",
                         etat(np.isfinite(v20) & (v20 > 0), np.where(v > 1.5 * np.where(v20 > 0, v20, 1), "élevé", "habituel")),
                         {"élevé": "Le volume dépasse de moitié sa moyenne : beaucoup d'échanges.",
                          "habituel": "Le volume est dans ses habitudes."},
                         lambda i: {"volume": v[i], "volume_moyen_20": v20[i]}))

    signaux = []
    for cle, nom, mesure, etats, phrases, valeurs in familles:
        actuel = str(etats[-1])
        if not actuel:
            continue
        signaux.append({"cle": cle, "nom": nom, "mesure": mesure, "etat": actuel, "phrase": phrases[actuel],
                        "valeurs": {k: float(x) for k, x in valeurs(n - 1).items()}, "test": _test(etats, futur, actuel, HORIZON)})
    fenetre = c[-60:]
    k = min(n, POINTS_GRAPHIQUE)
    propre = lambda x: [None if not np.isfinite(y) else round(float(y), 6) for y in x[-k:]]
    courbes = {"dates": [d.date().isoformat() for d in df.index[-k:]], "prix": propre(c), "moyenne_50": propre(s50),
               "moyenne_200": propre(s200), "bande_haute": propre(haute), "bande_basse": propre(basse), "rsi": propre(r),
               "macd": propre(ligne), "signal": propre(signal), "volume": propre(v), "volume_moyen_20": propre(v20)}
    return {"courbes": courbes, "date": df.index[-1].date().isoformat(), "seances": n, "premiere": df.index[0].date().isoformat(), "horizon": HORIZON,
            "prix": float(c[-1]), "plus_bas_60": float(fenetre.min()), "plus_haut_60": float(fenetre.max()), "signaux": signaux}


def sentiment(df: pd.DataFrame, tons: pd.Series, jours_graphique: int = 250) -> dict:
    """`tons` : ton GDELT par jour (index date), déjà limité au passé. Le ton d'un jour est comparé au rendement des 5 séances suivantes."""
    if tons.empty:
        raise ValueError("Pas de ton de presse pour cet actif.")
    c = df["close"].astype(float)
    jours = pd.Index(pd.to_datetime(c.index).normalize())
    prix = pd.Series(c.to_numpy(), index=jours)
    tons = tons.sort_index()
    ton_seance = tons.reindex(jours).to_numpy(dtype=float)
    futur = _futur(prix.to_numpy(), HORIZON_SENTIMENT)
    ok = ~np.isnan(ton_seance) & ~np.isnan(futur)
    test: dict = {"n": int(ok.sum()), "verdict": "trop_peu"}
    if ok.sum() >= 5 * MIN_OBSERVATIONS:
        seuil = float(np.quantile(ton_seance[ok], 0.2))
        etats = np.where(np.isnan(ton_seance), "", np.where(ton_seance <= seuil, "negatif", "autre"))
        test = {**_test(etats, futur, "negatif", HORIZON_SENTIMENT), "seuil": seuil,
                "correlation": float(np.corrcoef(ton_seance[ok], futur[ok])[0, 1])}
    recents = tons.iloc[-7:]
    annee = tons.loc[tons.index[-1] - pd.Timedelta(days=365):]
    graphique = tons.iloc[-jours_graphique:]
    prix_graphique = prix.loc[graphique.index[0]:]
    return {"dernier_jour": tons.index[-1].date().isoformat(), "premier_jour": tons.index[0].date().isoformat(), "jours": int(len(tons)),
            "ton_7_jours": float(recents.mean()), "ton_annee": float(annee.mean()), "ecart_type_annee": float(annee.std()),
            "test": test, "horizon": HORIZON_SENTIMENT,
            "serie": [{"date": d.date().isoformat(), "ton": round(float(x), 3)} for d, x in graphique.items()],
            "prix": [{"date": d.date().isoformat(), "close": round(float(x), 4)} for d, x in prix_graphique.items()]}
