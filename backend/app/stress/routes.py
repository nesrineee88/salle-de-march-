"""Routes du test de résistance des banques (conventionnelles et islamiques) aux chocs sur les matières premières."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..contexte import Contexte, obtenir_contexte
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from . import historique, ia, modele

routeur = APIRouter(prefix="/api/v1/stress")


@routeur.get("/banques")
def banques(_u: Utilisateur = Depends(exiger("marche.lire"))):
    return {"banques": [b.en_dict() for b in modele.panel_synthetique()], "groupes": [{"cle": g, "libelle": modele.LIBELLE_GROUPES[g]} for g in modele.GROUPES],
            "seuil_minimum": modele.SEUIL_MINIMUM, "seuil_coussin": modele.SEUIL_COUSSIN,
            "avertissement": "Banques INVENTÉES (synthétiques), aux profils plausibles : ce ne sont pas de vraies banques. Paramètres pédagogiques à valider avec l'encadrant."}


@routeur.get("/chocs-historiques")
def chocs_hist(ctx: Contexte = Depends(obtenir_contexte), _u: Utilisateur = Depends(exiger("marche.lire"))):
    return {"fenetres": historique.chocs_historiques(ctx.magasin), "symboles": historique.SYMBOLES,
            "note": "Chocs mesurés sur les prix d'origine du simulateur (hors crises injectées)."}


class CorpsStress(BaseModel):
    banque: dict = Field(default_factory=dict)
    chocs: dict = Field(default_factory=dict)


def _preparer(corps: CorpsStress):
    try:
        return modele.valider_banque(corps.banque), modele.valider_chocs(corps.chocs)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from None


@routeur.post("/simuler")
def simuler(corps: CorpsStress, _u: Utilisateur = Depends(exiger("marche.lire"))):
    b, chocs = _preparer(corps)
    return modele.stresser(b, chocs)


@routeur.post("/comparer")
def comparer(corps: CorpsStress, _u: Utilisateur = Depends(exiger("marche.lire"))):
    """Même choc appliqué à toutes les banques du panel synthétique, classées de la plus touchée à la moins touchée."""
    _b, chocs = _preparer(CorpsStress(banque={}, chocs=corps.chocs))
    lignes = []
    for b in modele.panel_synthetique():
        r = modele.stresser(b, chocs)
        lignes.append({k: r[k] for k in ("banque", "type", "ratio_avant", "ratio_apres", "variation_points", "statut")})
    lignes.sort(key=lambda x: x["variation_points"])
    par_type = {}
    for t in ("conventionnelle", "islamique"):
        v = [x["variation_points"] for x in lignes if x["type"] == t]
        par_type[t] = {"nb": len(v), "variation_moyenne": sum(v) / len(v), "pire": min(v)}
    return {"banques": lignes, "par_type": par_type, "chocs": chocs}


@routeur.post("/inverse")
def inverse(corps: CorpsStress, _u: Utilisateur = Depends(exiger("marche.lire"))):
    b, _ = _preparer(CorpsStress(banque=corps.banque, chocs={}))
    return {"minimum": modele.choc_inverse(b, modele.SEUIL_MINIMUM), "coussin": modele.choc_inverse(b, modele.SEUIL_COUSSIN)}


@routeur.post("/ia/comparaison")
def ia_comparaison(_u: Utilisateur = Depends(exiger("ia.utiliser"))):
    try:
        r = ia.entrainer()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None
    return {k: v for k, v in r.items() if not k.startswith("_")} | {
        "avertissement": "Les modèles apprennent à reproduire le modèle structurel sur des banques et des chocs tirés au hasard (données inventées) : ils ne remplacent pas le modèle structurel, qui reste la référence."}


class CorpsExplication(CorpsStress):
    modele: str = "boost"


@routeur.post("/ia/explication")
def ia_explication(corps: CorpsExplication, _u: Utilisateur = Depends(exiger("ia.utiliser"))):
    b, chocs = _preparer(corps)
    try:
        return ia.expliquer(b, chocs, corps.modele)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
