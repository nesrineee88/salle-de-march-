"""Routes du jeu. Aucune ne touche au bac à sable ni au portefeuille."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..utilisateurs.db import obtenir_session
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from . import service

routeur = APIRouter(prefix="/api/v1/jeu")
Acte = Literal["tenir", "reduire", "renforcer", "sortir"]


class CorpsPlan(BaseModel):
    perte_max: Literal[5, 10, 15, 20, 25]
    reaction: Acte


class CorpsPartie(BaseModel):
    mode: Literal["solo", "mystere", "jury"] = "solo"
    film: str | None = Field(None, max_length=20)
    difficulte: Literal["spectateur", "acteur", "realisateur"] = "acteur"
    plan: CorpsPlan | None = None


class CorpsVersion(BaseModel):
    version: int = Field(ge=0)


class CorpsAvancer(CorpsVersion):
    jusqu_a_l_arret: bool = False


class CorpsOrdreJeu(CorpsVersion):
    rang: int = Field(ge=0, le=9)
    sens: Literal["achat", "vente"]


class CorpsChoix(CorpsVersion):
    acte: Acte


class CorpsDevine(CorpsVersion):
    film: str = Field(max_length=20)


@routeur.get("/accueil")
def accueil(u: Utilisateur = Depends(exiger("jeu.jouer")), session: Session = Depends(obtenir_session)):
    return service.accueil(session, u.id)


@routeur.post("/parties", status_code=201)
def creer(corps: CorpsPartie, u: Utilisateur = Depends(exiger("jeu.jouer")), session: Session = Depends(obtenir_session)):
    plan = corps.plan.model_dump() if corps.plan else None
    return service.vue(service.creer(session, u.id, corps.mode, corps.film, corps.difficulte, plan))


@routeur.get("/parties/{partie_id}")
def lire(partie_id: str, u: Utilisateur = Depends(exiger("jeu.jouer")), session: Session = Depends(obtenir_session)):
    return service.vue(service.lire_partie(session, u.id, partie_id))


@routeur.post("/parties/{partie_id}/avancer")
def avancer(partie_id: str, corps: CorpsAvancer, u: Utilisateur = Depends(exiger("jeu.jouer")),
            session: Session = Depends(obtenir_session)):
    p = service.lire_partie(session, u.id, partie_id)
    return service.vue(service.avancer(session, p, corps.version, corps.jusqu_a_l_arret))


@routeur.post("/parties/{partie_id}/ordres")
def ordonner(partie_id: str, corps: CorpsOrdreJeu, u: Utilisateur = Depends(exiger("jeu.jouer")),
             session: Session = Depends(obtenir_session)):
    p = service.lire_partie(session, u.id, partie_id)
    return service.vue(service.ordonner(session, p, corps.version, corps.rang, corps.sens))


@routeur.post("/parties/{partie_id}/choix")
def choisir(partie_id: str, corps: CorpsChoix, u: Utilisateur = Depends(exiger("jeu.jouer")),
            session: Session = Depends(obtenir_session)):
    p = service.lire_partie(session, u.id, partie_id)
    return service.vue(service.choisir(session, p, corps.version, corps.acte))


@routeur.post("/parties/{partie_id}/deviner")
def deviner(partie_id: str, corps: CorpsDevine, u: Utilisateur = Depends(exiger("jeu.jouer")),
            session: Session = Depends(obtenir_session)):
    p = service.lire_partie(session, u.id, partie_id)
    return service.vue(service.deviner(session, p, corps.version, corps.film))


@routeur.post("/parties/{partie_id}/abandonner")
def abandonner(partie_id: str, corps: CorpsVersion, u: Utilisateur = Depends(exiger("jeu.jouer")),
               session: Session = Depends(obtenir_session)):
    p = service.lire_partie(session, u.id, partie_id)
    service.abandonner(session, p, corps.version)
    return {"statut": service.ABANDONNEE}
