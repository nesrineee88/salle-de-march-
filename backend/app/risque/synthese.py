"""Synthèse du tableau de bord : niveau de risque et alertes des règles stop-loss / take-profit. Fonctions pures.

Niveau de risque (méthode validée le 22/11/2026 ; seuils pédagogiques, NON réglementaires) :
 1. cinq familles, mesurées avec les poids actuels sur les 250 dernières séances communes ;
 2. chacune reçoit une note de 0 à 100 : 100/3 au seuil « modéré », 200/3 au seuil « élevé », linéaire entre les deux ;
 3. score = moyenne pondérée des notes. CVaR et concentration pèsent le plus ; VaR et volatilité répètent en partie la CVaR ;
 4. plancher de sécurité, car une moyenne peut masquer un danger : une note au-dessus de 200/3 donne au moins « modéré »,
    une note de 250/3 ou plus donne « élevé ». Sans lui, 100 % sur une seule action calme serait « modéré ».
Sous 30 séances communes le niveau est « incomplet » : rien n'est inventé, seule la concentration est donnée.
Le profil déclaré ne change pas le risque du portefeuille : c'est une alerte à part (`profil`).
Les parts sont mesurées sur la valeur TOTALE (liquidités comprises) : une petite ligne dans un portefeuille surtout en
liquidités n'est pas un risque de concentration.
"""
from __future__ import annotations

from .analyse import LIQUIDITES

# cle, poids, seuil « modéré », seuil « élevé » (fractions)
FAMILLES = (
    ("volatilite", 0.15, 0.15, 0.30),       # écart-type annualisé
    ("var", 0.15, 0.01, 0.025),             # VaR historique 95 % à 1 jour
    ("cvar", 0.25, 0.015, 0.035),           # perte moyenne des jours pires que la VaR
    ("drawdown", 0.20, 0.10, 0.20),         # pire baisse des poids actuels sur la fenêtre
    ("concentration", 0.25, 0.25, 0.50),    # plus grosse position ; le secteur a ses propres seuils
)
SEUILS_SECTEUR = (0.40, 0.60)               # mêmes seuils que les alertes de la page Portefeuille
NOTE_MODEREE, NOTE_ELEVEE, NOTE_CRITIQUE = 100 / 3, 200 / 3, 250 / 3
EPS = 1e-9
NIVEAUX = ("faible", "modere", "eleve")
PROXIMITE_ALERTE = 0.05                      # une règle est « proche » si le prix est à 5 % ou moins de son seuil
TYPES_SURVEILLES = ("stop_loss", "take_profit", "stop_suiveur")


def noter(valeur: float, bas: float, haut: float) -> float:
    """Note de 0 à 100, linéaire par morceaux ; 100 est atteint à deux fois le seuil élevé."""
    if valeur <= bas:
        x = valeur / bas / 3
    elif valeur <= haut:
        x = 1 / 3 + (valeur - bas) / (haut - bas) / 3
    else:
        x = 2 / 3 + (valeur - haut) / haut / 3
    return 100 * min(1.0, max(0.0, x))


def rang_note(note: float) -> int:
    """0 faible, 1 modéré, 2 élevé. Une note pile au seuil reste dans le niveau inférieur."""
    return 2 if note > NOTE_ELEVEE + EPS else 1 if note > NOTE_MODEREE + EPS else 0


def rang_plancher(note: float) -> int:
    return 2 if note >= NOTE_CRITIQUE - EPS else 1 if note > NOTE_ELEVEE + EPS else 0


def _plus_grosse_part(lignes: list[dict]) -> dict | None:
    investies = [l for l in lignes if l["libelle"] != LIQUIDITES and l["part"] > 0]
    return max(investies, key=lambda l: l["part"]) if investies else None


def niveau_risque(analyse: dict) -> dict:
    """`analyse` : sortie de risque.analyse.analyser. Niveau : aucun, incomplet, faible, modere ou eleve."""
    positions = [l for l in analyse["repartition"]["position"] if l["libelle"] != LIQUIDITES]
    part_investie = sum(l["part"] for l in positions)
    profil = analyse.get("profil") or {}
    sortie = {
        "niveau": "aucun", "score": None, "niveau_pondere": None, "plancher": None, "familles": [],
        "calcul_complet": True, "part_investie": 0.0, "jours": 0,
        "profil": {"statut": profil.get("statut", "profil_absent"), "perte_actuelle": profil.get("perte_actuelle"),
                   "tolerance": profil.get("perte_tolerance")},
    }
    if part_investie <= 0:
        return sortie

    r = analyse.get("risque") or {}
    valeurs = {"volatilite": r.get("volatilite_annuelle_seances"), "var": r.get("var"), "cvar": r.get("cvar"),
               "drawdown": r.get("drawdown_poids")}
    position = _plus_grosse_part(analyse["repartition"]["position"])
    secteur = _plus_grosse_part(analyse["repartition"]["secteur"])
    familles = []
    for cle, poids, bas, haut in FAMILLES:
        ligne = {"cle": cle, "poids": poids, "seuil_modere": bas, "seuil_eleve": haut}
        if cle == "concentration":
            candidats = [(noter(p["part"], *seuils), nature, p, seuils)
                         for nature, p, seuils in (("position", position, (bas, haut)), ("secteur", secteur, SEUILS_SECTEUR)) if p]
            note, nature, part, seuils = max(candidats, key=lambda c: c[0])
            ligne.update(valeur=part["part"], libelle=part["libelle"], nature=nature, seuil_modere=seuils[0], seuil_eleve=seuils[1])
        else:
            valeur = valeurs[cle]
            ligne["valeur"] = valeur
            note = noter(valeur, bas, haut) if valeur is not None else None
        ligne.update(note=note, rang=rang_note(note) if note is not None else None,
                     points=note * poids if note is not None else None)
        familles.append(ligne)

    pire = max((f for f in familles if f["note"] is not None), key=lambda f: f["note"])
    plancher = rang_plancher(pire["note"])
    complet = all(f["note"] is not None for f in familles)
    sortie.update(familles=familles, part_investie=part_investie, calcul_complet=complet, jours=r.get("jours", 0),
                  plancher={"niveau": NIVEAUX[plancher], "cle": pire["cle"], "note": pire["note"], "releve": False})
    if not complet:
        sortie["niveau"] = "incomplet"
        return sortie
    score = sum(f["points"] for f in familles)
    moyenne = rang_note(score)
    sortie["plancher"]["releve"] = plancher > moyenne
    sortie.update(score=score, niveau_pondere=NIVEAUX[moyenne], niveau=NIVEAUX[max(moyenne, plancher)])
    return sortie


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
