"""Routes actuarielles : tarification auto (prime, marge, probabilité de sinistre) et provisionnement par Chain Ladder."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import config
from ..utilisateurs.db import obtenir_session
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from ..utilisateurs.service import auditer
from . import tarification as tar

routeur = APIRouter(prefix="/api/v1/actuariat")


def dossier_modeles():
    return config.DATA_DIR / "modeles"


def fichiers_kaggle():
    d = config.DATA_DIR / "externes"
    return d / "freMTPL2freq.csv", d / "freMTPL2sev.csv"


def reentrainer() -> tar.ModeleTarif:
    freq, sev = fichiers_kaggle()
    try:
        if freq.exists() and sev.exists():
            m = tar.ModeleTarif.entrainer(tar.nettoyer(pd.read_csv(freq), pd.read_csv(sev)), "kaggle")
        else:
            m = tar.ModeleTarif.entrainer(tar.echantillon_synthetique(), "synthetique")
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    tar.sauvegarder(m, dossier_modeles())
    return m


def obtenir_modele() -> tar.ModeleTarif:
    return tar.charger(dossier_modeles()) or reentrainer()


@routeur.get("/modele")
def modele(_u: Utilisateur = Depends(exiger("marche.lire"))):
    m = obtenir_modele()
    relativites = lambda p: [{"variable": k, "libelle": tar._libelle(k), "facteur_par_ecart_type": float(__import__("math").exp(v))} for k, v in p.items() if k != "intercept"]
    return {"source": m.source, "metriques": m.metriques, "relativites_frequence": relativites(m.frequence), "relativites_cout": relativites(m.severite),
            "variables": [{"nom": n, "libelle": tar.LIBELLES[n], "min": lo, "max": hi} for n, (lo, hi) in tar.BORNES.items()]
                         + [{"nom": c, "libelle": tar.LIBELLES[c], "choix": v} for c, v in tar.CAT.items()],
            "avertissement": ("Modèle estimé sur des contrats et sinistres INVENTÉS (jeu synthétique) : les primes ne sont pas réalistes. "
                              "Placez freMTPL2freq.csv et freMTPL2sev.csv dans data/externes puis demandez un ré-entraînement." if m.source == "synthetique" else
                              "Modèle estimé sur le jeu freMTPL2 (assurance auto française) : à ne pas utiliser tel quel pour un autre marché.")}


class CorpsPrime(BaseModel):
    profil: dict = Field(default_factory=dict)
    exposition: float = Field(1.0, gt=0, le=1)
    frais: float = Field(0.20, ge=0, lt=0.9)
    marge: float = Field(0.05, ge=0, le=1)


@routeur.post("/prime")
def prime(corps: CorpsPrime, _u: Utilisateur = Depends(exiger("marche.lire"))):
    try:
        return {**obtenir_modele().prime(corps.profil, corps.exposition, corps.frais, corps.marge), "source": obtenir_modele().source}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


class CorpsTriangle(BaseModel):
    triangle: list[list[float | None]]


@routeur.get("/provision/exemple")
def exemple(_u: Utilisateur = Depends(exiger("marche.lire"))):
    return {"triangle": tar.triangle_synthetique(), "fictif": True, "unite": "milliers (inventés)"}


@routeur.post("/provision")
def provision(corps: CorpsTriangle, _u: Utilisateur = Depends(exiger("marche.lire"))):
    try:
        return tar.chain_ladder(corps.triangle)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@routeur.post("/admin/entrainer")
def entrainer(admin: Utilisateur = Depends(exiger("admin.ia")), session=Depends(obtenir_session)):
    m = reentrainer()
    auditer(session, "admin.ia.entrainer_tarif", admin.id, {"source": m.source})
    return {"source": m.source, "metriques": m.metriques}
