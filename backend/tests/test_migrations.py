"""Les migrations Alembic produisent exactement le schéma décrit par les modèles."""
import os
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app import config
from app.utilisateurs.db import Base

RACINE_BACKEND = Path(__file__).resolve().parents[1]


def config_alembic(url, monkeypatch):
    monkeypatch.setattr(config, "URL_BASE", url)
    cfg = Config(str(RACINE_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(RACINE_BACKEND / "migrations"))
    return cfg


def test_upgrade_puis_downgrade(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'mig.db'}"
    cfg = config_alembic(url, monkeypatch)
    command.upgrade(cfg, "head")
    moteur = create_engine(url)
    tables = set(inspect(moteur).get_table_names())
    attendues = {t for t in Base.metadata.tables}
    assert attendues <= tables and "alembic_version" in tables

    with moteur.connect() as c:                       # aucune différence entre les modèles et la base migrée
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []

    command.downgrade(cfg, "base")
    assert set(inspect(create_engine(url)).get_table_names()) <= {"alembic_version"}


def test_migration_0003_tolere_une_table_deja_creee_par_le_serveur_de_developpement(tmp_path, monkeypatch):
    """Cas réel : le serveur crée la table des règles avant que l'utilisateur lance « alembic upgrade head »."""
    url = f"sqlite:///{tmp_path / 'mig3.db'}"
    cfg = config_alembic(url, monkeypatch)
    command.upgrade(cfg, "0002")
    moteur = create_engine(url)
    Base.metadata.tables["bacs_regles"].create(moteur)
    command.upgrade(cfg, "head")
    with moteur.connect() as c:
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
        assert "origine" in {col["name"] for col in inspect(c).get_columns("bacs_ordres")}


def test_migrations_sur_postgresql_si_disponible(monkeypatch):
    url = os.environ.get("SDM_TEST_POSTGRES")
    if not url:
        return
    moteur = create_engine(url)
    Base.metadata.drop_all(moteur)
    with moteur.begin() as c:
        c.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    cfg = config_alembic(url, monkeypatch)
    command.upgrade(cfg, "head")
    with moteur.connect() as c:
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
    command.downgrade(cfg, "base")
    moteur.dispose()
