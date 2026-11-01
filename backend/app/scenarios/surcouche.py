"""Calcul des multiplicateurs de prix des scénarios de crise.

Un scénario multiplie, à partir de sa date de début, tous les prix (ouverture, plus haut, plus bas, clôture) de son périmètre
par 1 + choc le premier jour (le choc apparaît donc comme un « gap » à l'ouverture), puis le choc s'estompe linéairement :
après `duree` jours, la part `recuperation` du choc est regagnée. Plusieurs scénarios sur un même actif se multiplient.
Les prix d'origine ne sont jamais modifiés : retirer le scénario restitue les prix de départ."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from ..marche.catalogue import Univers

BENCHMARK = "^GSPC"
CLASSES_CHOC = ("action", "crypto", "matiere")


@dataclass(frozen=True)
class Parametres:
    debut: date
    portee_type: str
    portee_valeurs: tuple[str, ...]
    choc: float
    recuperation: float
    duree: int


def symboles_concernes(univers: Univers, portee_type: str, valeurs) -> set[str]:
    """Actifs touchés. « tous » = les actifs négociables ; l'indice de référence (S&P 500) suit dès que des actions sont visées,
    pour que la comparaison « portefeuille contre marché » reste cohérente. Le VIX n'est jamais modifié."""
    valeurs = set(valeurs or ())
    negociables = [a for a in univers if a.tradable]
    if portee_type == "tous":
        touches = {a.symbole for a in negociables}
    elif portee_type == "classe":
        touches = {a.symbole for a in negociables if a.classe in valeurs}
    elif portee_type == "secteur":
        touches = {a.symbole for a in negociables if a.secteur in valeurs}
    elif portee_type == "actifs":
        touches = {a.symbole for a in negociables if a.symbole in valeurs}
    else:
        raise ValueError(f"portée inconnue : {portee_type}")
    if any(univers[s].classe == "action" for s in touches if s in univers) and BENCHMARK in univers:
        touches.add(BENCHMARK)
    return touches


def multiplicateur(dates: pd.DatetimeIndex, p: Parametres) -> np.ndarray:
    jours = (dates - pd.Timestamp(p.debut)).days.to_numpy()
    avancement = np.clip(jours / p.duree, 0.0, 1.0) if p.duree > 0 else np.zeros(len(dates))
    m = 1.0 + p.choc * (1.0 - p.recuperation * avancement)
    return np.where(jours >= 0, m, 1.0)


def calculer(scenarios: list[Parametres], univers: Univers, series: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    """Multiplicateur journalier de chaque actif touché (produit de tous les scénarios qui le concernent)."""
    sortie: dict[str, pd.Series] = {}
    for p in scenarios:
        for symbole in symboles_concernes(univers, p.portee_type, p.portee_valeurs):
            df = series.get(symbole)
            if df is None or not len(df):
                continue
            m = pd.Series(multiplicateur(df.index, p), index=df.index)
            sortie[symbole] = m if symbole not in sortie else sortie[symbole] * m
    return sortie


def verifier(p: Parametres) -> None:
    """Messages en français affichables tels quels."""
    if not -0.95 <= p.choc <= 3.0 or p.choc == 0:
        raise ValueError("Le choc doit être compris entre −95 % et +300 % et ne pas être nul.")
    if not 0 <= p.recuperation <= 1:
        raise ValueError("La part récupérée doit être comprise entre 0 % et 100 %.")
    if p.recuperation > 0 and p.duree < 1:
        raise ValueError("Pour récupérer une part du choc, indiquez une durée d'au moins 1 jour.")
    if not 0 <= p.duree <= 1825:
        raise ValueError("La durée de récupération doit être comprise entre 0 et 1 825 jours.")
    if p.portee_type not in ("tous", "classe", "secteur", "actifs"):
        raise ValueError("Périmètre inconnu.")
    if p.portee_type != "tous" and not p.portee_valeurs:
        raise ValueError("Choisissez au moins un élément du périmètre.")
    if p.portee_type == "classe" and not set(p.portee_valeurs) <= set(CLASSES_CHOC):
        raise ValueError("Classe inconnue (actions, cryptomonnaies ou matières premières).")
