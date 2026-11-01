"""Crée (ou promeut) le premier administrateur. À lancer une fois depuis backend/ :

    python -m app.utilisateurs.creer_admin admin@exemple.com "Nom Affiché"

Le mot de passe est demandé au clavier (jamais en argument de ligne de commande, qui reste dans l'historique).
"""
from __future__ import annotations

import getpass
import sys

from sqlalchemy import select

from .db import obtenir_base
from .modeles import Utilisateur
from .service import ErreurMetier, auditer, inscrire


def creer_admin(session, email: str, nom: str, mot_de_passe: str) -> Utilisateur:
    email = email.strip().lower()
    existant = session.scalar(select(Utilisateur).where(Utilisateur.email == email))
    if existant is not None:
        existant.role, existant.actif = "admin", True
        session.commit()
        auditer(session, "admin_promu_cli", existant.id)
        return existant
    return inscrire(session, email, nom, mot_de_passe, role="admin")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__)
        return 2
    email, nom = argv
    mot_de_passe = getpass.getpass("Mot de passe (10 caractères minimum, lettres et chiffres) : ")
    if mot_de_passe != getpass.getpass("Confirmez le mot de passe : "):
        print("Les deux mots de passe diffèrent.")
        return 1
    base = obtenir_base()
    with base.session() as session:
        try:
            u = creer_admin(session, email, nom, mot_de_passe)
        except ErreurMetier as exc:
            print(f"Erreur : {exc.message}")
            return 1
    print(f"Administrateur prêt : {u.email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
