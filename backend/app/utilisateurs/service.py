"""Logique métier des comptes : inscription, connexion, rotation des jetons, audit."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import config
from . import securite
from .modeles import JetonRafraichissement, JournalAudit, Utilisateur, en_utc, maintenant
from .profil_risque import ReponsesInvalides, evaluer_profil
from .roles import ROLES

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


class ErreurMetier(Exception):
    def __init__(self, code: str, message: str, statut: int = 400):
        super().__init__(message)
        self.code, self.message, self.statut = code, message, statut


def auditer(session: Session, action: str, utilisateur_id: int | None = None,
            details: dict | None = None, ip: str | None = None) -> None:
    """Ne jamais passer de mot de passe ni de jeton dans `details`."""
    session.add(JournalAudit(utilisateur_id=utilisateur_id, action=action, details=details, ip=ip))
    session.commit()


# ------------------------------------------------------------------ inscription
def inscrire(session: Session, email: str, nom: str, mot_de_passe: str, ip: str | None = None,
             role: str = "apprenant") -> Utilisateur:
    email = email.strip().lower()
    nom = " ".join(nom.split())
    if len(email) > 254 or not EMAIL.match(email):
        raise ErreurMetier("email_invalide", "Adresse e-mail invalide.", 422)
    if not 2 <= len(nom) <= 60:
        raise ErreurMetier("nom_invalide", "Le nom doit contenir entre 2 et 60 caractères.", 422)
    probleme = securite.valider_mot_de_passe(mot_de_passe, email, nom)
    if probleme:
        raise ErreurMetier("mot_de_passe_faible", probleme, 422)
    if role not in ROLES:
        raise ErreurMetier("role_invalide", f"Rôle inconnu : {role}", 422)

    deja = session.scalar(select(Utilisateur).where(
        (Utilisateur.email == email) | (Utilisateur.nom_normalise == nom.lower())))
    if deja:
        auditer(session, "inscription_refusee", None, {"motif": "doublon"}, ip)
        raise ErreurMetier("doublon", "Cet e-mail ou ce nom d'utilisateur est déjà utilisé.", 409)

    utilisateur = Utilisateur(email=email, nom=nom, nom_normalise=nom.lower(),
                              mot_de_passe_hash=securite.hacher(mot_de_passe), role=role)
    session.add(utilisateur)
    session.commit()
    auditer(session, "inscription", utilisateur.id, {"role": role}, ip)
    return utilisateur


# ------------------------------------------------------------------ jetons
def _emettre_jetons(session: Session, utilisateur: Utilisateur, famille: str,
                    ip: str | None, agent: str | None) -> tuple[str, str]:
    jeton, empr = securite.nouveau_jeton_rafraichissement()
    session.add(JetonRafraichissement(
        utilisateur_id=utilisateur.id, empreinte=empr, famille=famille,
        expire_le=maintenant() + timedelta(days=config.REFRESH_DUREE_JOURS),
        ip=ip, agent=(agent or "")[:255] or None,
    ))
    session.commit()
    return securite.creer_jeton_acces(utilisateur.id, utilisateur.role), jeton


def _revoquer_famille(session: Session, famille: str) -> None:
    session.execute(update(JetonRafraichissement)
                    .where(JetonRafraichissement.famille == famille, JetonRafraichissement.revoque_le.is_(None))
                    .values(revoque_le=maintenant()))
    session.commit()


def revoquer_tous_les_jetons(session: Session, utilisateur_id: int) -> None:
    session.execute(update(JetonRafraichissement)
                    .where(JetonRafraichissement.utilisateur_id == utilisateur_id,
                           JetonRafraichissement.revoque_le.is_(None))
                    .values(revoque_le=maintenant()))
    session.commit()


# ------------------------------------------------------------------ connexion
def connecter(session: Session, email: str, mot_de_passe: str, ip: str | None = None,
              agent: str | None = None) -> tuple[Utilisateur, str, str]:
    email = email.strip().lower()
    u = session.scalar(select(Utilisateur).where(Utilisateur.email == email))
    generique = ErreurMetier("identifiants", "E-mail ou mot de passe incorrect.", 401)

    if u is None:
        securite.verifier_mot_de_passe(mot_de_passe, securite.HASH_FACTICE)   # même durée qu'un vrai compte
        auditer(session, "connexion_echec", None, {"motif": "inconnu"}, ip)
        raise generique

    verrou = en_utc(u.verrouille_jusqua)
    if verrou and verrou > maintenant():
        auditer(session, "connexion_refusee", u.id, {"motif": "verrouille"}, ip)
        raise ErreurMetier("verrouille", "Compte temporairement verrouillé. Réessayez plus tard.", 423)

    correct, nouveau_hash = securite.verifier_mot_de_passe(mot_de_passe, u.mot_de_passe_hash)
    if not correct:
        u.echecs_connexion += 1
        if u.echecs_connexion >= config.MAX_ECHECS_CONNEXION:
            u.verrouille_jusqua = maintenant() + timedelta(minutes=config.VERROU_DUREE_MIN)
            u.echecs_connexion = 0
            session.commit()
            auditer(session, "compte_verrouille", u.id, {"minutes": config.VERROU_DUREE_MIN}, ip)
        else:
            session.commit()
        auditer(session, "connexion_echec", u.id, {"motif": "mot_de_passe"}, ip)
        raise generique
    if not u.actif:
        auditer(session, "connexion_refusee", u.id, {"motif": "desactive"}, ip)
        raise ErreurMetier("desactive", "Ce compte est désactivé. Contactez un administrateur.", 403)

    u.echecs_connexion, u.verrouille_jusqua, u.derniere_connexion = 0, None, maintenant()
    if nouveau_hash:
        u.mot_de_passe_hash = nouveau_hash
    session.commit()
    acces, rafraichissement = _emettre_jetons(session, u, uuid.uuid4().hex, ip, agent)
    auditer(session, "connexion", u.id, None, ip)
    return u, acces, rafraichissement


def rafraichir(session: Session, jeton: str, ip: str | None = None,
               agent: str | None = None) -> tuple[Utilisateur, str, str]:
    """Rotation : le jeton présenté est consommé. Le présenter une 2e fois = vol probable -> toute la session est révoquée."""
    ligne = session.scalar(select(JetonRafraichissement).where(
        JetonRafraichissement.empreinte == securite.empreinte(jeton)))
    invalide = ErreurMetier("jeton_invalide", "Session expirée, reconnectez-vous.", 401)
    if ligne is None:
        raise invalide
    if ligne.revoque_le is not None:
        _revoquer_famille(session, ligne.famille)
        auditer(session, "jeton_reutilise", ligne.utilisateur_id, {"famille": ligne.famille}, ip)
        raise invalide
    if en_utc(ligne.expire_le) <= maintenant():
        raise invalide
    u = session.get(Utilisateur, ligne.utilisateur_id)
    if u is None or not u.actif:
        raise invalide
    ligne.revoque_le = maintenant()
    session.commit()
    acces, nouveau = _emettre_jetons(session, u, ligne.famille, ip, agent)
    return u, acces, nouveau


def deconnecter(session: Session, jeton: str, ip: str | None = None) -> None:
    """Idempotent : un jeton inconnu ou déjà révoqué ne provoque pas d'erreur."""
    ligne = session.scalar(select(JetonRafraichissement).where(
        JetonRafraichissement.empreinte == securite.empreinte(jeton)))
    if ligne is not None:
        _revoquer_famille(session, ligne.famille)
        auditer(session, "deconnexion", ligne.utilisateur_id, None, ip)


# ------------------------------------------------------------------ profil et administration
def enregistrer_profil_risque(session: Session, utilisateur: Utilisateur, reponses: dict) -> dict:
    try:
        profil = evaluer_profil(reponses)
    except ReponsesInvalides as exc:
        raise ErreurMetier("reponses_invalides", str(exc), 422) from None
    utilisateur.profil_risque = profil
    session.commit()
    auditer(session, "profil_risque", utilisateur.id, {"categorie": profil["categorie"]})
    return profil


def modifier_utilisateur(session: Session, admin: Utilisateur, cible_id: int,
                         role: str | None, actif: bool | None, ip: str | None = None) -> Utilisateur:
    cible = session.get(Utilisateur, cible_id)
    if cible is None:
        raise ErreurMetier("introuvable", "Utilisateur introuvable.", 404)
    if cible.id == admin.id:
        raise ErreurMetier("auto_modification", "Vous ne pouvez pas modifier votre propre rôle ou statut.", 409)
    if role is not None:
        if role not in ROLES:
            raise ErreurMetier("role_invalide", f"Rôle inconnu : {role}", 422)
        cible.role = role
    if actif is not None:
        cible.actif = actif
    session.commit()
    if actif is False:
        revoquer_tous_les_jetons(session, cible.id)
    auditer(session, "modification_utilisateur", admin.id,
            {"cible": cible.id, "role": role, "actif": actif}, ip)
    return cible


# ------------------------------------------------------------------ sessions et mot de passe
def lister_sessions(session: Session, utilisateur_id: int, jeton_courant: str | None = None) -> list[dict]:
    """Sessions de connexion actives (une par appareil connecté). `courante` : celle de ce navigateur."""
    maintenant_ = maintenant()
    lignes = session.scalars(select(JetonRafraichissement).where(
        JetonRafraichissement.utilisateur_id == utilisateur_id).order_by(JetonRafraichissement.cree_le)).all()
    actives = {l.famille for l in lignes if l.revoque_le is None and en_utc(l.expire_le) > maintenant_}
    courante = securite.empreinte(jeton_courant) if jeton_courant else None
    sessions: dict[str, dict] = {}
    for l in lignes:
        if l.famille not in actives:
            continue
        s = sessions.setdefault(l.famille, {"famille": l.famille, "debut": l.cree_le, "derniere_activite": l.cree_le,
                                            "ip": l.ip, "agent": l.agent, "courante": False})
        s["derniere_activite"], s["ip"], s["agent"] = l.cree_le, l.ip, l.agent
        if l.revoque_le is None and l.empreinte == courante:
            s["courante"] = True
    return sorted(
        ({**s, "debut": en_utc(s["debut"]).isoformat(timespec="seconds"),
          "derniere_activite": en_utc(s["derniere_activite"]).isoformat(timespec="seconds")} for s in sessions.values()),
        key=lambda s: s["derniere_activite"], reverse=True)


def terminer_session(session: Session, utilisateur_id: int, famille: str, ip: str | None = None) -> None:
    existe = session.scalar(select(JetonRafraichissement.id).where(
        JetonRafraichissement.utilisateur_id == utilisateur_id, JetonRafraichissement.famille == famille))
    if existe is None:
        raise ErreurMetier("introuvable", "Session introuvable.", 404)
    _revoquer_famille(session, famille)
    auditer(session, "session_terminee", utilisateur_id, None, ip)


def terminer_toutes_les_sessions(session: Session, utilisateur_id: int, ip: str | None = None) -> None:
    revoquer_tous_les_jetons(session, utilisateur_id)
    auditer(session, "deconnexion_partout", utilisateur_id, None, ip)


def changer_mot_de_passe(session: Session, utilisateur: Utilisateur, ancien: str, nouveau: str,
                         jeton_a_garder: str | None = None, ip: str | None = None) -> None:
    """Change le mot de passe ; toutes les autres sessions sont fermées (celle de `jeton_a_garder` est conservée)."""
    correct, _ = securite.verifier_mot_de_passe(ancien, utilisateur.mot_de_passe_hash)
    if not correct:
        auditer(session, "mot_de_passe_echec", utilisateur.id, None, ip)
        raise ErreurMetier("mot_de_passe_incorrect", "Le mot de passe actuel est incorrect.", 403)
    if ancien == nouveau:
        raise ErreurMetier("identique", "Le nouveau mot de passe doit être différent de l'ancien.", 422)
    probleme = securite.valider_mot_de_passe(nouveau, utilisateur.email, utilisateur.nom)
    if probleme:
        raise ErreurMetier("mot_de_passe_faible", probleme, 422)
    utilisateur.mot_de_passe_hash = securite.hacher(nouveau)
    session.commit()
    garder = None
    if jeton_a_garder:
        ligne = session.scalar(select(JetonRafraichissement).where(
            JetonRafraichissement.empreinte == securite.empreinte(jeton_a_garder),
            JetonRafraichissement.utilisateur_id == utilisateur.id, JetonRafraichissement.revoque_le.is_(None)))
        garder = ligne.famille if ligne else None
    session.execute(update(JetonRafraichissement).where(
        JetonRafraichissement.utilisateur_id == utilisateur.id, JetonRafraichissement.revoque_le.is_(None),
        *( [JetonRafraichissement.famille != garder] if garder else [] )).values(revoque_le=maintenant()))
    session.commit()
    auditer(session, "mot_de_passe_change", utilisateur.id, None, ip)
