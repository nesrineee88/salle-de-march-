"""Routes de la formation : leçons, questions corrigées côté serveur, progression, ligue, vue du formateur."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..utilisateurs.db import obtenir_session
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from ..utilisateurs.service import auditer
from . import service
from .contenu import INDEX
from .modeles import LeconDesactivee

routeur = APIRouter(prefix="/api/v1/formation")


@routeur.get("/lecons")
def lecons(u: Utilisateur = Depends(exiger("formation.suivre")), session: Session = Depends(obtenir_session)):
    return {"lecons": service.lister(session, u.id, u.role), "progression": service.progression(session, u.id)}


def _lecon_visible(session: Session, u: Utilisateur, lecon_id: str) -> None:
    if lecon_id not in INDEX:
        raise HTTPException(404, "Leçon introuvable.")
    if lecon_id in service.desactivees(session) and u.role not in ("formateur", "admin"):
        raise HTTPException(404, "Cette leçon n'est pas disponible pour le moment.")


@routeur.get("/lecons/{lecon_id}")
def une_lecon(lecon_id: str, u: Utilisateur = Depends(exiger("formation.suivre")), session: Session = Depends(obtenir_session)):
    _lecon_visible(session, u, lecon_id)
    return service.detail(session, u.id, lecon_id)


class CorpsReponses(BaseModel):
    reponses: list[int | None] = Field(max_length=20)


@routeur.post("/lecons/{lecon_id}/repondre")
def repondre(lecon_id: str, corps: CorpsReponses, u: Utilisateur = Depends(exiger("formation.suivre")), session: Session = Depends(obtenir_session)):
    _lecon_visible(session, u, lecon_id)
    try:
        return service.corriger(session, u.id, lecon_id, corps.reponses)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@routeur.get("/ligue")
def ligue(jusqu_au: date | None = Query(None), _u: Utilisateur = Depends(exiger("formation.suivre")), session: Session = Depends(obtenir_session)):
    return {"classement": service.ligue(session, jusqu_au), "jusqu_au": jusqu_au.isoformat() if jusqu_au else None,
            "regle": ("Score = rendement divisé par la pire baisse (au moins 5 %). Au moins 5 jours simulés. "
                      + ("Tous les participants sont jugés à la même date simulée : classement équitable." if jusqu_au else
                         "Sans date fixe, chacun est jugé sur sa propre période simulée : comparez avec prudence, ou choisissez une date commune."))}


@routeur.get("/classe")
def classe(_u: Utilisateur = Depends(exiger("classe.voir")), session: Session = Depends(obtenir_session)):
    return service.classe(session)


class CorpsActivation(BaseModel):
    actif: bool


@routeur.patch("/lecons/{lecon_id}/activation")
def activation(lecon_id: str, corps: CorpsActivation, u: Utilisateur = Depends(exiger("formation.gerer")), session: Session = Depends(obtenir_session)):
    if lecon_id not in INDEX:
        raise HTTPException(404, "Leçon introuvable.")
    existe = session.get(LeconDesactivee, lecon_id)
    if corps.actif and existe:
        session.delete(existe)
    elif not corps.actif and not existe:
        session.add(LeconDesactivee(lecon_id=lecon_id))
    session.commit()
    auditer(session, "formation.lecon.activer" if corps.actif else "formation.lecon.desactiver", u.id, {"lecon": lecon_id})
    return {"id": lecon_id, "active": corps.actif}
