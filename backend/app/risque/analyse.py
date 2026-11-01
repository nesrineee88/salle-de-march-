"""Analyse complète d'un portefeuille à un instant simulé : assemble les indicateurs purs."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from . import indicateurs as ind

LIBELLE_MARCHE = {"action": "Actions", "crypto": "Cryptomonnaies", "matiere": "Matières premières", "indice": "Indices"}
LIQUIDITES = "Liquidités"


def _repartition(valo: dict, catalogue: dict[str, tuple[str, str]], cle: str) -> list[dict]:
    """Parts de la valeur totale : par marché, par secteur ou par position, liquidités comprises."""
    equity = valo["equity"]
    if not equity:
        return []
    parts: dict[str, float] = {}
    for p in valo["positions"]:
        classe, secteur = catalogue.get(p["symbole"], ("?", "?"))
        nom = {"marche": LIBELLE_MARCHE.get(classe, classe), "secteur": secteur, "position": p["symbole"]}[cle]
        parts[nom] = parts.get(nom, 0.0) + p["valeur"] / equity
    parts[LIQUIDITES] = valo["cash"] / equity
    return sorted(({"libelle": k, "part": v} for k, v in parts.items() if abs(v) > 1e-9), key=lambda x: -x["part"])


def analyser(valo: dict, historique: list[dict], series_prix: dict[str, pd.Series],
             catalogue: dict[str, tuple[str, str]], profil: dict | None) -> dict:
    """`valo` : sortie de SalleDeMarche.valorisation ; `historique` : points de valeur jusqu'à maintenant ;
    `series_prix` : clôtures passées de chaque actif détenu (jamais le futur) ; `catalogue` : symbole -> (classe, secteur)."""
    avertissements: list[str] = []
    equity = valo["equity"]
    positions = valo["positions"]

    # Courbe de valeur : drawdown et statistiques
    points = [(datetime.fromisoformat(p["instant"]), p["equity"]) for p in historique]
    valeurs = [v for _, v in points] or [equity]
    dd = ind.drawdown(valeurs)
    stats = ind.statistiques_courbe(points)
    if stats is None:
        avertissements.append(
            f"Volatilité, Sharpe et Sortino demandent au moins {ind.MIN_POINTS_COURBE} points de valeur : "
            "avancez dans le temps en gardant des positions.")

    # Risque du portefeuille actuel sur le passé des actifs détenus
    poids = {p["symbole"]: p["valeur"] / equity for p in positions} if equity else {}
    risque = None
    correlations = None
    if poids:
        retours = ind.rendements_actifs({s: series_prix[s] for s in poids if s in series_prix})
        serie = ind.rendements_portefeuille(poids, retours)
        risque = ind.var_cvar(serie)
        if risque is None:
            avertissements.append(f"VaR et CVaR demandent au moins {ind.MIN_JOURS_VAR} jours d'historique commun aux actifs détenus.")
        else:
            risque["var_montant"] = risque["var"] * equity
            risque["cvar_montant"] = risque["cvar"] * equity
        if len(retours.columns) >= 2 and len(retours) >= ind.MIN_JOURS_VAR:
            c = retours.corr()
            correlations = {"symboles": list(c.columns), "matrice": [[float(x) for x in ligne] for ligne in c.to_numpy()]}
    else:
        avertissements.append("Aucune position : les indicateurs de risque apparaîtront après un premier achat.")

    # Concentration et diversification (positions investies, liquidités exclues)
    conc = ind.concentration({p["symbole"]: p["valeur"] for p in positions})
    marches = {catalogue.get(p["symbole"], ("?", "?"))[0] for p in positions}
    diversification = None
    if conc is not None:
        diversification = {"score": ind.score_diversification(conc["hhi"], len(marches)),
                           "nb_positions": len(positions), "nb_marches": len(marches)}

    return {
        "instant": valo["instant"],
        "performance": {
            "rendement_total": equity / valo["capital_initial"] - 1 if valo["capital_initial"] else None,
            "drawdown_max": dd["max"], "drawdown_courant": dd["courant"], "points_courbe": len(points),
            **(stats or {"volatilite_annuelle": None, "rendement_annuel": None, "sharpe": None, "sortino": None}),
        },
        "risque": risque,
        "concentration": conc,
        "diversification": diversification,
        "repartition": {cle: _repartition(valo, catalogue, cle) for cle in ("marche", "secteur", "position")},
        "correlations": correlations,
        "profil": ind.comparer_profil(profil, dd["courant"], risque["var"] if risque else None),
        "avertissements": avertissements,
    }
