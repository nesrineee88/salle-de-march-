"""Table des parties. Elle ne référence ni le bac à sable ni le portefeuille : le compte de jeu est indépendant."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..utilisateurs.db import Base
from ..utilisateurs.modeles import maintenant


class PartieJeu(Base):
    __tablename__ = "jeu_parties"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)          # aléatoire : ne révèle ni le film ni le rang
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id", ondelete="CASCADE"), index=True)
    film: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(10))                          # solo, mystere, jury
    difficulte: Mapped[str] = mapped_column(String(15))
    statut: Mapped[str] = mapped_column(String(12))                        # en_cours, terminee, abandonnee
    premiere: Mapped[bool] = mapped_column(Boolean, default=False)         # première rencontre de ce joueur avec ce film
    seance: Mapped[int] = mapped_column(Integer, default=0)                # dernière séance dévoilée
    version: Mapped[int] = mapped_column(Integer, default=0)               # refuse deux actions parties du même état
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    presentation: Mapped[list] = mapped_column(JSON, default=list)         # ordre d'affichage des actifs
    ordres: Mapped[list] = mapped_column(JSON, default=list)               # journal : séance, actif, sens
    choix: Mapped[list] = mapped_column(JSON, default=list)                # journal : séance, choix
    devine: Mapped[str | None] = mapped_column(String(20), nullable=True)  # séance mystère : la crise devinée
    note: Mapped[int | None] = mapped_column(Integer, nullable=True)       # calculée par le serveur au générique
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    maj_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
