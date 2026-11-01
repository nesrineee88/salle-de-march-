"""Environnement Alembic : l'adresse de la base est celle de l'application (SDM_DATABASE_URL)."""
from alembic import context
from sqlalchemy import create_engine

from app import config
from app.utilisateurs import modeles  # noqa: F401  (enregistre les tables)
from app.trading import persistance  # noqa: F401
from app.scenarios import modeles as _scenarios  # noqa: F401
from app.formation import modeles as _formation  # noqa: F401
from app.utilisateurs.db import Base

cible = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.URL_BASE, target_metadata=cible, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    moteur = create_engine(config.URL_BASE)
    with moteur.connect() as connexion:
        context.configure(connection=connexion, target_metadata=cible, compare_type=True,
                          render_as_batch=connexion.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
