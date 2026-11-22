"""Routes de la protection du portefeuille. Lecture seule : rien n'est débité, aucun contrat n'est enregistré."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..contexte import Contexte, acces_bac, instant_compte, obtenir_contexte
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from . import calcul

routeur = APIRouter(prefix="/api/v1/protection")
DUREES = (30, 91, 182)
PERIMETRES = {"portefeuille": None, "crypto": "crypto", "matieres": "matiere", "actions": "action"}


def preparer(ctx: Contexte, bac, t, perimetre: str) -> tuple[dict, dict]:
    """Valeurs détenues et clôtures passées (séances terminées seulement). À appeler sous le verrou du compte."""
    classe = PERIMETRES[perimetre]
    valeurs = {p["symbole"]: p["valeur"] for p in bac.salle.valorisation(bac.compte_id, t)["positions"]
               if p["valeur"] > 0 and ctx.magasin.a_des_donnees(p["symbole"])
               and (classe is None or ctx.univers[p["symbole"]].classe == classe)}
    cours = {s: ctx.magasin.barres_terminees(s, t.date())["close"] for s in valeurs}
    return valeurs, cours


def devis(valeurs: dict, cours: dict, franchise: float, plafond: float, jours: int) -> dict:
    if not valeurs:
        return {"vide": True}
    return {"vide": False, **calcul.tarifer(cours, valeurs, franchise, plafond, jours)}


@routeur.get("/devis")
def lire_devis(perimetre: Literal["portefeuille", "crypto", "matieres", "actions"] = "portefeuille",
               franchise: float = Query(0.10, ge=0.02, le=0.30), plafond: float = Query(0.25, ge=0.05, le=0.50),
               jours: int = Query(91),
               ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    if jours not in DUREES:
        raise HTTPException(422, "Durée possible : 30, 91 ou 182 jours.")
    with acces_bac(ctx, u) as (bac, t):
        t = instant_compte(bac, t)
        valeurs, cours = preparer(ctx, bac, t, perimetre)
    try:
        r = devis(valeurs, cours, franchise, plafond, jours)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {"instant": t.isoformat(timespec="seconds"), "perimetre": perimetre, **r,
            "noms": {s: ctx.univers[s].nom for s in valeurs}}
