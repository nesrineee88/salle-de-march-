"""Routes d'analyse fondamentale : score Z d'Altman et probabilité de défaut (PD)."""
from __future__ import annotations

from dataclasses import asdict
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import config
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from ..utilisateurs.service import auditer
from ..utilisateurs.db import obtenir_session
from . import pd_modele, zscore

routeur = APIRouter(prefix="/api/v1")


def dossier_modeles():
    return config.DATA_DIR / "modeles"


def fichier_kaggle():
    return config.DATA_DIR / "externes" / "cs-training.csv"


class CorpsComptes(BaseModel):
    modele: Literal["z", "z2"] = "z"
    actif_courant: float = Field(allow_inf_nan=False)
    passif_courant: float = Field(allow_inf_nan=False)
    total_actif: float = Field(allow_inf_nan=False)
    benefices_non_distribues: float = Field(allow_inf_nan=False)
    ebit: float = Field(allow_inf_nan=False)
    capitaux_propres: float = Field(allow_inf_nan=False, description="Valeur de marché pour Z, valeur comptable pour Z''")
    total_dettes: float = Field(allow_inf_nan=False)
    chiffre_affaires: float = Field(allow_inf_nan=False)


@routeur.get("/credit/zscore/exemples")
def exemples(_u: Utilisateur = Depends(exiger("marche.lire"))):
    return [{"nom": e["nom"], "fictive": True, "comptes": asdict(e["comptes"])} for e in zscore.EXEMPLES]


@routeur.post("/credit/zscore")
def calculer_z(corps: CorpsComptes, _u: Utilisateur = Depends(exiger("marche.lire"))):
    try:
        c = zscore.Comptes(**corps.model_dump(exclude={"modele"}))
        return zscore.calculer(c, corps.modele)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


def obtenir_modele() -> pd_modele.ModelePD:
    """Modèle enregistré ; à défaut, entraîné sur le fichier Kaggle s'il est présent, sinon sur l'échantillon synthétique étiqueté."""
    m = pd_modele.charger(dossier_modeles())
    if m is not None:
        return m
    return reentrainer()


def reentrainer() -> pd_modele.ModelePD:
    try:
        if fichier_kaggle().exists():
            m = pd_modele.entrainer(pd.read_csv(fichier_kaggle()), "kaggle")
        else:
            m = pd_modele.entrainer(pd_modele.echantillon_synthetique(), "synthetique")
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    pd_modele.sauvegarder(m, dossier_modeles())
    return m


@routeur.get("/credit/pd/modele")
def description_modele(_u: Utilisateur = Depends(exiger("marche.lire"))):
    m = obtenir_modele()
    return {"source": m.source, "taux_defaut": m.taux_defaut, "metriques": m.metriques,
            "variables": [{"nom": n, "libelle": pd_modele.VARIABLES[n][0], "aide": pd_modele.VARIABLES[n][1], "min": pd_modele.BORNES[n][0],
                           "max": pd_modele.BORNES[n][1], "mediane": m.medianes[n], "coefficient": m.coefs[n]} for n in pd_modele.NOMS],
            "intercept": m.intercept,
            "avertissement": ("Modèle entraîné sur des emprunteurs INVENTÉS (jeu synthétique) : les chiffres ne sont pas ceux de vrais emprunteurs. "
                              "Placez cs-training.csv dans data/externes puis demandez un ré-entraînement." if m.source == "synthetique" else
                              "Crédit aux particuliers (Give Me Some Credit) : ce n'est pas la probabilité de défaut d'une entreprise. Les lignes dont une colonne de retards porte un code d'erreur (96 ou 98) sont écartées.")}


class CorpsPD(BaseModel):
    valeurs: dict[str, float] = Field(default_factory=dict)


@routeur.post("/credit/pd")
def predire_pd(corps: CorpsPD, _u: Utilisateur = Depends(exiger("marche.lire"))):
    m = obtenir_modele()
    try:
        return {**m.predire(corps.valeurs), "source": m.source}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@routeur.post("/admin/credit/pd/entrainer")
def entrainer(admin: Utilisateur = Depends(exiger("admin.ia")), session=Depends(obtenir_session)):
    m = reentrainer()
    auditer(session, "admin.ia.entrainer_pd", admin.id, {"source": m.source, "auc": round(m.metriques["auc_logistique"], 4)})
    return {"source": m.source, "metriques": m.metriques}