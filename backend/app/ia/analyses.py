"""Analyses par apprentissage automatique sur les PRIX PASSÉS d'un actif (jamais au-delà de la date simulée de l'utilisateur).

Quatre outils, tous évalués honnêtement :
 - prédiction : le sens de la prochaine séance, évalué en « marche avant » (le modèle n'apprend jamais sur ce qu'il prédit) et comparé à deux références naïves ;
 - anomalies : jours dont le rendement ou le volume sort nettement de l'ordinaire (score robuste, médiane et MAD) ;
 - régimes : trois états de marché (calme, haussier, agité ou baissier) découverts par un mélange gaussien sur rendement et volatilité ;
 - optimiseur : poids de portefeuille à variance minimale et à parité de risque, avec la contribution de chaque position au risque ;
 - agent : un apprentissage par renforcement tabulaire (Q-learning) entraîné sur le passé ancien et jugé uniquement sur la période la plus récente.
Sur des prix journaliers, battre le hasard est difficile : les résultats sont donnés avec leur marge d'erreur, et un résultat dans le bruit est dit tel quel."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..analyse import backtest as bt
from ..analyse import indicateurs as ind

CARACTERISTIQUES = ["rend_1j", "rend_5j", "rend_20j", "vol_20j", "rsi_14", "ecart_sma_50", "ratio_volume"]
LIBELLES = {"rend_1j": "Rendement de la veille", "rend_5j": "Rendement sur 5 jours", "rend_20j": "Rendement sur 20 jours", "vol_20j": "Volatilité sur 20 jours",
            "rsi_14": "RSI (14 jours)", "ecart_sma_50": "Écart à la moyenne mobile à 50 jours", "ratio_volume": "Volume par rapport à sa moyenne"}


def _sklearn():
    try:
        import sklearn  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("scikit-learn n'est pas installé : lancez « pip install -r requirements-ia.txt » dans backend.") from exc


def rendements(c: pd.Series) -> pd.Series:
    """Rendement relatif sur la valeur absolue du prix précédent (le pétrole a eu un prix négatif)."""
    return (c - c.shift(1)) / c.shift(1).abs()


def caracteristiques(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"].astype(float)
    r = rendements(c)
    f = pd.DataFrame(index=df.index)
    f["rend_1j"] = r
    f["rend_5j"] = (c - c.shift(5)) / c.shift(5).abs()
    f["rend_20j"] = (c - c.shift(20)) / c.shift(20).abs()
    f["vol_20j"] = r.rolling(20).std()
    f["rsi_14"] = pd.Series(ind.rsi(c.to_numpy(), 14), index=df.index) / 100.0
    sma = pd.Series(ind.sma(c.to_numpy(), 50), index=df.index)
    f["ecart_sma_50"] = (c - sma) / sma.abs()
    v = df["volume"].astype(float)
    moy = v.rolling(20).mean()
    f["ratio_volume"] = np.where(moy > 0, v / moy, 1.0)
    return f.replace([np.inf, -np.inf], np.nan)


# ------------------------------------------------------------------ prédiction du sens de la prochaine séance
def predire(df: pd.DataFrame, pas: int = 21, depart: int = 250) -> dict:
    """Marche avant : tous les `pas` jours, le modèle est ré-entraîné sur le passé seulement, puis prédit les jours suivants.
    Cible : la prochaine séance est-elle haussière (clôture suivante > clôture du jour) ?"""
    _sklearn()
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    f = caracteristiques(df)
    c = df["close"].astype(float)
    y = (c.shift(-1) > c).astype(float)
    y[c.shift(-1).isna()] = np.nan
    donnees = f.assign(y=y).dropna(subset=CARACTERISTIQUES)
    if len(donnees) < depart + 2 * pas:
        raise ValueError(f"Pas assez d'historique : il faut au moins {depart + 2 * pas} séances avec indicateurs, vous en avez {len(donnees)}.")
    X, cible = donnees[CARACTERISTIQUES].to_numpy(), donnees["y"].to_numpy()
    n = len(donnees)
    # la dernière ligne n'a pas de cible (le futur est inconnu) : elle sert à la prédiction du jour
    n_connu = int(np.sum(~np.isnan(cible)))
    ok = {"logistique": [], "boost": [], "toujours_hausse": [], "veille": []}
    vrai = []
    i = depart
    while i < n_connu:
        j = min(i + pas, n_connu)
        sc = StandardScaler().fit(X[:i])
        lr = LogisticRegression(max_iter=500).fit(sc.transform(X[:i]), cible[:i])
        gb = GradientBoostingClassifier(n_estimators=60, max_depth=2, random_state=0).fit(X[:i], cible[:i])
        ok["logistique"] += list(lr.predict(sc.transform(X[i:j])))
        ok["boost"] += list(gb.predict(X[i:j]))
        ok["toujours_hausse"] += [1.0] * (j - i)
        ok["veille"] += list((X[i:j, 0] > 0).astype(float))                    # « demain fera comme hier »
        vrai += list(cible[i:j])
        i = j
    vrai_a = np.array(vrai)
    noms = {"logistique": "Régression logistique", "boost": "Arbres boostés", "toujours_hausse": "Référence : toujours « hausse »", "veille": "Référence : « comme la veille »"}
    resultats = []
    nt = len(vrai_a)
    for cle, p in ok.items():
        acc = float(np.mean(np.array(p) == vrai_a))
        marge = 1.96 * math.sqrt(acc * (1 - acc) / nt)
        resultats.append({"cle": cle, "nom": noms[cle], "precision": acc, "marge": marge})
    base = max(r["precision"] for r in resultats if r["cle"] in ("toujours_hausse", "veille"))
    meilleur = max((r for r in resultats if r["cle"] in ("logistique", "boost")), key=lambda r: r["precision"])
    dans_le_bruit = meilleur["precision"] - base < meilleur["marge"] + 0.0
    # prédiction pour la prochaine séance, modèle ré-entraîné sur tout le passé connu
    sc = StandardScaler().fit(X[:n_connu])
    lr = LogisticRegression(max_iter=500).fit(sc.transform(X[:n_connu]), cible[:n_connu])
    x_now = f[CARACTERISTIQUES].iloc[[-1]].to_numpy()
    if np.isnan(x_now).any():
        raise ValueError("Les indicateurs de la dernière séance ne sont pas disponibles.")
    z = sc.transform(x_now)[0]
    contribs = [{"variable": v, "libelle": LIBELLES[v], "valeur": float(x_now[0, k]), "contribution": float(lr.coef_[0][k] * z[k])} for k, v in enumerate(CARACTERISTIQUES)]
    contribs.sort(key=lambda d: -abs(d["contribution"]))
    logit = float(lr.intercept_[0] + sum(c["contribution"] for c in contribs))
    return {"n_test": nt, "resultats": resultats, "reference_max": base, "meilleur": meilleur["cle"], "dans_le_bruit": bool(dans_le_bruit),
            "proba_hausse": 1 / (1 + math.exp(-logit)), "contributions": contribs, "intercept": float(lr.intercept_[0]), "dernier_jour": df.index[-1].date().isoformat(),
            "conclusion": ("Le meilleur modèle ne fait pas mieux que la meilleure référence au-delà de la marge d'erreur : en pratique, il ne prédit pas mieux que le hasard." if dans_le_bruit else
                           "Le meilleur modèle dépasse la meilleure référence au-delà de la marge d'erreur sur cette période. Cela ne garantit rien pour la suite, surtout après frais.")}


# ------------------------------------------------------------------ anomalies
def anomalies(df: pd.DataFrame, fenetre: int = 250, seuil: float = 4.0, limite: int = 15) -> dict:
    """Score robuste : écart à la médiane divisé par 1,4826 × MAD (équivalent d'un écart-type insensible aux extrêmes). Seuil de 4."""
    d = df.tail(fenetre + 1)
    if len(d) < 60:
        raise ValueError("Pas assez d'historique (au moins 60 séances).")
    r = rendements(d["close"].astype(float)).dropna()
    v = np.log1p(d["volume"].astype(float).clip(lower=0)).loc[r.index]

    def robuste(x: pd.Series) -> pd.Series:
        med = x.median()
        mad = (x - med).abs().median() * 1.4826
        return (x - med) / mad if mad > 0 else x * 0.0

    zr, zv = robuste(r), robuste(v)
    lignes = []
    for jour in r.index:
        if abs(zr[jour]) >= seuil or zv[jour] >= seuil:
            lignes.append({"jour": jour.date().isoformat(), "rendement": float(r[jour]), "score_rendement": float(zr[jour]), "score_volume": float(zv[jour]),
                           "type": "rendement et volume" if abs(zr[jour]) >= seuil and zv[jour] >= seuil else "rendement" if abs(zr[jour]) >= seuil else "volume"})
    lignes.sort(key=lambda x: -max(abs(x["score_rendement"]), x["score_volume"]))
    return {"fenetre": len(r), "seuil": seuil, "nb": len(lignes), "anomalies": lignes[:limite],
            "note": "Une anomalie n'est ni une erreur ni un signal d'achat : c'est un jour inhabituel par rapport à l'année écoulée, qui mérite qu'on cherche pourquoi (annonce, crise, donnée aberrante)."}


# ------------------------------------------------------------------ régimes de marché
def regimes(df: pd.DataFrame, k: int = 3) -> dict:
    _sklearn()
    from sklearn.mixture import GaussianMixture

    c = df["close"].astype(float)
    r = rendements(c)
    X = pd.DataFrame({"rend": r.rolling(20).mean() * 252, "vol": r.rolling(20).std() * math.sqrt(252)}).dropna()
    if len(X) < 120:
        raise ValueError("Pas assez d'historique (au moins 140 séances).")
    mu, sd = X.mean(), X.std().replace(0, 1.0)
    gm = GaussianMixture(k, covariance_type="full", random_state=0, n_init=3).fit((X - mu) / sd)
    etiq = gm.predict((X - mu) / sd)
    stats = pd.DataFrame({"e": etiq, "rend": X["rend"].to_numpy(), "vol": X["vol"].to_numpy()}).groupby("e").mean()
    agite = int(stats["vol"].idxmax())
    reste = [e for e in stats.index if e != agite]
    haussier = int(stats.loc[reste, "rend"].idxmax())
    noms = {agite: "Agité", haussier: "Haussier calme", **{e: "Baissier ou atone" for e in reste if e != haussier}}
    serie = pd.Series([noms[e] for e in etiq], index=X.index)
    actuel = serie.iloc[-1]
    duree = 1
    while duree < len(serie) and serie.iloc[-1 - duree] == actuel:
        duree += 1
    resume = [{"regime": nom, "part": float((serie == nom).mean()), "rendement_annualise": float(stats.loc[e, "rend"]), "volatilite_annualisee": float(stats.loc[e, "vol"])}
              for e, nom in noms.items()]
    resume.sort(key=lambda x: -x["volatilite_annualisee"])
    return {"regime_actuel": actuel, "depuis_jours": duree, "regimes": resume, "dernier_jour": X.index[-1].date().isoformat(),
            "note": "Les régimes sont découverts par la machine à partir du rendement et de la volatilité des 20 derniers jours ; les noms sont donnés après coup selon leurs moyennes. Ils décrivent le passé récent et ne prédisent pas le suivant."}


# ------------------------------------------------------------------ optimiseur de portefeuille
def optimiser(retours: pd.DataFrame, poids_actuels: dict[str, float]) -> dict:
    """Poids à variance minimale (long seulement) et à parité de risque, et contribution actuelle de chaque position au risque."""
    from scipy.optimize import minimize

    r = retours.dropna()
    if r.shape[1] < 2:
        raise ValueError("Il faut au moins deux positions pour comparer des répartitions.")
    if len(r) < 60:
        raise ValueError("Pas assez d'historique commun (au moins 60 séances).")
    noms = list(r.columns)
    cov = r.cov().to_numpy() * 252
    n = len(noms)
    x0 = np.full(n, 1 / n)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    bornes = [(0.0, 1.0)] * n
    vmin = minimize(lambda w: w @ cov @ w, x0, bounds=bornes, constraints=cons, method="SLSQP").x

    def ecart_parite(w):
        rc = w * (cov @ w)
        return float(np.sum((rc / max(rc.sum(), 1e-12) - 1 / n) ** 2))
    parite = minimize(ecart_parite, x0, bounds=[(1e-4, 1.0)] * n, constraints=cons, method="SLSQP", options={"maxiter": 300}).x
    w0 = np.array([poids_actuels.get(s, 0.0) for s in noms])
    w0 = w0 / w0.sum() if w0.sum() > 0 else x0
    vol = lambda w: float(math.sqrt(max(w @ cov @ w, 0.0)))
    rc = w0 * (cov @ w0)
    rc = rc / rc.sum() if rc.sum() > 0 else rc
    lignes = [{"symbole": s, "poids_actuel": float(w0[i]), "contribution_risque": float(rc[i]), "poids_variance_minimale": float(vmin[i]), "poids_parite_risque": float(parite[i])} for i, s in enumerate(noms)]
    lignes.sort(key=lambda x: -x["contribution_risque"])
    plus = lignes[0]
    return {"lignes": lignes, "volatilite_actuelle": vol(w0), "volatilite_variance_minimale": vol(vmin), "volatilite_parite_risque": vol(parite), "jours": len(r),
            "recommandations": [f"{plus['symbole']} représente {plus['poids_actuel']:.0%} du portefeuille mais {plus['contribution_risque']:.0%} du risque."
                                if plus["contribution_risque"] > plus["poids_actuel"] + 0.05 else "Aucune position ne pèse de façon disproportionnée dans le risque.",
                                f"La parité de risque ramènerait la volatilité annualisée de {vol(w0):.1%} à {vol(parite):.1%}, la variance minimale à {vol(vmin):.1%} (estimations sur le passé)."],
            "note": "Calculs sur le passé récent des positions détenues : les corrélations changent, notamment pendant les crises. Ce n'est pas un conseil d'investissement."}


# ------------------------------------------------------------------ agent de trading par renforcement
def _etat(rsi: float, ecart: float) -> int:
    r = 0 if rsi < 0.35 else 1 if rsi < 0.65 else 2
    t = 0 if ecart < -0.02 else 1 if ecart < 0.02 else 2
    return r * 3 + t


def agent(df: pd.DataFrame, cout_bps: float = 7.5, passages: int = 40, graine: int = 0, part_test: float = 0.3) -> dict:
    """Q-learning tabulaire : état = (RSI en 3 classes) × (écart à la moyenne à 50 jours en 3 classes) × position détenue ; actions : rester hors marché ou investi.
    Récompense : rendement de la séance suivante si investi, moins le coût d'un changement de position. Entraîné sur 70 % de l'historique le plus ancien,
    jugé sur les 30 % les plus récents seulement (la table n'y est plus modifiée)."""
    f = caracteristiques(df)
    c = df["close"].astype(float)
    suivant = ((c.shift(-1) - c) / c.abs()).to_numpy()
    d = pd.DataFrame({"rsi": f["rsi_14"], "ecart": f["ecart_sma_50"]}).assign(r=suivant, idx=np.arange(len(df)))
    d = d.dropna()
    d = d.iloc[:-1] if len(d) and np.isnan(suivant[-1]) else d
    if len(d) < 300:
        raise ValueError("Pas assez d'historique (au moins 300 séances avec indicateurs).")
    coupe = int(len(d) * (1 - part_test))
    apprentissage, test = d.iloc[:coupe], d.iloc[coupe:]
    etats = lambda x: [_etat(a, b) for a, b in zip(x["rsi"], x["ecart"])]
    sa, st = etats(apprentissage), etats(test)
    cout = cout_bps / 1e4
    rng = np.random.default_rng(graine)
    Q = np.zeros((9, 2, 2))                                # [état, position détenue, action]
    for p in range(passages):
        eps = max(0.05, 0.5 * (1 - p / passages))
        pos = 0
        for i in range(len(sa) - 1):
            a = int(rng.integers(2)) if rng.random() < eps else int(np.argmax(Q[sa[i], pos]))
            rec = (apprentissage["r"].iloc[i] if a == 1 else 0.0) - (cout if a != pos else 0.0)
            Q[sa[i], pos, a] += 0.1 * (rec + 0.95 * Q[sa[i + 1], a].max() - Q[sa[i], pos, a])
            pos = a
    pos, rend, cibles, detenues = 0, [], [], []
    for s, r in zip(st, test["r"]):
        a = int(np.argmax(Q[s, pos]))
        rend.append((r if a == 1 else 0.0) - (cout if a != pos else 0.0))
        detenues.append(pos); cibles.append(a)
        pos = a
    rend = np.array(rend)
    dates = df.index[test["idx"].astype(int).to_numpy()]
    m_agent = bt.metriques(rend, pd.DatetimeIndex(dates), np.array(cibles, dtype=float), np.array(detenues, dtype=float))
    m_ref = bt.metriques(test["r"].to_numpy(), pd.DatetimeIndex(dates), np.ones(len(test)), np.concatenate([[0.0], np.ones(len(test) - 1)]))
    noms_etats = ["RSI bas", "RSI moyen", "RSI haut"]
    noms_t = ["sous la moyenne", "près de la moyenne", "au-dessus de la moyenne"]
    politique = [{"etat": f"{noms_etats[e // 3]}, prix {noms_t[e % 3]}", "hors_marche": "investir" if Q[e, 0].argmax() == 1 else "rester dehors",
                  "investi": "rester investi" if Q[e, 1].argmax() == 1 else "sortir"} for e in range(9)]
    return {"entrainement": {"debut": df.index[int(apprentissage["idx"].iloc[0])].date().isoformat(), "fin": df.index[int(apprentissage["idx"].iloc[-1])].date().isoformat(), "jours": len(apprentissage)},
            "test": {"debut": dates[0].date().isoformat(), "fin": dates[-1].date().isoformat(), "jours": len(test)}, "agent": m_agent, "achat_conservation": m_ref,
            "politique": politique, "cout_bps": cout_bps,
            "note": "L'agent n'a jamais vu la période de test pendant son entraînement. Un apprentissage par renforcement sur des prix journaliers est fragile : le résultat dépend du hasard de l'entraînement, des 9 états retenus et de la période. À comparer, pas à croire."}
