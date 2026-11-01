"""Routes d'authentification, de profil et d'administration + dépendances de sécurité."""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from . import service
from .db import obtenir_session
from .limiteur import LimiteurFenetre
from .modeles import JournalAudit, Utilisateur
from .profil_risque import QUESTIONS
from .roles import ROLES, a_permission
from .securite import JetonInvalide, lire_jeton_acces

routeur = APIRouter(prefix="/api/v1")
_schema = HTTPBearer(auto_error=False)


@lru_cache
def obtenir_limiteur() -> LimiteurFenetre:
    return LimiteurFenetre(config.LIMITE_REQUETES_AUTH, 300)


def ip_de(requete: Request) -> str:
    # Derrière un proxy inverse, il faudra lire X-Forwarded-For (uniquement depuis un proxy de confiance).
    return requete.client.host if requete.client else "inconnue"


def limiter(requete: Request, limiteur: LimiteurFenetre = Depends(obtenir_limiteur)) -> None:
    if not limiteur.autoriser(ip_de(requete)):
        raise HTTPException(429, "Trop de tentatives. Réessayez dans quelques minutes.")


def utilisateur_courant(
    identifiants: HTTPAuthorizationCredentials | None = Depends(_schema),
    session: Session = Depends(obtenir_session),
) -> Utilisateur:
    non_authentifie = HTTPException(401, "Authentification requise.", headers={"WWW-Authenticate": "Bearer"})
    if identifiants is None:
        raise non_authentifie
    try:
        charge = lire_jeton_acces(identifiants.credentials)
        utilisateur = session.get(Utilisateur, int(charge["sub"]))
    except (JetonInvalide, ValueError):
        raise non_authentifie from None
    if utilisateur is None or not utilisateur.actif:     # rôle et statut relus en base : une rétrogradation est immédiate
        raise non_authentifie
    return utilisateur


def exiger(permission: str):
    def dependance(utilisateur: Utilisateur = Depends(utilisateur_courant)) -> Utilisateur:
        if not a_permission(utilisateur.role, permission):
            raise HTTPException(403, "Permission insuffisante pour cette action.")
        return utilisateur
    return dependance


def publique(u: Utilisateur) -> dict:
    return {"id": u.id, "email": u.email, "nom": u.nom, "role": u.role, "actif": u.actif,
            "profil_risque": u.profil_risque,
            "derniere_connexion": u.derniere_connexion.isoformat() if u.derniere_connexion else None}


# ------------------------------------------------------------------ authentification
class CorpsInscription(BaseModel):
    email: str = Field(max_length=254)
    nom: str = Field(max_length=100)
    mot_de_passe: str = Field(max_length=256)


class CorpsConnexion(BaseModel):
    email: str = Field(max_length=254)
    mot_de_passe: str = Field(max_length=256)


class CorpsJeton(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=200)


def _reponse_jetons(u: Utilisateur, acces: str, rafraichissement: str) -> dict:
    return {"token_type": "bearer", "access_token": acces, "refresh_token": rafraichissement,
            "expire_dans": config.ACCES_DUREE_MIN * 60, "utilisateur": publique(u)}


@routeur.post("/auth/inscription", status_code=201, dependencies=[Depends(limiter)])
def inscription(corps: CorpsInscription, requete: Request, session: Session = Depends(obtenir_session)):
    u = service.inscrire(session, corps.email, corps.nom, corps.mot_de_passe, ip_de(requete))
    return publique(u)


@routeur.post("/auth/connexion", dependencies=[Depends(limiter)])
def connexion(corps: CorpsConnexion, requete: Request, session: Session = Depends(obtenir_session)):
    u, acces, rafraichissement = service.connecter(
        session, corps.email, corps.mot_de_passe, ip_de(requete), requete.headers.get("user-agent"))
    return _reponse_jetons(u, acces, rafraichissement)


@routeur.post("/auth/rafraichir", dependencies=[Depends(limiter)])
def rafraichir(corps: CorpsJeton, requete: Request, session: Session = Depends(obtenir_session)):
    u, acces, rafraichissement = service.rafraichir(
        session, corps.refresh_token, ip_de(requete), requete.headers.get("user-agent"))
    return _reponse_jetons(u, acces, rafraichissement)


@routeur.post("/auth/deconnexion", status_code=204)
def deconnexion(corps: CorpsJeton, requete: Request, session: Session = Depends(obtenir_session)):
    service.deconnecter(session, corps.refresh_token, ip_de(requete))


# ------------------------------------------------------------------ profil
@routeur.get("/moi")
def moi(utilisateur: Utilisateur = Depends(utilisateur_courant)):
    return publique(utilisateur)


@routeur.get("/profil-risque/questionnaire")
def questionnaire():
    return {"questions": QUESTIONS, "avertissement": "Outil pédagogique, pas un conseil en investissement."}


class CorpsProfil(BaseModel):
    reponses: dict[str, int]


@routeur.post("/moi/profil-risque")
def definir_profil(corps: CorpsProfil, utilisateur: Utilisateur = Depends(utilisateur_courant),
                   session: Session = Depends(obtenir_session)):
    return service.enregistrer_profil_risque(session, utilisateur, corps.reponses)


# ------------------------------------------------------------------ sessions et mot de passe
class CorpsJetonFacultatif(BaseModel):
    refresh_token: str | None = Field(None, max_length=200)


@routeur.post("/moi/sessions")
def mes_sessions(corps: CorpsJetonFacultatif, utilisateur: Utilisateur = Depends(utilisateur_courant),
                 session: Session = Depends(obtenir_session)):
    """Appareils connectés. On envoie le jeton de ce navigateur pour savoir lequel est « celui-ci »."""
    return service.lister_sessions(session, utilisateur.id, corps.refresh_token)


@routeur.delete("/moi/sessions/{famille}", status_code=204)
def fermer_session(famille: str, requete: Request, utilisateur: Utilisateur = Depends(utilisateur_courant),
                   session: Session = Depends(obtenir_session)):
    service.terminer_session(session, utilisateur.id, famille, ip_de(requete))


@routeur.post("/moi/deconnexion-partout", status_code=204)
def deconnexion_partout(requete: Request, utilisateur: Utilisateur = Depends(utilisateur_courant),
                        session: Session = Depends(obtenir_session)):
    service.terminer_toutes_les_sessions(session, utilisateur.id, ip_de(requete))


class CorpsMotDePasse(BaseModel):
    ancien: str = Field(max_length=256)
    nouveau: str = Field(max_length=256)
    refresh_token: str | None = Field(None, max_length=200)


@routeur.post("/moi/mot-de-passe", status_code=204, dependencies=[Depends(limiter)])
def changer_mot_de_passe(corps: CorpsMotDePasse, requete: Request, utilisateur: Utilisateur = Depends(utilisateur_courant),
                         session: Session = Depends(obtenir_session)):
    service.changer_mot_de_passe(session, utilisateur, corps.ancien, corps.nouveau, corps.refresh_token, ip_de(requete))


# ------------------------------------------------------------------ administration
@routeur.get("/admin/utilisateurs")
def lister_utilisateurs(_admin: Utilisateur = Depends(exiger("admin.utilisateurs")),
                        session: Session = Depends(obtenir_session)):
    return [publique(u) for u in session.scalars(select(Utilisateur).order_by(Utilisateur.id))]


class CorpsModification(BaseModel):
    role: str | None = None
    actif: bool | None = None


@routeur.patch("/admin/utilisateurs/{utilisateur_id}")
def modifier_utilisateur(utilisateur_id: int, corps: CorpsModification, requete: Request,
                         admin: Utilisateur = Depends(exiger("admin.utilisateurs")),
                         session: Session = Depends(obtenir_session)):
    return publique(service.modifier_utilisateur(
        session, admin, utilisateur_id, corps.role, corps.actif, ip_de(requete)))


@routeur.get("/admin/audit")
def journal_audit(limite: int = 100, _admin: Utilisateur = Depends(exiger("admin.audit")),
                  session: Session = Depends(obtenir_session)):
    lignes = session.scalars(select(JournalAudit).order_by(JournalAudit.id.desc()).limit(min(max(limite, 1), 500)))
    return [{"id": a.id, "utilisateur_id": a.utilisateur_id, "action": a.action, "details": a.details,
             "ip": a.ip, "horodatage": a.horodatage.isoformat()} for a in lignes]


@routeur.get("/roles")
def lister_roles():
    return {"roles": list(ROLES)}
