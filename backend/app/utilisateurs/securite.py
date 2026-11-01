"""Mots de passe (Argon2id), jetons d'accès (JWT) et jetons de rafraîchissement (opaques, hachés)."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .. import config

_hasher = PasswordHasher()                       # Argon2id, paramètres par défaut de la bibliothèque
HASH_FACTICE = _hasher.hash("mot-de-passe-factice-pour-egaliser-les-temps")

MOTS_DE_PASSE_COURANTS = {
    "password12", "motdepasse1", "123456789a", "azertyuiop1", "qwertyuiop1", "password123",
    "motdepasse123", "1234567890a", "azerty12345", "admin12345",
}


class JetonInvalide(Exception):
    pass


def hacher(mot_de_passe: str) -> str:
    return _hasher.hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, hash_stocke: str) -> tuple[bool, str | None]:
    """Retourne (correct, nouveau_hash_si_les_paramètres_ont_changé)."""
    try:
        _hasher.verify(hash_stocke, mot_de_passe)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, None
    return True, (_hasher.hash(mot_de_passe) if _hasher.check_needs_rehash(hash_stocke) else None)


def valider_mot_de_passe(mot_de_passe: str, email: str = "", nom: str = "") -> str | None:
    """Retourne un message d'erreur en français, ou None si le mot de passe est acceptable."""
    if len(mot_de_passe) < 10:
        return "Le mot de passe doit contenir au moins 10 caractères."
    if len(mot_de_passe) > 128:
        return "Le mot de passe ne doit pas dépasser 128 caractères."
    if not any(c.isalpha() for c in mot_de_passe) or not any(c.isdigit() for c in mot_de_passe):
        return "Le mot de passe doit contenir au moins une lettre et un chiffre."
    bas = mot_de_passe.lower()
    if bas in MOTS_DE_PASSE_COURANTS:
        return "Ce mot de passe est trop courant."
    local = email.split("@")[0].lower()
    if (len(local) >= 4 and local in bas) or (len(nom) >= 4 and nom.lower() in bas):
        return "Le mot de passe ne doit pas contenir votre e-mail ou votre nom."
    return None


def secret_jwt() -> str:
    if config.JWT_SECRET:
        return config.JWT_SECRET
    if config.ENVIRONNEMENT == "production":
        raise RuntimeError("SDM_JWT_SECRET est obligatoire en production.")
    return _SECRET_EPHEMERE                       # développement : les jetons meurent au redémarrage


_SECRET_EPHEMERE = secrets.token_urlsafe(48)


def creer_jeton_acces(utilisateur_id: int, role: str, secret: str | None = None, duree_min: int | None = None) -> str:
    maintenant = datetime.now(timezone.utc)
    charge = {
        "sub": str(utilisateur_id), "role": role, "typ": "acces", "jti": uuid.uuid4().hex,
        "iat": maintenant, "exp": maintenant + timedelta(minutes=duree_min or config.ACCES_DUREE_MIN),
    }
    return jwt.encode(charge, secret or secret_jwt(), algorithm="HS256")


def lire_jeton_acces(jeton: str, secret: str | None = None) -> dict:
    try:
        charge = jwt.decode(
            jeton, secret or secret_jwt(), algorithms=["HS256"], options={"require": ["exp", "sub", "typ"]}
        )
    except jwt.PyJWTError as exc:
        raise JetonInvalide(str(exc)) from None
    if charge.get("typ") != "acces":
        raise JetonInvalide("type de jeton incorrect")
    return charge


def nouveau_jeton_rafraichissement() -> tuple[str, str]:
    jeton = secrets.token_urlsafe(48)
    return jeton, empreinte(jeton)


def empreinte(jeton: str) -> str:
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()
