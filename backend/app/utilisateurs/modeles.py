"""Tables : utilisateurs, jetons de rafraîchissement, journal d'audit."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def maintenant() -> datetime:
    return datetime.now(timezone.utc)


def en_utc(dt: datetime | None) -> datetime | None:
    """SQLite restitue des dates sans fuseau : on les considère comme UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)         # toujours en minuscules
    nom: Mapped[str] = mapped_column(String(60))
    nom_normalise: Mapped[str] = mapped_column(String(60), unique=True, index=True)  # minuscules : unicité sans casse
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="apprenant")
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    echecs_connexion: Mapped[int] = mapped_column(Integer, default=0)
    verrouille_jusqua: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    profil_risque: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class JetonRafraichissement(Base):
    __tablename__ = "jetons_rafraichissement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id", ondelete="CASCADE"), index=True)
    empreinte: Mapped[str] = mapped_column(String(64), unique=True)       # SHA-256 : le jeton lui-même n'est jamais stocké
    famille: Mapped[str] = mapped_column(String(32), index=True)          # une famille = une session de connexion
    expire_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoque_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    agent: Mapped[str | None] = mapped_column(String(255), nullable=True)


class JournalAudit(Base):
    __tablename__ = "journal_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    utilisateur_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)   # pas de clé étrangère : l'audit survit
    action: Mapped[str] = mapped_column(String(60), index=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant, index=True)
