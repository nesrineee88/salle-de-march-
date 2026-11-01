"""Routes du mode Direct (bêta)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import config
from ..contexte import Contexte, acces_bac, obtenir_contexte
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from . import fournisseur

routeur = APIRouter(prefix="/api/v1/direct")

# Remplaçable dans les tests par un faux flux.
telechargeur_actuel = fournisseur.telechargeur_yahoo

AVERTISSEMENTS = [
    "Version bêta : le flux Yahoo Finance est non officiel et peut s'interrompre ou être limité.",
    "Les cours des actions américaines sont généralement différés d'environ 15 minutes.",
    "Les heures d'ouverture des actions sont fixes (14 h 30 à 21 h UTC) : elles sont décalées d'une heure pendant l'heure d'été américaine.",
    "Les crises injectées par l'administrateur ne s'appliquent pas aux prix en direct.",
    "Le mode Direct n'est pas conservé au redémarrage du serveur : vous reviendrez dans la période rejouée.",
]


def _fournisseur(ctx: Contexte) -> fournisseur.FournisseurDirect:
    if ctx.direct is None:
        if config.DIRECT_DEMO:
            f = fournisseur.FournisseurDirect(ctx.magasin, ctx.moteur, ctx.univers, fournisseur.flux_demonstration(ctx.magasin))
            f.demo = True
        else:
            f = fournisseur.FournisseurDirect(ctx.magasin, ctx.moteur, ctx.univers, lambda symboles: telechargeur_actuel(symboles))
        ctx.direct = f
    return ctx.direct                                                    # type: ignore[return-value]


@routeur.get("/etat")
def etat(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    bac = ctx.bac(u.id)
    avertissements = (["FLUX DE DÉMONSTRATION : les prix sont inventés (SDM_DIRECT_DEMO=1), ce ne sont pas de vrais cours."] if config.DIRECT_DEMO else []) + AVERTISSEMENTS
    return {"disponible": config.DIRECT_ACTIF, "actif": bac.direct, "beta": True, "demo": config.DIRECT_DEMO, "avertissements": avertissements,
            "flux": ctx.direct.etat() if ctx.direct is not None else None}


@routeur.post("/activer")
def activer(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    if not config.DIRECT_ACTIF:
        raise HTTPException(403, "Le mode Direct est désactivé sur ce serveur (SDM_DIRECT=0).")
    flux = _fournisseur(ctx)
    ancien = flux.derniere_maj
    if ancien is None or flux.etat()["age_secondes"] is None or flux.etat()["age_secondes"] > fournisseur.INTERVALLE_S:
        flux.rafraichir()
    if not ctx.magasin.a_du_direct():
        raise HTTPException(503, f"Les prix en direct sont indisponibles ({flux.erreur or 'aucune réponse'}). "
                                 "Vérifiez que le serveur a accès à Internet (Yahoo Finance), puis réessayez.")
    from ..contexte import maintenant_utc
    with acces_bac(ctx, u) as (bac, _t):
        bac.direct = True
        bac.horloge.regler_facteur(1.0)
        bac.horloge.aller_a(maintenant_utc())
        bac.horloge.reprendre()
    flux.inscrire(u.id)
    return {"actif": True, "flux": flux.etat(), "avertissements": AVERTISSEMENTS}


@routeur.post("/quitter")
def quitter(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    with acces_bac(ctx, u) as (bac, _t):
        bac.direct = False
        bac.horloge.aller_a(ctx.fin_simulation)
        bac.horloge.pause()
    if ctx.direct is not None:
        ctx.direct.retirer(u.id)
    return {"actif": False}
