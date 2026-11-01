"""Carnet d'ordres SYNTHÉTIQUE.

Il n'existe pas de carnet réel dans des données journalières : on en construit un autour du prix de
référence. Les paramètres ci-dessous sont PÉDAGOGIQUES, non calibrés sur des marchés réels
(documenté dans docs/DECISIONS.md). Le carnet est une fonction pure du prix de référence : pour la
liquidité qui se consomme et se reconstitue, voir l'impact de marché dans `salle.py`.

Fonctionne avec des prix négatifs (WTI, avril 2020) : les écarts sont calculés sur la valeur absolue.
"""
from __future__ import annotations

from dataclasses import dataclass

NB_NIVEAUX = 10
SPREAD_BPS = {"action": 5.0, "crypto": 10.0, "matiere": 8.0, "indice": 5.0}
PROFONDEUR_NIVEAU_USD = {"action": 20_000.0, "crypto": 10_000.0, "matiere": 15_000.0, "indice": 20_000.0}
FRAIS_BPS = {"action": 5.0, "crypto": 10.0, "matiere": 5.0, "indice": 0.0}
ECHELLE_MIN = 0.01


@dataclass(frozen=True)
class Niveau:
    prix: float
    quantite: float


@dataclass(frozen=True)
class Carnet:
    symbole: str
    prix_reference: float
    achats: tuple[Niveau, ...]       # offres d'achat, meilleur prix en premier (décroissant)
    ventes: tuple[Niveau, ...]       # offres de vente, meilleur prix en premier (croissant)

    @property
    def meilleur_achat(self) -> float:
        return self.achats[0].prix

    @property
    def meilleur_vente(self) -> float:
        return self.ventes[0].prix

    @property
    def spread(self) -> float:
        return self.meilleur_vente - self.meilleur_achat

    def en_dict(self) -> dict:
        return {
            "symbole": self.symbole,
            "prix_reference": self.prix_reference,
            "spread": self.spread,
            "achats": [{"prix": n.prix, "quantite": n.quantite} for n in self.achats],
            "ventes": [{"prix": n.prix, "quantite": n.quantite} for n in self.ventes],
            "synthetique": True,
        }


def echelle(prix: float) -> float:
    return max(abs(prix), ECHELLE_MIN)


def quantite_niveau_1(classe: str, prix_ref: float, liquidite: float = 1.0) -> float:
    return PROFONDEUR_NIVEAU_USD[classe] * liquidite / echelle(prix_ref)


def construire_carnet(
    symbole: str, classe: str, prix_ref: float, liquidite: float = 1.0, niveaux: int = NB_NIVEAUX
) -> Carnet:
    e = echelle(prix_ref)
    demi = e * SPREAD_BPS[classe] / 2e4
    q1 = quantite_niveau_1(classe, prix_ref, liquidite)
    achats, ventes = [], []
    for k in range(niveaux):
        q = q1 * (1.0 + 0.5 * k)                     # plus profond = plus de volume
        ventes.append(Niveau(prix_ref + demi + k * demi, q))
        achats.append(Niveau(prix_ref - demi - k * demi, q))
    return Carnet(symbole, prix_ref, tuple(achats), tuple(ventes))


def frais(classe: str, prix: float, quantite: float) -> float:
    """Commission en pourcentage du montant (valeur absolue du prix x quantité)."""
    return FRAIS_BPS[classe] * abs(prix) * quantite / 1e4
