"""Probabilité de défaut (PD) d'un emprunteur particulier par régression logistique, avec contributions locales exactes.

Jeu de données prévu : « Give Me Some Credit » (cs-training.csv, Kaggle) : 150 000 emprunteurs, cible SeriousDlqin2yrs
(retard de paiement grave dans les deux ans). C'est du crédit aux **particuliers** : ce n'est pas la PD d'une entreprise.
Sans ce fichier, un échantillon **synthétique** (tirage au hasard à partir d'une loi connue) permet de faire tourner la chaîne : il est étiqueté comme tel.
Explicabilité : dans une régression logistique, le logit (log des chances) est une somme exacte, donc chaque variable contribue
« coefficient × valeur centrée-réduite » : la contribution locale est exacte, pas approchée."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

CIBLE = "SeriousDlqin2yrs"
VARIABLES = {
    "RevolvingUtilizationOfUnsecuredLines": ("Utilisation des crédits renouvelables", "Part du plafond de crédit utilisée (0,3 = 30 %)"),
    "age": ("Âge", "En années"),
    "NumberOfTime30-59DaysPastDueNotWorse": ("Retards de 30 à 59 jours", "Nombre de fois"),
    "DebtRatio": ("Taux d'endettement", "Dettes mensuelles / revenu mensuel"),
    "MonthlyIncome": ("Revenu mensuel", "En dollars"),
    "NumberOfOpenCreditLinesAndLoans": ("Crédits ouverts", "Nombre"),
    "NumberOfTimes90DaysLate": ("Retards de 90 jours ou plus", "Nombre de fois"),
    "NumberRealEstateLoansOrLines": ("Prêts immobiliers", "Nombre"),
    "NumberOfTime60-89DaysPastDueNotWorse": ("Retards de 60 à 89 jours", "Nombre de fois"),
    "NumberOfDependents": ("Personnes à charge", "Nombre"),
}
NOMS = list(VARIABLES)
BORNES = {"RevolvingUtilizationOfUnsecuredLines": (0, 2), "age": (18, 100), "NumberOfTime30-59DaysPastDueNotWorse": (0, 20),
          "DebtRatio": (0, 5), "MonthlyIncome": (0, 50_000), "NumberOfOpenCreditLinesAndLoans": (0, 40),
          "NumberOfTimes90DaysLate": (0, 20), "NumberRealEstateLoansOrLines": (0, 10),
          "NumberOfTime60-89DaysPastDueNotWorse": (0, 20), "NumberOfDependents": (0, 10)}


COLONNES_RETARDS = ["NumberOfTime30-59DaysPastDueNotWorse", "NumberOfTime60-89DaysPastDueNotWorse", "NumberOfTimes90DaysLate"]


def nettoyer(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoyage documenté : colonnes d'index ou d'identifiant retirées, valeurs manquantes remplacées par la médiane, valeurs extrêmes bornées.
    Les lignes qui portent un code spécial (96 ou 98) dans une colonne de retards sont ÉCARTÉES : ce sont des codes d'erreur et non de vrais nombres de retards
    (183 lignes sur 104 805 dans l'échantillon examiné, dont plus de la moitié en défaut). Les borner à 20 retards faussait le modèle : le coefficient des retards de
    60 à 89 jours devenait négatif. Le nombre de lignes écartées est dans `attrs[\"codes_retires\"]`."""
    df = df.drop(columns=[c for c in df.columns if c.lower().startswith("unnamed")], errors="ignore").copy()
    manque = [c for c in NOMS + [CIBLE] if c not in df.columns]
    if manque:
        raise ValueError(f"Colonnes absentes du fichier : {', '.join(manque)}")
    codes = (df[COLONNES_RETARDS] >= 90).any(axis=1)
    df = df[~codes].copy()
    for c in NOMS:
        df[c] = df[c].fillna(df[c].median()).clip(*BORNES[c])
    df[CIBLE] = df[CIBLE].astype(int)
    sortie = df[NOMS + [CIBLE]]
    sortie.attrs["codes_retires"] = int(codes.sum())
    return sortie


def echantillon_synthetique(n: int = 20_000, graine: int = 7) -> pd.DataFrame:
    """Emprunteurs INVENTÉS à partir d'une loi logistique connue. Sert uniquement à tester la chaîne."""
    rng = np.random.default_rng(graine)
    df = pd.DataFrame({
        "RevolvingUtilizationOfUnsecuredLines": np.clip(rng.beta(1.2, 2.5, n), 0, 2),
        "age": np.clip(rng.normal(50, 14, n), 21, 95).round(),
        "NumberOfTime30-59DaysPastDueNotWorse": rng.poisson(0.35, n),
        "DebtRatio": np.clip(rng.lognormal(-1.0, 0.8, n), 0, 5),
        "MonthlyIncome": np.clip(rng.lognormal(8.6, 0.6, n), 500, 50_000).round(),
        "NumberOfOpenCreditLinesAndLoans": rng.poisson(8, n),
        "NumberOfTimes90DaysLate": rng.poisson(0.12, n),
        "NumberRealEstateLoansOrLines": rng.poisson(1.0, n),
        "NumberOfTime60-89DaysPastDueNotWorse": rng.poisson(0.1, n),
        "NumberOfDependents": rng.poisson(0.8, n),
    })
    logit = (-4.3 + 2.0 * df.iloc[:, 0] - 0.025 * (df["age"] - 50) + 0.55 * df["NumberOfTime30-59DaysPastDueNotWorse"]
             + 1.1 * df["NumberOfTimes90DaysLate"] + 0.5 * df["NumberOfTime60-89DaysPastDueNotWorse"] + 0.3 * df["DebtRatio"]
             - 0.00006 * df["MonthlyIncome"] + 0.05 * df["NumberOfDependents"])
    df[CIBLE] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return df


@dataclass
class ModelePD:
    intercept: float
    coefs: dict[str, float]
    moyennes: dict[str, float]
    ecarts: dict[str, float]
    medianes: dict[str, float]
    metriques: dict
    source: str                       # "kaggle" ou "synthetique"
    taux_defaut: float

    def logit(self, valeurs: dict[str, float]) -> tuple[float, list[dict]]:
        contributions = []
        total = self.intercept
        for nom in NOMS:
            v = float(valeurs.get(nom, self.medianes[nom]))
            z = (v - self.moyennes[nom]) / self.ecarts[nom]
            contribution = self.coefs[nom] * z
            total += contribution
            contributions.append({"variable": nom, "libelle": VARIABLES[nom][0], "valeur": v, "contribution": contribution})
        return total, contributions

    def predire(self, valeurs: dict[str, float]) -> dict:
        inconnues = set(valeurs) - set(NOMS)
        if inconnues:
            raise ValueError(f"Variable inconnue : {', '.join(sorted(inconnues))}")
        for nom, v in valeurs.items():
            lo, hi = BORNES[nom]
            if not (isinstance(v, (int, float)) and math.isfinite(v) and lo <= v <= hi):
                raise ValueError(f"« {VARIABLES[nom][0]} » doit être compris entre {lo} et {hi}.")
        logit, contributions = self.logit(valeurs)
        pd_ = 1 / (1 + math.exp(-logit))
        contributions.sort(key=lambda c: -abs(c["contribution"]))
        return {"pd": pd_, "taux_defaut_moyen": self.taux_defaut, "logit": logit, "intercept": self.intercept, "contributions": contributions}

    def en_dict(self) -> dict:
        return {"intercept": self.intercept, "coefs": self.coefs, "moyennes": self.moyennes, "ecarts": self.ecarts, "medianes": self.medianes,
                "metriques": self.metriques, "source": self.source, "taux_defaut": self.taux_defaut}


def entrainer(df: pd.DataFrame, source: str, graine: int = 42) -> ModelePD:
    """Régression logistique sur variables centrées-réduites ; jeu de test de 25 % mis de côté pour les mesures."""
    try:
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import brier_score_loss, roc_auc_score
        from sklearn.model_selection import train_test_split
    except ImportError as exc:
        raise RuntimeError("scikit-learn n'est pas installé : lancez « pip install -r requirements-ia.txt » dans backend.") from exc
    df = nettoyer(df)
    retires = int(df.attrs.get("codes_retires", 0))
    X, y = df[NOMS], df[CIBLE]
    if y.nunique() < 2 or y.sum() < 50:
        raise ValueError("Trop peu de défauts dans le jeu de données pour entraîner un modèle.")
    Xa, Xt, ya, yt = train_test_split(X, y, test_size=0.25, random_state=graine, stratify=y)
    moy, ec = Xa.mean(), Xa.std(ddof=0).replace(0, 1.0)
    lr = LogisticRegression(max_iter=1000).fit((Xa - moy) / ec, ya)
    p = lr.predict_proba((Xt - moy) / ec)[:, 1]
    gb = GradientBoostingClassifier(random_state=graine, n_estimators=100, max_depth=3).fit(Xa, ya)
    p_gb = gb.predict_proba(Xt)[:, 1]
    # calibration : dix groupes de même taille du plus faible au plus fort risque prédit
    groupes = pd.qcut(pd.Series(p).rank(method="first"), 10, labels=False)
    calib = [{"groupe": int(g) + 1, "pd_moyenne": float(p[groupes == g].mean()), "taux_observe": float(yt.to_numpy()[groupes == g].mean())} for g in range(10)]
    metriques = {"auc_logistique": float(roc_auc_score(yt, p)), "auc_arbres_boostes": float(roc_auc_score(yt, p_gb)),
                 "brier": float(brier_score_loss(yt, p)), "brier_reference": float(brier_score_loss(yt, np.full(len(yt), ya.mean()))),
                 "n_apprentissage": int(len(Xa)), "n_test": int(len(Xt)), "lignes_ecartees": retires, "calibration": calib}
    return ModelePD(float(lr.intercept_[0]), dict(zip(NOMS, map(float, lr.coef_[0]))), moy.to_dict(), ec.to_dict(), X.median().to_dict(),
                    metriques, source, float(y.mean()))


def sauvegarder(m: ModelePD, dossier: Path) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "pd_credit.json").write_text(json.dumps(m.en_dict(), ensure_ascii=False, indent=1), encoding="utf-8")


def charger(dossier: Path) -> ModelePD | None:
    chemin = dossier / "pd_credit.json"
    if not chemin.exists():
        return None
    return ModelePD(**json.loads(chemin.read_text(encoding="utf-8")))