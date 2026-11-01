"""Horloge de simulation (replay).

Temps simulé = départ + (temps réel écoulé) x facteur.
Exemple demandé par le projet : « 1 semaine simulée = 1 heure réelle » -> facteur 168.

Toutes les dates sont en UTC, sans fuseau (naïves). La source de temps est injectable pour les tests.
Une horloge par utilisateur (bac à sable) ou une horloge partagée (ligue) : même classe.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Callable

FACTEUR_MAX = 1_000_000.0

FACTEURS_PREDEFINIS = {
    "temps réel": 1.0,
    "1 jour = 1 heure": 24.0,
    "1 semaine = 1 heure": 168.0,
    "1 mois = 1 heure": 720.0,      # mois de 30 jours
}


def facteur_depuis(duree_simulee: timedelta, duree_reelle: timedelta) -> float:
    if duree_reelle <= timedelta(0) or duree_simulee <= timedelta(0):
        raise ValueError("les deux durées doivent être positives")
    return duree_simulee / duree_reelle


class HorlogeSimulation:
    def __init__(
        self,
        debut: datetime,
        facteur: float = 1.0,
        en_pause: bool = False,
        source_temps: Callable[[], float] = time.monotonic,
    ):
        self._verifier_facteur(facteur)
        self._source = source_temps
        self._facteur = float(facteur)
        self._en_pause = en_pause
        self._base_sim = debut
        self._base_reel = self._source()

    @staticmethod
    def _verifier_facteur(facteur: float) -> None:
        if not (0 < facteur <= FACTEUR_MAX):
            raise ValueError(f"facteur hors limites (0 < f <= {FACTEUR_MAX:g}) : {facteur}")

    def maintenant(self) -> datetime:
        if self._en_pause:
            return self._base_sim
        ecoule = self._source() - self._base_reel
        return self._base_sim + timedelta(seconds=ecoule * self._facteur)

    def _rebaser(self) -> None:
        """Fige l'instant simulé courant comme nouveau point de départ (évite tout saut)."""
        self._base_sim = self.maintenant()
        self._base_reel = self._source()

    def pause(self) -> None:
        if not self._en_pause:
            self._rebaser()
            self._en_pause = True

    def reprendre(self) -> None:
        if self._en_pause:
            self._base_reel = self._source()
            self._en_pause = False

    def regler_facteur(self, facteur: float) -> None:
        self._verifier_facteur(facteur)
        self._rebaser()
        self._facteur = float(facteur)

    def aller_a(self, instant: datetime) -> None:
        self._base_sim = instant
        self._base_reel = self._source()

    @property
    def facteur(self) -> float:
        return self._facteur

    @property
    def en_pause(self) -> bool:
        return self._en_pause

    def etat(self) -> dict:
        return {
            "maintenant": self.maintenant().isoformat(timespec="seconds"),
            "facteur": self._facteur,
            "en_pause": self._en_pause,
        }
