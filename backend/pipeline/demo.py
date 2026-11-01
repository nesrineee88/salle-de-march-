"""Données de DÉMONSTRATION : séries générées au hasard, pour voir l'interface sans accès à Yahoo.

Elles ne correspondent à aucun prix réel et un marqueur (DONNEES_SYNTHETIQUES.txt) fait afficher un
bandeau d'avertissement dans l'interface. Le nettoyage des vraies données supprime ce marqueur.
"""
from __future__ import annotations

import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from app.marche.catalogue import Univers

from .nettoyer import fenetre_brute

VOLATILITE_JOUR = {"action": 0.018, "crypto": 0.04, "matiere": 0.016, "indice": 0.011}
PLAGE_PRIX = {"action": (40, 450), "crypto": (0.05, 30000), "matiere": (4, 2000), "indice": (12, 3000)}
TEXTE_MARQUEUR = (
    "Ces données sont générées au hasard pour la démonstration. Elles ne sont PAS des prix réels.\n"
    "Pour les vraies données : python -m pipeline tout\n"
)


def serie_demo(symbole: str, classe: str, calendrier: str, debut, fin, graine: int) -> pd.DataFrame:
    rng = np.random.default_rng(zlib.crc32(symbole.encode()) ^ graine)
    dates = pd.bdate_range(debut, fin) if calendrier == "semaine" else pd.date_range(debut, fin)
    n = len(dates)
    sigma = VOLATILITE_JOUR[classe]
    bas, haut = PLAGE_PRIX[classe]
    depart = float(np.exp(rng.uniform(np.log(bas), np.log(haut))))
    rendements = rng.normal(0.0003, sigma, n)
    cloture = depart * np.exp(np.cumsum(rendements))
    ouverture = np.concatenate([[depart], cloture[:-1]]) * np.exp(rng.normal(0, sigma * 0.3, n))
    amplitude = np.abs(rng.normal(0, sigma * 0.6, n)) + 1e-4
    plus_haut = np.maximum(ouverture, cloture) * (1 + amplitude)
    plus_bas = np.minimum(ouverture, cloture) * (1 - amplitude)
    volume = np.round(rng.uniform(0.5, 1.5, n) * 1e6)
    return pd.DataFrame(
        {"open": ouverture, "high": plus_haut, "low": plus_bas, "close": cloture, "volume": volume, "corrige": False},
        index=pd.DatetimeIndex(dates, name="date"),
    )


def generer_demo(univers: Univers, dossier_clean: Path, marqueur: Path, graine: int = 2026) -> int:
    dossier_clean.mkdir(parents=True, exist_ok=True)
    debut = fenetre_brute(univers.debut, univers.historique_prealable_jours)
    for actif in univers:
        df = serie_demo(actif.symbole, actif.classe, actif.calendrier, debut, univers.fin, graine)
        df.to_csv(dossier_clean / actif.fichier, index_label="date", float_format="%.10g")
    marqueur.write_text(TEXTE_MARQUEUR, encoding="utf-8")
    return len(univers.actifs)
