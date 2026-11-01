"""Enregistrement du bac à sable de trading en base de données (SQLite en local, PostgreSQL en production).

Cinq tables : l'état du compte et de l'horloge, les positions, les ordres, les exécutions, les règles automatiques.
Les exécutions ne sont qu'ajoutées (jamais modifiées) ; positions et ordres sont réécrits à chaque sauvegarde.
Toutes les dates sont des instants simulés (UTC, sans fuseau).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..utilisateurs.db import Base


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class BacEtat(Base):
    __tablename__ = "bacs_etat"

    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True)
    capital_initial: Mapped[float] = mapped_column(Float(53))
    cash: Mapped[float] = mapped_column(Float(53))
    pnl_realise: Mapped[float] = mapped_column(Float(53), default=0.0)
    frais_cumules: Mapped[float] = mapped_column(Float(53), default=0.0)
    prochain_ordre_id: Mapped[int] = mapped_column(Integer, default=1)
    dernier_t: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    impacts: Mapped[dict] = mapped_column(JSON, default=dict)
    horloge_instant: Mapped[datetime] = mapped_column(DateTime)
    horloge_facteur: Mapped[float] = mapped_column(Float(53))
    mis_a_jour_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)


class PositionDb(Base):
    __tablename__ = "bacs_positions"

    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True)
    symbole: Mapped[str] = mapped_column(String(20), primary_key=True)
    quantite: Mapped[float] = mapped_column(Float(53))
    prix_moyen: Mapped[float] = mapped_column(Float(53))


class OrdreDb(Base):
    __tablename__ = "bacs_ordres"

    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True)
    ordre_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbole: Mapped[str] = mapped_column(String(20))
    sens: Mapped[str] = mapped_column(String(10))
    type: Mapped[str] = mapped_column(String(10))
    quantite: Mapped[float] = mapped_column(Float(53))
    prix_limite: Mapped[float | None] = mapped_column(Float(53), nullable=True)
    prix_stop: Mapped[float | None] = mapped_column(Float(53), nullable=True)
    statut: Mapped[str] = mapped_column(String(12), index=True)
    quantite_executee: Mapped[float] = mapped_column(Float(53), default=0.0)
    prix_moyen: Mapped[float | None] = mapped_column(Float(53), nullable=True)
    declenche: Mapped[bool] = mapped_column(Boolean, default=False)
    motif: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cree_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    origine: Mapped[str | None] = mapped_column(String(40), nullable=True)     # « regle:12 » si placé par une règle automatique


class RegleDb(Base):
    """Règles automatiques (stop-loss en %, prise de profit, stop suiveur, achat complémentaire) : voir D25."""
    __tablename__ = "bacs_regles"

    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True)
    regle_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbole: Mapped[str] = mapped_column(String(20))
    type: Mapped[str] = mapped_column(String(24))
    seuil: Mapped[float] = mapped_column(Float(53))
    part: Mapped[float] = mapped_column(Float(53), default=1.0)
    statut: Mapped[str] = mapped_column(String(12), index=True)
    cree_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    declenchee_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    plus_haut: Mapped[float | None] = mapped_column(Float(53), nullable=True)
    motif: Mapped[str | None] = mapped_column(String(300), nullable=True)


class ExecutionDb(Base):
    __tablename__ = "bacs_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id", ondelete="CASCADE"), index=True)
    ordre_id: Mapped[int] = mapped_column(Integer)
    symbole: Mapped[str] = mapped_column(String(20))
    sens: Mapped[str] = mapped_column(String(10))
    quantite: Mapped[float] = mapped_column(Float(53))
    prix: Mapped[float] = mapped_column(Float(53))
    frais: Mapped[float] = mapped_column(Float(53))
    instant: Mapped[datetime] = mapped_column(DateTime)
    pnl: Mapped[float | None] = mapped_column(Float(53), nullable=True)      # gain ou perte réalisé sur une vente


class HistoriqueValeurDb(Base):
    """Courbe de valeur du portefeuille : un point par jour simulé (la valeur la plus récente de ce jour)."""
    __tablename__ = "bacs_historique_valeur"

    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True)
    jour: Mapped[date] = mapped_column(primary_key=True)
    instant: Mapped[datetime] = mapped_column(DateTime)
    equity: Mapped[float] = mapped_column(Float(53))
    cash: Mapped[float] = mapped_column(Float(53))
    valeur_positions: Mapped[float] = mapped_column(Float(53))


def _dt(iso: str | None) -> datetime | None:
    return datetime.fromisoformat(iso) if iso else None


def sauvegarder(session: Session, utilisateur_id: int, etat: dict, nb_executions_deja_sauvees: int) -> int:
    """Écrit l'état complet dans une seule transaction. Retourne le nombre d'exécutions désormais enregistrées."""
    session.merge(BacEtat(
        utilisateur_id=utilisateur_id, capital_initial=etat["capital_initial"], cash=etat["cash"],
        pnl_realise=etat["pnl_realise"], frais_cumules=etat["frais_cumules"],
        prochain_ordre_id=etat["prochain_ordre_id"], dernier_t=_dt(etat["dernier_t"]), impacts=etat["impacts"],
        horloge_instant=_dt(etat["horloge_instant"]), horloge_facteur=etat["horloge_facteur"],
        mis_a_jour_le=_maintenant(),
    ))
    session.execute(delete(PositionDb).where(PositionDb.utilisateur_id == utilisateur_id))
    session.execute(delete(OrdreDb).where(OrdreDb.utilisateur_id == utilisateur_id))
    session.execute(delete(RegleDb).where(RegleDb.utilisateur_id == utilisateur_id))
    session.flush()
    session.add_all([PositionDb(utilisateur_id=utilisateur_id, **p) for p in etat["positions"]])
    session.add_all([
        OrdreDb(utilisateur_id=utilisateur_id, ordre_id=o["id"],
                **{k: v for k, v in o.items() if k not in ("id", "cree_le")}, cree_le=_dt(o["cree_le"]))
        for o in etat["ordres"]
    ])
    session.add_all([
        RegleDb(utilisateur_id=utilisateur_id, regle_id=r["id"],
                **{k: v for k, v in r.items() if k not in ("id", "cree_le", "declenchee_le")},
                cree_le=_dt(r["cree_le"]), declenchee_le=_dt(r["declenchee_le"]))
        for r in etat.get("regles", [])
    ])
    nouvelles = etat["executions"][nb_executions_deja_sauvees:]
    session.add_all([
        ExecutionDb(utilisateur_id=utilisateur_id, **{**e, "instant": _dt(e["instant"])}) for e in nouvelles
    ])
    session.commit()
    return len(etat["executions"])


def charger(session: Session, utilisateur_id: int) -> dict | None:
    bac = session.get(BacEtat, utilisateur_id)
    if bac is None:
        return None
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    dernier_regle = session.scalar(select(RegleDb.regle_id).where(RegleDb.utilisateur_id == utilisateur_id)
                                   .order_by(RegleDb.regle_id.desc()).limit(1))
    return {
        "prochaine_regle_id": (dernier_regle or 0) + 1,
        "capital_initial": bac.capital_initial, "cash": bac.cash, "pnl_realise": bac.pnl_realise,
        "frais_cumules": bac.frais_cumules, "prochain_ordre_id": bac.prochain_ordre_id,
        "dernier_t": iso(bac.dernier_t), "impacts": bac.impacts or {},
        "horloge_instant": iso(bac.horloge_instant), "horloge_facteur": bac.horloge_facteur,
        "positions": [
            {"symbole": p.symbole, "quantite": p.quantite, "prix_moyen": p.prix_moyen}
            for p in session.scalars(select(PositionDb).where(PositionDb.utilisateur_id == utilisateur_id))
        ],
        "ordres": [
            {"id": o.ordre_id, "symbole": o.symbole, "sens": o.sens, "type": o.type, "quantite": o.quantite,
             "prix_limite": o.prix_limite, "prix_stop": o.prix_stop, "statut": o.statut,
             "quantite_executee": o.quantite_executee, "prix_moyen": o.prix_moyen, "declenche": o.declenche,
             "motif": o.motif, "origine": o.origine, "cree_le": iso(o.cree_le)}
            for o in session.scalars(
                select(OrdreDb).where(OrdreDb.utilisateur_id == utilisateur_id).order_by(OrdreDb.ordre_id))
        ],
        "regles": [
            {"id": r.regle_id, "symbole": r.symbole, "type": r.type, "seuil": r.seuil, "part": r.part,
             "statut": r.statut, "cree_le": iso(r.cree_le), "declenchee_le": iso(r.declenchee_le),
             "plus_haut": r.plus_haut, "motif": r.motif}
            for r in session.scalars(
                select(RegleDb).where(RegleDb.utilisateur_id == utilisateur_id).order_by(RegleDb.regle_id))
        ],
        "executions": [
            {"ordre_id": e.ordre_id, "symbole": e.symbole, "sens": e.sens, "quantite": e.quantite,
             "prix": e.prix, "frais": e.frais, "instant": iso(e.instant), "pnl": e.pnl}
            for e in session.scalars(
                select(ExecutionDb).where(ExecutionDb.utilisateur_id == utilisateur_id).order_by(ExecutionDb.id))
        ],
    }


def enregistrer_point(session: Session, utilisateur_id: int, point: dict) -> None:
    session.merge(HistoriqueValeurDb(
        utilisateur_id=utilisateur_id, jour=date.fromisoformat(point["jour"]), instant=_dt(point["instant"]),
        equity=point["equity"], cash=point["cash"], valeur_positions=point["valeur_positions"]))
    session.commit()


def lire_historique(session: Session, utilisateur_id: int) -> list[dict]:
    lignes = session.scalars(select(HistoriqueValeurDb).where(HistoriqueValeurDb.utilisateur_id == utilisateur_id)
                             .order_by(HistoriqueValeurDb.instant))
    return [{"jour": h.jour.isoformat(), "instant": h.instant.isoformat(timespec="seconds"), "equity": h.equity,
             "cash": h.cash, "valeur_positions": h.valeur_positions} for h in lignes]


def supprimer(session: Session, utilisateur_id: int) -> None:
    for modele in (ExecutionDb, OrdreDb, RegleDb, PositionDb, HistoriqueValeurDb):
        session.execute(delete(modele).where(modele.utilisateur_id == utilisateur_id))
    session.execute(delete(BacEtat).where(BacEtat.utilisateur_id == utilisateur_id))
    session.commit()
