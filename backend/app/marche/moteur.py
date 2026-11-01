"""Moteur de cotation : (actif, instant simulé) -> prix, statut et bougie en formation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import numpy as np

from .catalogue import Actif, Univers
from .stockage import DonneeIndisponible, Magasin
from .ticks import barre_partielle, generer_ticks, graine_barre, prix_a_fraction


@dataclass(frozen=True)
class Cotation:
    symbole: str
    horodatage: datetime
    prix: float
    statut: str                       # "ouvert" | "ferme"
    origine: str                      # "tick_simule" | "cloture" | "cloture_precedente" | "ouverture"
    derniere_cloture: float | None
    barre_en_formation: dict | None   # open/high/low/close déjà atteints, jamais le futur
    reference_variation: float | None = None   # base de la variation affichée (marché fermé : la séance d'avant)


def fraction_de_journee(t: datetime) -> float:
    return (t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6) / 86400.0


def _fraction_seance(actif: Actif, t: datetime) -> float:
    """Position dans la séance : <0 avant l'ouverture, >1 après la clôture, sinon dans [0, 1]."""
    if actif.session_utc is None:
        return fraction_de_journee(t)
    debut, fin = actif.session_utc
    d = debut.hour * 3600 + debut.minute * 60
    f = fin.hour * 3600 + fin.minute * 60
    s = t.hour * 3600 + t.minute * 60 + t.second
    return (s - d) / (f - d)


class MoteurMarche:
    def __init__(self, magasin: Magasin, univers: Univers, nb_ticks: int = 96):
        self._magasin = magasin
        self._univers = univers
        self._nb_ticks = nb_ticks
        self._chemins: dict[tuple[str, date], np.ndarray] = {}

    def _chemin(self, actif: Actif, jour: date, barre) -> np.ndarray:
        """Chemin de ticks de la journée, mis en cache (déterministe, donc sans risque)."""
        cle = (actif.symbole, jour)
        if cle not in self._chemins:
            if len(self._chemins) > 5000:
                self._chemins.clear()
            self._chemins[cle] = generer_ticks(
                barre["open"], barre["high"], barre["low"], barre["close"],
                n=self._nb_ticks, graine=graine_barre(actif.symbole, jour),
            )
        return self._chemins[cle]

    def invalider(self) -> None:
        """Vide le cache des chemins de ticks (à appeler quand les prix servis changent, par exemple après un scénario de crise)."""
        self._chemins.clear()

    def cotation(self, symbole: str, t: datetime) -> Cotation:
        if symbole not in self._univers:
            raise KeyError(symbole)
        actif = self._univers[symbole]
        jour = t.date()
        precedente = self._magasin.derniere_cloture_avant(symbole, jour)
        barre = self._magasin.barre_du_jour(symbole, jour)

        def fermee(prix: float, origine: str, formation=None) -> Cotation:
            # Marché fermé sans nouvelle séance : le prix est la dernière clôture, on le compare à la clôture d'avant.
            reference = self._magasin.cloture_avant_derniere(symbole, jour) if origine != "cloture" else precedente
            return Cotation(symbole, t, prix, "ferme", origine, precedente, formation, reference)

        if barre is None:                                  # week-end, jour férié, ou avant la 1re cotation
            if precedente is None:
                raise DonneeIndisponible(f"{symbole} ne cote pas encore au {jour.isoformat()}")
            return fermee(precedente, "cloture_precedente")

        f = _fraction_seance(actif, t)
        if barre.get("direct"):                            # mode Direct : le dernier prix du flux, jamais un tick simulé
            complete = {k: float(barre[k]) for k in ("open", "high", "low", "close")}
            if f < 0:
                return fermee(precedente if precedente is not None else float(barre["open"]), "cloture_precedente")
            if f > 1:
                return fermee(float(barre["close"]), "cloture", complete)
            return Cotation(symbole, t, float(barre["close"]), "ouvert", "direct", precedente, complete, precedente)
        if f < 0:                                          # avant l'ouverture : on ne montre pas la barre du jour
            if precedente is None:
                return fermee(float(barre["open"]), "ouverture")
            return fermee(precedente, "cloture_precedente")
        if f > 1:                                          # après la clôture : la barre est terminée
            complete = {k: float(barre[k]) for k in ("open", "high", "low", "close")}
            return fermee(float(barre["close"]), "cloture", complete)

        chemin = self._chemin(actif, jour, barre)
        return Cotation(
            symbole, t, prix_a_fraction(chemin, f), "ouvert", "tick_simule",
            precedente, barre_partielle(chemin, f), precedente,
        )

    def historique(self, symbole: str, t: datetime, barres: int = 250) -> list[dict]:
        """Barres terminées + la barre du jour en formation (marquée), sans aucune donnée future."""
        if symbole not in self._univers:
            raise KeyError(symbole)
        jour = t.date()
        passe = self._magasin.barres_terminees(symbole, jour, n=barres)
        sortie = [
            {
                "date": d.date().isoformat(),
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "volume": float(r["volume"]), "en_formation": False,
            }
            for d, r in passe.iterrows()
        ]
        if self._magasin.barre_du_jour(symbole, jour) is not None:
            c = self.cotation(symbole, t)
            if c.barre_en_formation is not None:
                sortie.append(
                    {"date": jour.isoformat(), **c.barre_en_formation,
                     "volume": None,                       # volume partiel non inventé
                     "en_formation": c.statut == "ouvert"}
                )
        return sortie[-barres:]
