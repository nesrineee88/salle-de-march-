"""Objets métier du trading : ordres, exécutions, positions, comptes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

ACHAT, VENTE = "achat", "vente"
MARCHE, LIMITE, STOP = "marche", "limite", "stop"
EN_ATTENTE, PARTIEL, EXECUTE, ANNULE, REJETE = "en_attente", "partiel", "execute", "annule", "rejete"
OUVERTS = {EN_ATTENTE, PARTIEL}
EPS = 1e-9

# Règles automatiques sur une position (décision D25)
STOP_LOSS, TAKE_PROFIT, STOP_SUIVEUR, ACHAT_COMPLEMENTAIRE = "stop_loss", "take_profit", "stop_suiveur", "achat_complementaire"
TYPES_REGLE = (STOP_LOSS, TAKE_PROFIT, STOP_SUIVEUR, ACHAT_COMPLEMENTAIRE)
ACTIVE, DECLENCHEE, ANNULEE, ECHEC = "active", "declenchee", "annulee", "echec"


@dataclass
class Execution:
    ordre_id: int
    compte_id: str
    symbole: str
    sens: str
    quantite: float
    prix: float
    frais: float
    instant: datetime
    pnl: float | None = None         # gain ou perte réalisé (hors frais) sur une vente ; None pour un achat


@dataclass
class Ordre:
    id: int
    compte_id: str
    symbole: str
    sens: str
    type: str
    quantite: float
    prix_limite: float | None = None
    prix_stop: float | None = None
    statut: str = EN_ATTENTE
    quantite_executee: float = 0.0
    prix_moyen: float | None = None
    declenche: bool = False          # un ordre stop devient ordre au marché une fois déclenché
    cree_le: datetime | None = None
    motif: str | None = None
    origine: str | None = None       # None : ordre de l'utilisateur ; « regle:12 » : placé par la règle automatique n° 12

    @property
    def reste(self) -> float:
        return self.quantite - self.quantite_executee

    @property
    def ouvert(self) -> bool:
        return self.statut in OUVERTS


@dataclass
class Regle:
    """Règle automatique évaluée à chaque avance du temps. `seuil` est une fraction signée du prix de revient moyen :
    stop_loss -0,30 (sort si le prix perd 30 %), take_profit +0,50 (vend `part` si le prix gagne 50 %),
    achat_complementaire +0,50 (rachète `part` de la position si le prix gagne 50 %),
    stop_suiveur 0,10 (sort si le prix recule de 10 % depuis son plus haut depuis la création de la règle)."""
    id: int
    compte_id: str
    symbole: str
    type: str
    seuil: float
    part: float = 1.0
    statut: str = ACTIVE
    cree_le: datetime | None = None
    declenchee_le: datetime | None = None
    plus_haut: float | None = None   # stop suiveur : plus haut prix observé depuis la création
    motif: str | None = None

    @property
    def active(self) -> bool:
        return self.statut == ACTIVE


@dataclass
class Position:
    symbole: str
    quantite: float
    prix_moyen: float


@dataclass
class Compte:
    id: str
    capital_initial: float
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    ordres: dict[int, Ordre] = field(default_factory=dict)
    executions: list[Execution] = field(default_factory=list)
    regles: dict[int, Regle] = field(default_factory=dict)
    pnl_realise: float = 0.0         # hors frais
    frais_cumules: float = 0.0
