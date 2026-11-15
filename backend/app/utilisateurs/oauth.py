"""Connexion avec Google ou GitHub (flux « code d'autorisation », côté serveur).

Principes de sécurité :
- le paramètre `state` est signé (HMAC) et expire en 10 minutes : il protège contre la falsification de requête ;
- on n'accepte QUE une adresse e-mail que le fournisseur déclare vérifiée ;
- aucun secret ni jeton du fournisseur n'est conservé : on ne s'en sert que le temps de lire l'identité ;
- le navigateur reçoit uniquement notre jeton de rafraîchissement, dans le fragment d'URL (jamais envoyé à un serveur).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from .. import config
from . import securite

FOURNISSEURS = {
    "google": {
        "autorisation": "https://accounts.google.com/o/oauth2/v2/auth",
        "jeton": "https://oauth2.googleapis.com/token",
        "portee": "openid email profile",
    },
    "github": {
        "autorisation": "https://github.com/login/oauth/authorize",
        "jeton": "https://github.com/login/oauth/access_token",
        "portee": "read:user user:email",
    },
}


class ErreurOAuth(Exception):
    pass


def _identifiants(fournisseur: str) -> tuple[str, str] | None:
    i, s = ((config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET) if fournisseur == "google"
            else (config.GITHUB_CLIENT_ID, config.GITHUB_CLIENT_SECRET))
    return (i, s) if i and s else None


def disponibles() -> list[str]:
    return [f for f in FOURNISSEURS if _identifiants(f)]


def url_retour(fournisseur: str) -> str:
    return f"{config.URL_FRONT}/api/v1/auth/oauth/{fournisseur}/retour"


def _signer(charge: str) -> str:
    return hmac.new(securite.secret_jwt().encode(), charge.encode(), hashlib.sha256).hexdigest()


def creer_state(fournisseur: str) -> str:
    charge = f"{fournisseur}.{int(time.time())}.{secrets.token_urlsafe(12)}"
    return f"{charge}.{_signer(charge)}"


def verifier_state(state: str, fournisseur: str) -> bool:
    try:
        charge, signature = state.rsplit(".", 1)
        f, t, _ = charge.split(".", 2)
    except ValueError:
        return False
    return f == fournisseur and hmac.compare_digest(signature, _signer(charge)) and time.time() - int(t) < 600


def url_autorisation(fournisseur: str) -> str:
    ident = _identifiants(fournisseur)
    if not ident:
        raise ErreurOAuth("Ce mode de connexion n'est pas configuré sur ce serveur.")
    f = FOURNISSEURS[fournisseur]
    params = {"client_id": ident[0], "redirect_uri": url_retour(fournisseur), "scope": f["portee"],
              "state": creer_state(fournisseur)}
    if fournisseur == "google":
        params |= {"response_type": "code", "prompt": "select_account"}
    return f"{f['autorisation']}?{urllib.parse.urlencode(params)}"


def _http(url: str, donnees: dict | None = None, entetes: dict | None = None) -> dict | list:
    corps = urllib.parse.urlencode(donnees).encode() if donnees is not None else None
    req = urllib.request.Request(url, data=corps, headers={"Accept": "application/json", "User-Agent": "SalleDeMarche", **(entetes or {})})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        raise ErreurOAuth("Le fournisseur de connexion ne répond pas. Réessayez.") from None


def identite(fournisseur: str, code: str) -> tuple[str, str]:
    """Échange le code contre l'identité : (e-mail vérifié, nom). Lève ErreurOAuth sinon."""
    ident = _identifiants(fournisseur)
    if not ident:
        raise ErreurOAuth("Ce mode de connexion n'est pas configuré sur ce serveur.")
    f = FOURNISSEURS[fournisseur]
    rep = _http(f["jeton"], {"client_id": ident[0], "client_secret": ident[1], "code": code,
                             "redirect_uri": url_retour(fournisseur), "grant_type": "authorization_code"})
    acces = rep.get("access_token") if isinstance(rep, dict) else None
    if not acces:
        raise ErreurOAuth("Connexion refusée par le fournisseur.")
    auth = {"Authorization": f"Bearer {acces}"}
    if fournisseur == "google":
        info = _http("https://openidconnect.googleapis.com/v1/userinfo", None, auth)
        if not info.get("email") or not info.get("email_verified"):
            raise ErreurOAuth("Votre adresse Google n'est pas vérifiée.")
        return info["email"], info.get("name") or info["email"].split("@")[0]
    profil = _http("https://api.github.com/user", None, auth)
    adresses = _http("https://api.github.com/user/emails", None, auth)
    principale = next((a["email"] for a in adresses if a.get("primary") and a.get("verified")), None) if isinstance(adresses, list) else None
    if not principale:
        raise ErreurOAuth("Aucune adresse e-mail principale vérifiée sur votre compte GitHub.")
    return principale, profil.get("name") or profil.get("login") or principale.split("@")[0]
