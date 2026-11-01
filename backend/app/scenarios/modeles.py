"""Tables : scénarios de crise (chocs de prix injectés par l'administrateur) et actualités datées."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..utilisateurs.db import Base
from ..utilisateurs.modeles import maintenant


class ScenarioDb(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(600), default="")
    date_debut: Mapped[date] = mapped_column(Date, index=True)
    portee_type: Mapped[str] = mapped_column(String(12))                 # tous | classe | secteur | actifs
    portee_valeurs: Mapped[list] = mapped_column(JSON, default=list)
    choc: Mapped[float] = mapped_column(Float)                           # -0,30 = -30 % dès l'ouverture du premier jour
    recuperation: Mapped[float] = mapped_column(Float, default=0.0)      # part du choc regagnée (0 à 1)
    duree_recuperation_jours: Mapped[int] = mapped_column(Integer, default=0)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    cree_par: Mapped[int | None] = mapped_column(Integer, nullable=True)  # pas de clé étrangère : la trace survit au compte
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)


class ActualiteDb(Base):
    __tablename__ = "actualites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)                 # jour de parution (visible dès 08:00 ce jour-là)
    titre: Mapped[str] = mapped_column(String(200))
    texte: Mapped[str] = mapped_column(String(1200), default="")
    symboles: Mapped[list] = mapped_column(JSON, default=list)           # vide : nouvelle générale (marché)
    type_source: Mapped[str] = mapped_column(String(12), index=True)     # historique | fictif | scenario | import
    note_source: Mapped[str] = mapped_column(String(300), default="")
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    scenario_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
