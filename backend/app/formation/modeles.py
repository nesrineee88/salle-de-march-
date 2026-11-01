"""Tables : progression de chaque apprenant par leçon, leçons désactivées par l'administration."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..utilisateurs.db import Base
from ..utilisateurs.modeles import maintenant


class ProgresLecon(Base):
    __tablename__ = "formation_progres"

    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True)
    lecon_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    meilleur_score: Mapped[float] = mapped_column(Float, default=0.0)         # part de bonnes réponses, de 0 à 1
    dernier_score: Mapped[float] = mapped_column(Float, default=0.0)
    tentatives: Mapped[int] = mapped_column(Integer, default=0)
    reussie_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    derniere_tentative: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)


class LeconDesactivee(Base):
    __tablename__ = "formation_lecons_desactivees"

    lecon_id: Mapped[str] = mapped_column(String(30), primary_key=True)
