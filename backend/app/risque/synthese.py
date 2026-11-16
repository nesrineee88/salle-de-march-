"""Synthèse du tableau de bord : niveau de risque global et alertes des règles stop-loss / take-profit. Fonctions pures.

Niveau de risque global (pédagogique, seuils NON réglementaires) : chaque critère reçoit un rang 0 (faible), 1 (modéré)
ou 2 (élevé) et le niveau global est le rang le plus élevé. On retient le pire critère plutôt qu'une moyenne : un
portefeuille à 90 % dans un seul secteur reste dangereux même si sa VaR passée est faible.
Les parts sont mesurées sur la valeur TOTALE du portefeuille (liquidités comprises) : une petite ligne dans un
portefeuille surtout en liquidités n'est pas un risque de concentration.
"""
from __future__ import annotations

from .analyse import LIQUIDITES

# Seuils (fractions). Bornes incluses dans le niveau inférieur : une VaR de 1 % pile reste « faible ».
SEUILS = {
    "var": (0.01, 0.025),                    # VaR historique 95 % à 1 jour, en fraction de la valeur totale
    "concentration_position": (0.25, 0.50),  # part de la plus grosse position dans la valeur totale
    "concentration_secteur": (0.40, 0.60),   # part du plus gros secteur (mêmes seuils que les alertes de la page Portefeuille)
    "baisse": (0.10, 0.20),                  # baisse actuelle depuis le plus haut de la courbe de valeur
}
NIVEAUX = ("faible", "modere", "eleve")
PROXIMITE_ALERTE = 0.05                      # une règle est « proche » si le prix est à 5 % ou moins de son seuil
TYPES_SURVEILLES = ("stop_loss", "take_profit", "stop_suiveur")
RANG_PROFIL = {"ok": 0, "proche": 1, "depasse": 2}


def _rang(valeur: float, seuils: tuple[float, float]) -> int:
    """0 si valeur ≤ seuil bas, 1 si ≤ seuil haut, 2 au-delà."""
    bas, haut = seuils
    return 0 if valeur <= bas else 1 if valeur <= haut else 2


def _plus_grosse_part(lignes: list[dict]) -> dict | None:
    investies = [l for l in lignes if l["libelle"] != LIQUIDITES and l["part"] > 0]
    return max(investies, key=lambda l: l["part"]) if investies else None


def niveau_risque(analyse: dict) -> dict:
    """Niveau global (« aucun » sans position) et critères triés du plus inquiétant au moins inquiétant.

    `analyse` : sortie de risque.analyse.analyser. Un critère incalculable (VaR sans historique suffisant,
    profil non renseigné) est omis : il n'est jamais remplacé par une valeur inventée."""
    positions = [l for l in analyse["repartition"]["position"] if l["libelle"] != LIQUIDITES]
    part_investie = sum(l["part"] for l in positions)
    if part_investie <= 0:
        return {"niveau": "aucun", "criteres": [], "part_investie": 0.0}

    criteres: list[dict] = []
    if analyse.get("risque"):
        v = analyse["risque"]["var"]
        criteres.append({"critere": "var", "rang": _rang(v, SEUILS["var"]), "valeur": v})
    position = _plus_grosse_part(analyse["repartition"]["position"])
    if position:
        criteres.append({"critere": "concentration_position", "rang": _rang(position["part"], SEUILS["concentration_position"]),
                         "valeur": position["part"], "libelle": position["libelle"]})
    secteur = _plus_grosse_part(analyse["repartition"]["secteur"])
    if secteur:
        criteres.append({"critere": "concentration_secteur", "rang": _rang(secteur["part"], SEUILS["concentration_secteur"]),
                         "valeur": secteur["part"], "libelle": secteur["libelle"]})
    profil = analyse.get("profil") or {}
    if profil.get("statut") in RANG_PROFIL:
        criteres.append({"critere": "profil", "rang": RANG_PROFIL[profil["statut"]], "valeur": profil.get("perte_actuelle"),
                         "tolerance": profil.get("perte_tolerance")})
    baisse = analyse["performance"]["drawdown_courant"] or 0.0
    criteres.append({"critere": "baisse", "rang": _rang(baisse, SEUILS["baisse"]), "valeur": baisse})

    criteres.sort(key=lambda c: -c["rang"])          # tri stable : l'ordre ci-dessus départage les ex aequo
    return {"niveau": NIVEAUX[criteres[0]["rang"]], "criteres": criteres, "part_investie": part_investie}


def alertes_regles(regles: list[dict], prix: dict[str, float], proximite: float = PROXIMITE_ALERTE) -> dict:
    """Règles de protection actives triées par distance au déclenchement, et dernières règles déclenchées.

    distance = |seuil de déclenchement − prix actuel| / |prix actuel| (fraction ; 0,02 = le prix est à 2 % du seuil).
    `regles` : sortie de GET /regles (champ `niveau` = prix de déclenchement) ; `prix` : symbole -> prix actuel."""
    surveillance = []
    for r in regles:
        p = prix.get(r["symbole"])
        if r["statut"] != "active" or r["type"] not in TYPES_SURVEILLES or r.get("niveau") is None or not p:
            continue
        distance = abs(r["niveau"] - p) / abs(p)
        surveillance.append({"id": r["id"], "symbole": r["symbole"], "type": r["type"], "niveau": r["niveau"], "prix": p,
                             "distance": distance, "proche": distance <= proximite})
    surveillance.sort(key=lambda a: a["distance"])
    declenchees = sorted((r for r in regles if r["statut"] in ("declenchee", "echec") and r.get("declenchee_le")),
                         key=lambda r: r["declenchee_le"], reverse=True)[:5]
    return {
        "surveillance": surveillance,
        "declenchees": [{k: r.get(k) for k in ("id", "symbole", "type", "statut", "declenchee_le", "motif")} for r in declenchees],
    }
