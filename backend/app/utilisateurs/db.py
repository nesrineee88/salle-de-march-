"""Accès à la base des utilisateurs (SQLAlchemy 2). SQLite en local, PostgreSQL en production."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .. import config


class Base(DeclarativeBase):
    pass


class BaseUtilisateurs:
    def __init__(self, url: str):
        options: dict = {}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                options["poolclass"] = StaticPool            # une seule connexion pour la mémoire
        self.moteur = create_engine(url, **options)
        self._fabrique = sessionmaker(self.moteur, expire_on_commit=False)
        from . import modeles  # noqa: F401  (enregistre les tables)
        from ..trading import persistance  # noqa: F401
        from ..scenarios import modeles as _scenarios  # noqa: F401
        from ..formation import modeles as _formation  # noqa: F401

        # Développement : les tables manquantes sont créées automatiquement.
        # Production (SDM_ENV=production) : le schéma est géré uniquement par `alembic upgrade head`.
        if config.ENVIRONNEMENT != "production":
            self._verifier_schema()            # avant create_all : on ne crée rien dans une base qu'il faut d'abord migrer
            Base.metadata.create_all(self.moteur)

    def _verifier_schema(self) -> None:
        """`create_all` ne modifie jamais une table qui existe déjà. Si la base de développement date d'une version
        précédente (colonne ajoutée depuis), on arrête avec un message clair plutôt que d'échouer plus tard, à l'enregistrement."""
        from sqlalchemy import inspect

        inspecteur = inspect(self.moteur)
        manque = []
        for table in Base.metadata.sorted_tables:
            if not inspecteur.has_table(table.name):
                continue
            presentes = {c["name"] for c in inspecteur.get_columns(table.name)}
            manque += [f"{table.name}.{c.name}" for c in table.columns if c.name not in presentes]
        if manque:
            raise RuntimeError(
                "La base de données de développement date d'une version précédente du projet "
                f"(colonnes absentes : {', '.join(manque)}). Arrêtez le serveur puis supprimez le fichier "
                "data/utilisateurs.db (vos comptes de test seront effacés ; recréez l'administrateur ensuite), "
                "ou, avec PostgreSQL, lancez `alembic upgrade head`.")

    def session(self) -> Session:
        return self._fabrique()


@lru_cache
def obtenir_base() -> BaseUtilisateurs:
    if config.URL_BASE.startswith("sqlite:///") and ":memory:" not in config.URL_BASE:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return BaseUtilisateurs(config.URL_BASE)


def obtenir_session():
    base = obtenir_base()
    session = base.session()
    try:
        yield session
    finally:
        session.close()
