"""Chocs de matières premières mesurés sur les VRAIES séries du simulateur (jamais inventés)."""
from __future__ import annotations

from datetime import date

import numpy as np

from ..marche.stockage import Magasin

SYMBOLES = {
    "energie": ["CL=F", "BZ=F", "NG=F"],
    "metaux_precieux": ["GC=F", "SI=F", "PL=F"],
    "metaux_industriels": ["HG=F"],
    "agricole": ["ZW=F", "ZC=F", "ZS=F", "KC=F"],
}
FENETRES = [
    {"cle": "petrole_2018", "nom": "Chute du pétrole, octobre à décembre 2018", "debut": date(2018, 10, 3), "fin": date(2018, 12, 24)},
    {"cle": "covid_2020", "nom": "Début du Covid-19, février à avril 2020", "debut": date(2020, 2, 19), "fin": date(2020, 4, 30)},
    {"cle": "ukraine_2022", "nom": "Invasion de l'Ukraine, février à juin 2022", "debut": date(2022, 2, 23), "fin": date(2022, 6, 30)},
]


def choc_groupe(magasin: Magasin, symboles: list[str], debut: date, fin: date) -> tuple[float | None, list[str]]:
    """Plus forte variation (en valeur absolue) du prix depuis le début de la fenêtre, moyennée sur les symboles disponibles.
    Les prix négatifs ou nuls (pétrole WTI en avril 2020) sont ignorés : le rendement relatif n'y a pas de sens."""
    valeurs, utilises = [], []
    for s in symboles:
        if not magasin.a_des_donnees(s):
            continue
        df = magasin.prix_origine(s)
        w = df.loc[str(debut):str(fin), "close"]
        if len(w) < 5 or w.iloc[0] <= 0:
            continue
        rel = (w[w > 0] / w.iloc[0] - 1).to_numpy()
        valeurs.append(float(rel[np.argmax(np.abs(rel))]))
        utilises.append(s)
    return (float(np.mean(valeurs)) if valeurs else None), utilises


def chocs_historiques(magasin: Magasin) -> list[dict]:
    sortie = []
    for f in FENETRES:
        chocs, notes = {}, []
        for g, symboles in SYMBOLES.items():
            v, utilises = choc_groupe(magasin, symboles, f["debut"], f["fin"])
            chocs[g] = round(v, 4) if v is not None else None
            if v is None:
                notes.append(f"Aucune donnée pour {g} sur cette période.")
        sortie.append({"cle": f["cle"], "nom": f["nom"], "debut": f["debut"].isoformat(), "fin": f["fin"].isoformat(), "chocs": chocs, "notes": notes})
    return sortie
