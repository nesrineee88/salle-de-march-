"""Tarification d'une assurance auto : fréquence (Poisson avec exposition), coût moyen (Gamma), prime pure, prime commerciale, probabilité de sinistre.

Jeux de données prévus : freMTPL2freq.csv et freMTPL2sev.csv (assurance auto française, Kaggle / OpenML). Sans eux, un échantillon SYNTHÉTIQUE
tiré d'une loi connue permet de faire tourner et de tester la chaîne ; il est étiqueté comme tel.

 - Fréquence : le nombre de sinistres suit une loi de Poisson dont le taux dépend du profil ; la durée d'exposition (en années) est prise en compte
   (régression de la fréquence = sinistres / exposition, pondérée par l'exposition).
 - Coût moyen : montant d'un sinistre, loi Gamma à lien logarithmique.
 - Prime pure = fréquence annuelle × coût moyen. Prime commerciale = prime pure × (1 + marge de sécurité) / (1 − frais).
 - Probabilité d'au moins un sinistre sur l'exposition donnée = 1 − exp(−fréquence × exposition).
Les coefficients sont en échelle logarithmique : exp(coefficient) est un facteur multiplicatif (1,10 = +10 %)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

NUM = ["VehPower", "VehAge", "DrivAge", "BonusMalus", "LogDensity"]
CAT = {"VehGas": ["Diesel", "Regular"], "Area": list("ABCDEF")}
BORNES = {"VehPower": (4, 15), "VehAge": (0, 100), "DrivAge": (18, 100), "BonusMalus": (50, 230), "Density": (1, 30000)}
LIBELLES = {"VehPower": "Puissance du véhicule", "VehAge": "Âge du véhicule (années)", "DrivAge": "Âge du conducteur (années)", "BonusMalus": "Bonus-malus",
            "LogDensity": "Densité de population (log)", "Density": "Densité de population (habitants par km²)", "VehGas": "Carburant", "Area": "Zone (A rurale à F urbaine)"}
REFERENCE = {"VehGas": "Diesel", "Area": "A"}


def nettoyer(freq: pd.DataFrame, sev: pd.DataFrame | None = None) -> pd.DataFrame:
    """Plafonds usuels : sinistres ≤ 4, exposition ≤ 1, puissance ≤ 9 (trop peu de véhicules au-delà), âge du véhicule ≤ 20, âge du conducteur ≤ 90, bonus-malus ≤ 150."""
    manque = [c for c in ["ClaimNb", "Exposure", "VehPower", "VehAge", "DrivAge", "BonusMalus", "VehGas", "Area", "Density"] if c not in freq.columns]
    if manque:
        raise ValueError(f"Colonnes absentes du fichier : {', '.join(manque)}")
    d = freq.copy()
    d["ClaimNb"] = d["ClaimNb"].clip(upper=4)
    d["Exposure"] = d["Exposure"].clip(lower=1 / 365, upper=1.0)
    d["VehPower"] = d["VehPower"].clip(upper=9)
    d["VehAge"] = d["VehAge"].clip(upper=20)
    d["DrivAge"] = d["DrivAge"].clip(upper=90)
    d["BonusMalus"] = d["BonusMalus"].clip(upper=150)
    d["LogDensity"] = np.log(d["Density"].clip(lower=1))
    d["VehGas"] = d["VehGas"].astype(str).str.strip().str.capitalize()
    d["Area"] = d["Area"].astype(str).str.strip().str.upper()
    if sev is not None and "IDpol" in d.columns and {"IDpol", "ClaimAmount"} <= set(sev.columns):
        total = sev.groupby("IDpol")["ClaimAmount"].sum()
        d["ClaimAmount"] = d["IDpol"].map(total).fillna(0.0)
    return d


def echantillon_synthetique(n: int = 30_000, graine: int = 5) -> pd.DataFrame:
    """Contrats et sinistres INVENTÉS à partir d'une loi connue : fréquence et coût moyen dépendent du profil."""
    rng = np.random.default_rng(graine)
    d = pd.DataFrame({
        "IDpol": np.arange(1, n + 1), "Exposure": np.clip(rng.beta(4, 2, n), 0.02, 1.0),
        "VehPower": rng.integers(4, 13, n), "VehAge": np.clip(rng.gamma(2.0, 3.5, n), 0, 30).round(),
        "DrivAge": np.clip(rng.normal(45, 14, n), 18, 95).round(), "BonusMalus": np.clip(rng.gamma(9, 11, n), 50, 200).round(),
        "VehGas": rng.choice(["Diesel", "Regular"], n), "Area": rng.choice(list("ABCDEF"), n, p=[0.1, 0.15, 0.2, 0.25, 0.2, 0.1]),
        "Density": np.clip(rng.lognormal(6.0, 1.6, n), 1, 30000).round(),
    })
    d = nettoyer(d.assign(ClaimNb=0))
    lin = (-2.6 + 0.012 * (d["BonusMalus"] - 100) / 1 - 0.015 * (d["DrivAge"] - 45) + 0.02 * (d["VehPower"] - 7) - 0.01 * d["VehAge"]
           + 0.07 * d["LogDensity"] + 0.12 * (d["VehGas"] == "Regular") + 0.05 * d["Area"].map(lambda a: "ABCDEF".index(a)))
    d["ClaimNb"] = rng.poisson(np.exp(lin) * d["Exposure"])
    cout = np.exp(7.0 + 0.04 * (d["VehPower"] - 7) + 0.05 * (d["DrivAge"] < 25) + 0.03 * d["Area"].map(lambda a: "ABCDEF".index(a)))
    d["ClaimAmount"] = [float(rng.gamma(2.0, c / 2.0, k).sum()) if k > 0 else 0.0 for k, c in zip(d["ClaimNb"], cout)]
    return d


def _matrice(d: pd.DataFrame) -> pd.DataFrame:
    X = d[NUM].astype(float).copy()
    for cat, niveaux in CAT.items():
        for n in niveaux:
            if n != REFERENCE[cat]:
                X[f"{cat}={n}"] = (d[cat] == n).astype(float)
    return X


class ModeleTarif:
    def __init__(self, frequence: dict, severite: dict, moyennes: dict, metriques: dict, source: str):
        self.frequence, self.severite, self.moyennes, self.metriques, self.source = frequence, severite, moyennes, metriques, source

    @staticmethod
    def entrainer(d: pd.DataFrame, source: str, graine: int = 42) -> "ModeleTarif":
        try:
            from sklearn.linear_model import GammaRegressor, PoissonRegressor
            from sklearn.metrics import mean_gamma_deviance, mean_poisson_deviance
            from sklearn.model_selection import train_test_split
        except ImportError as exc:
            raise RuntimeError("scikit-learn n'est pas installé : lancez « pip install -r requirements-ia.txt » dans backend.") from exc
        d = nettoyer(d) if "LogDensity" not in d.columns else d
        if "ClaimAmount" not in d.columns:
            raise ValueError("Les montants de sinistres sont absents (fichier freMTPL2sev.csv).")
        if d["ClaimNb"].sum() < 200:
            raise ValueError("Trop peu de sinistres pour estimer un modèle.")
        a, t = train_test_split(d, test_size=0.25, random_state=graine)
        Xa, Xt = _matrice(a), _matrice(t)
        moy, ec = Xa.mean(), Xa.std(ddof=0).replace(0, 1.0)
        freq = PoissonRegressor(alpha=1e-4, max_iter=500).fit((Xa - moy) / ec, a["ClaimNb"] / a["Exposure"], sample_weight=a["Exposure"])
        pt = freq.predict((Xt - moy) / ec)
        base = float(a["ClaimNb"].sum() / a["Exposure"].sum())
        # coût moyen : un sinistre à la fois (contrats avec au moins un sinistre), montant moyen par sinistre
        sa = a[(a["ClaimNb"] > 0) & (a["ClaimAmount"] > 0)]
        st = t[(t["ClaimNb"] > 0) & (t["ClaimAmount"] > 0)]
        if len(sa) < 100:
            raise ValueError("Trop peu de sinistres avec un montant pour estimer le coût moyen.")
        sev = GammaRegressor(alpha=1e-4, max_iter=500).fit((Xa.loc[sa.index] - moy) / ec, sa["ClaimAmount"] / sa["ClaimNb"], sample_weight=sa["ClaimNb"])
        ps = sev.predict((Xt.loc[st.index] - moy) / ec)
        cible_s = st["ClaimAmount"] / st["ClaimNb"]
        metriques = {
            "deviance_poisson": float(mean_poisson_deviance(t["ClaimNb"] / t["Exposure"], pt, sample_weight=t["Exposure"])),
            "deviance_poisson_reference": float(mean_poisson_deviance(t["ClaimNb"] / t["Exposure"], np.full(len(t), base), sample_weight=t["Exposure"])),
            "deviance_gamma": float(mean_gamma_deviance(cible_s, ps, sample_weight=st["ClaimNb"])),
            "deviance_gamma_reference": float(mean_gamma_deviance(cible_s, np.full(len(st), float((sa["ClaimAmount"].sum() / sa["ClaimNb"].sum()))), sample_weight=st["ClaimNb"])),
            "frequence_moyenne": base, "cout_moyen": float(sa["ClaimAmount"].sum() / sa["ClaimNb"].sum()),
            "n_contrats": int(len(d)), "n_sinistres": int(d["ClaimNb"].sum()),
        }
        coef = lambda m: {"intercept": float(m.intercept_), **dict(zip(Xa.columns, map(float, m.coef_)))}
        return ModeleTarif(coef(freq), coef(sev), {"moy": moy.to_dict(), "ec": ec.to_dict()}, metriques, source)

    def _log(self, params: dict, x: dict) -> tuple[float, list[dict]]:
        total, contribs = params["intercept"], []
        for nom, v in x.items():
            z = (v - self.moyennes["moy"][nom]) / self.moyennes["ec"][nom]
            c = params[nom] * z
            total += c
            contribs.append({"variable": nom, "libelle": _libelle(nom), "valeur": v, "facteur": math.exp(c)})
        return total, contribs

    def prime(self, profil: dict, exposition: float = 1.0, frais: float = 0.20, marge: float = 0.05) -> dict:
        x = profil_vers_x(profil)
        if not 0 < exposition <= 1:
            raise ValueError("L'exposition doit être comprise entre 0 (exclu) et 1 an.")
        if not 0 <= frais < 0.9 or not 0 <= marge <= 1:
            raise ValueError("Les frais doivent être compris entre 0 % et 90 %, la marge de sécurité entre 0 % et 100 %.")
        lf, cf = self._log(self.frequence, x)
        ls, cs = self._log(self.severite, x)
        f, s = math.exp(lf), math.exp(ls)
        pure = f * s * exposition
        return {"frequence_annuelle": f, "cout_moyen": s, "prime_pure": pure, "marge_securite": pure * marge, "frais": pure * (1 + marge) / (1 - frais) * frais,
                "prime_commerciale": pure * (1 + marge) / (1 - frais), "probabilite_sinistre": 1 - math.exp(-f * exposition), "exposition": exposition,
                "facteurs_frequence": sorted(cf, key=lambda c: -abs(math.log(c["facteur"]))), "facteurs_cout": sorted(cs, key=lambda c: -abs(math.log(c["facteur"])))}

    def en_dict(self) -> dict:
        return {"frequence": self.frequence, "severite": self.severite, "moyennes": self.moyennes, "metriques": self.metriques, "source": self.source}


def _libelle(nom: str) -> str:
    if "=" in nom:
        c, n = nom.split("=")
        return f"{LIBELLES[c]} : {n}"
    return LIBELLES.get(nom, nom)


def profil_vers_x(p: dict) -> dict:
    inconnus = set(p) - set(BORNES) - set(CAT)
    if inconnus:
        raise ValueError(f"Variable inconnue : {', '.join(sorted(inconnus))}")
    d = {"VehPower": 7, "VehAge": 5, "DrivAge": 45, "BonusMalus": 100, "Density": 1000, "VehGas": "Diesel", "Area": "C", **p}
    for nom, (lo, hi) in BORNES.items():
        v = d[nom]
        if not (isinstance(v, (int, float)) and math.isfinite(v) and lo <= v <= hi):
            raise ValueError(f"« {LIBELLES.get(nom, nom)} » doit être compris entre {lo} et {hi}.")
    for cat, niveaux in CAT.items():
        if d[cat] not in niveaux:
            raise ValueError(f"« {LIBELLES[cat]} » doit valoir : {', '.join(niveaux)}.")
    x = {"VehPower": min(d["VehPower"], 9), "VehAge": min(d["VehAge"], 20), "DrivAge": min(d["DrivAge"], 90), "BonusMalus": min(d["BonusMalus"], 150), "LogDensity": math.log(max(1.0, d["Density"]))}
    for cat, niveaux in CAT.items():
        for n in niveaux:
            if n != REFERENCE[cat]:
                x[f"{cat}={n}"] = 1.0 if d[cat] == n else 0.0
    return x


def sauvegarder(m: ModeleTarif, dossier: Path) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "tarif_auto.json").write_text(json.dumps(m.en_dict(), ensure_ascii=False, indent=1), encoding="utf-8")


def charger(dossier: Path) -> ModeleTarif | None:
    c = dossier / "tarif_auto.json"
    return ModeleTarif(**json.loads(c.read_text(encoding="utf-8"))) if c.exists() else None


# ------------------------------------------------------------------ provisions : Chain Ladder
def chain_ladder(triangle: list[list[float | None]]) -> dict:
    """Triangle de règlements CUMULÉS : ligne = année de survenance, colonne = année de développement (0 = première).
    Facteur de développement j → j+1 = somme des règlements de la colonne j+1 / somme des règlements de la colonne j, sur les années où les deux sont connus.
    Provision (IBNR + sinistres à régler) = ultime estimé − dernier montant connu."""
    n = len(triangle)
    if n < 3 or any(len(l) != n for l in triangle):
        raise ValueError("Le triangle doit être carré, avec au moins 3 années.")
    t = np.full((n, n), np.nan)
    for i, ligne in enumerate(triangle):
        for j, v in enumerate(ligne):
            if v is None:
                continue
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0):
                raise ValueError("Les règlements doivent être des nombres positifs ou nuls.")
            if j > n - 1 - i:
                raise ValueError("Le triangle inférieur doit rester vide (valeurs futures).")
            t[i, j] = v
    for i in range(n):
        for j in range(n - i):
            if math.isnan(t[i, j]):
                raise ValueError("Le triangle supérieur doit être complet (aucune case vide avant la diagonale).")
        for j in range(1, n - i):
            if t[i, j] < t[i, j - 1] - 1e-9:
                raise ValueError(f"Les règlements cumulés ne peuvent pas diminuer (année {i + 1}).")
    facteurs = []
    for j in range(n - 1):
        lignes = range(n - 1 - j)
        den = sum(t[i, j] for i in lignes)
        if den <= 0:
            raise ValueError("Une colonne de développement est entièrement nulle : impossible de calculer un facteur.")
        facteurs.append(sum(t[i, j + 1] for i in lignes) / den)
    complet = t.copy()
    for i in range(n):
        for j in range(n - i, n):
            complet[i, j] = complet[i, j - 1] * facteurs[j - 1]
    lignes_res = []
    for i in range(n):
        dernier = float(t[i, n - 1 - i])
        ultime = float(complet[i, n - 1])
        lignes_res.append({"annee": i + 1, "dernier_connu": dernier, "ultime": ultime, "provision": ultime - dernier})
    return {"facteurs": facteurs, "triangle_complete": [[float(v) for v in l] for l in complet], "annees": lignes_res,
            "provision_totale": sum(l["provision"] for l in lignes_res), "ultime_total": sum(l["ultime"] for l in lignes_res),
            "limites": "Hypothèses : le schéma de règlement passé se répète, sans inflation nouvelle ni changement de gestion des dossiers. Aucune marge d'incertitude (méthode de Mack) n'est calculée."}


def triangle_synthetique(n: int = 8, graine: int = 3) -> list[list[float | None]]:
    """Triangle INVENTÉ : cadence de règlement connue (60 % la première année, 25 % la seconde…) et bruit léger."""
    rng = np.random.default_rng(graine)
    cadence = np.array([0.60, 0.25, 0.08, 0.04, 0.015, 0.008, 0.004, 0.003])[:n]
    cadence = cadence / cadence.sum()
    cum = np.cumsum(cadence)
    tri: list[list[float | None]] = []
    for i in range(n):
        ult = 1000 * (1.04 ** i) * rng.uniform(0.95, 1.05)
        ligne = []
        for j in range(n):
            ligne.append(round(float(ult * cum[j] * rng.uniform(0.98, 1.02)), 1) if j <= n - 1 - i else None)
        for j in range(1, n - i):                                   # le bruit ne doit jamais faire baisser un cumul
            if ligne[j] < ligne[j - 1]:
                ligne[j] = ligne[j - 1]
        tri.append(ligne)
    return tri
