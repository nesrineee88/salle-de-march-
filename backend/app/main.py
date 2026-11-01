"""API du simulateur : marché, horloge, trading, portefeuille et utilisateurs.

Chaque utilisateur dispose de son propre bac à sable : sa propre horloge de replay, son propre
compte et ses propres ordres (décision D6), enregistrés en base (D18). Les données de marché,
elles, sont partagées en lecture seule.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, time
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import config
from .analyse.routes import routeur as routeur_analyse
from .direct.routes import routeur as routeur_direct
from .credit.routes import routeur as routeur_credit
from .formation.routes import routeur as routeur_formation
from .ia.routes import routeur as routeur_ia
from .stress.routes import routeur as routeur_stress
from .actuariat.routes import routeur as routeur_actuariat
from .contexte import Bac, Contexte, acces_bac, donnees_ou_erreur as _donnees_ou_503, obtenir_contexte  # noqa: F401  (ré-exportés pour les tests)
from .marche.horloge import FACTEURS_PREDEFINIS
from .marche.stockage import DonneeIndisponible
from .routes_admin_stats import routeur as routeur_admin_stats
from .routes_portefeuille import routeur as routeur_portefeuille
from .routes_regles import routeur as routeur_regles
from .scenarios.routes import routeur as routeur_scenarios
from .trading.salle import ordre_en_dict
from .utilisateurs.modeles import Utilisateur
from .utilisateurs.routes import exiger, routeur as routeur_utilisateurs
from .utilisateurs.service import ErreurMetier

app = FastAPI(title="Simulateur de salle de marché — API", version="0.2.0")
app.include_router(routeur_utilisateurs)
app.include_router(routeur_portefeuille)
app.include_router(routeur_analyse)
app.include_router(routeur_regles)
app.include_router(routeur_scenarios)
app.include_router(routeur_direct)
app.include_router(routeur_credit)
app.include_router(routeur_stress)
app.include_router(routeur_formation)
app.include_router(routeur_ia)
app.include_router(routeur_admin_stats)
app.include_router(routeur_actuariat)


@app.exception_handler(ErreurMetier)
async def gerer_erreur_metier(_requete: Request, exc: ErreurMetier):
    return JSONResponse(status_code=exc.statut, content={"detail": exc.message, "code": exc.code})


# ----------------------------------------------------------------------------- public
@app.get("/api/v1/sante")
def sante(ctx: Contexte = Depends(obtenir_contexte)):
    manquants = sorted(set(ctx.univers.actifs) - ctx.magasin.disponibles())
    return {"statut": "ok" if not manquants else "donnees_incompletes",
            "actifs_charges": len(ctx.magasin.disponibles()), "actifs_manquants": manquants}


# ----------------------------------------------------------------------------- marché (lecture)
@app.get("/api/v1/actifs")
def actifs(ctx: Contexte = Depends(obtenir_contexte), _u: Utilisateur = Depends(exiger("marche.lire"))):
    sortie = []
    for a in ctx.univers:
        entree = {"symbole": a.symbole, "nom": a.nom, "classe": a.classe, "secteur": a.secteur,
                  "devise": a.devise, "calendrier": a.calendrier, "tradable": a.tradable,
                  "disponible": ctx.magasin.a_des_donnees(a.symbole)}
        if entree["disponible"]:
            debut, fin = ctx.magasin.periode(a.symbole)
            entree["premiere_cotation"], entree["derniere_cotation"] = debut.isoformat(), fin.isoformat()
        sortie.append(entree)
    return sortie


@app.get("/api/v1/cotations/{symbole:path}")
def cotation(symbole: str, ctx: Contexte = Depends(obtenir_contexte),
             u: Utilisateur = Depends(exiger("marche.lire"))):
    _donnees_ou_503(ctx, symbole)
    with acces_bac(ctx, u) as (_bac, t):
        try:
            c = ctx.moteur.cotation(symbole, t)
        except DonneeIndisponible as exc:
            raise HTTPException(409, str(exc)) from None
    sortie = asdict(c)
    sortie["horodatage"] = c.horodatage.isoformat(timespec="seconds")
    return sortie


@app.get("/api/v1/historique/{symbole:path}")
def historique(symbole: str, barres: int = Query(250, ge=1, le=2000),
               ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    _donnees_ou_503(ctx, symbole)
    with acces_bac(ctx, u) as (_bac, t):
        try:
            return ctx.moteur.historique(symbole, t, barres)
        except DonneeIndisponible as exc:
            raise HTTPException(409, str(exc)) from None


@app.get("/api/v1/carnet/{symbole:path}")
def carnet(symbole: str, ctx: Contexte = Depends(obtenir_contexte),
           u: Utilisateur = Depends(exiger("marche.lire"))):
    _donnees_ou_503(ctx, symbole)
    with acces_bac(ctx, u) as (bac, t):
        try:
            c, statut = bac.salle.carnet(symbole, t)
        except DonneeIndisponible as exc:
            raise HTTPException(409, str(exc)) from None
    return {**c.en_dict(), "statut_marche": statut}


@app.get("/api/v1/marche/instantane")
def instantane(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    """Une seule requête pour l'écran de marché : horloge, fenêtre de simulation et cotation de tous les actifs."""
    with acces_bac(ctx, u) as (bac, t):
        cotations = []
        for symbole in sorted(ctx.magasin.disponibles()):
            try:
                c = ctx.moteur.cotation(symbole, t)
            except DonneeIndisponible:
                continue                               # l'actif ne cote pas encore à cette date
            cotations.append({"symbole": symbole, "prix": c.prix, "statut": c.statut, "origine": c.origine,
                              "derniere_cloture": c.derniere_cloture, "reference": c.reference_variation})
        horloge = {**bac.horloge.etat(), "facteurs_predefinis": FACTEURS_PREDEFINIS}
        en_direct = bac.direct
    return {
        "instant": t.isoformat(timespec="seconds"),
        "direct": en_direct,
        "direct_flux": ctx.direct.etat() if (en_direct and ctx.direct is not None) else None,
        "termine": t >= ctx.fin_simulation and not en_direct,   # la période rejouée est finie : le temps est arrêté
        "horloge": horloge,
        "fenetre": {"debut": ctx.univers.debut.isoformat(), "fin": ctx.univers.fin.isoformat()},
        "cotations": cotations,
        "synthetiques": config.MARQUEUR_SYNTHETIQUE.exists(),     # données de démonstration, pas de vrais prix
    }


# ----------------------------------------------------------------------------- horloge personnelle
@app.get("/api/v1/horloge")
def lire_horloge(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    bac = ctx.bac(u.id)
    with bac.verrou:
        return {**bac.horloge.etat(), "facteurs_predefinis": FACTEURS_PREDEFINIS}


def _refuser_en_direct(bac: Bac) -> None:
    if bac.direct:
        raise HTTPException(409, "Le mode Direct suit l'heure réelle : quittez le mode Direct pour piloter le temps.")


@app.post("/api/v1/horloge/pause")
def mettre_en_pause(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    with acces_bac(ctx, u) as (bac, _t):
        _refuser_en_direct(bac)
        bac.horloge.pause()
        return bac.horloge.etat()


@app.post("/api/v1/horloge/reprendre")
def reprendre(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    with acces_bac(ctx, u) as (bac, _t):
        _refuser_en_direct(bac)
        bac.horloge.reprendre()
        return bac.horloge.etat()


class CorpsFacteur(BaseModel):
    facteur: float = Field(gt=0, le=1_000_000, allow_inf_nan=False)


@app.post("/api/v1/horloge/facteur")
def regler_facteur(corps: CorpsFacteur, ctx: Contexte = Depends(obtenir_contexte),
                   u: Utilisateur = Depends(exiger("marche.lire"))):
    with acces_bac(ctx, u) as (bac, _t):
        _refuser_en_direct(bac)
        bac.horloge.regler_facteur(corps.facteur)
        return bac.horloge.etat()


class CorpsAllerA(BaseModel):
    instant: datetime


@app.post("/api/v1/horloge/aller-a")
def aller_a(corps: CorpsAllerA, ctx: Contexte = Depends(obtenir_contexte),
            u: Utilisateur = Depends(exiger("marche.lire"))):
    instant = corps.instant.replace(tzinfo=None)
    debut = datetime.combine(ctx.univers.debut, time(0, 0))
    fin = datetime.combine(ctx.univers.fin, time(23, 59, 59))
    if not (debut <= instant <= fin):
        raise HTTPException(422, f"L'instant doit être entre {debut.isoformat()} et {fin.isoformat()}.")
    with acces_bac(ctx, u) as (bac, _t):
        _refuser_en_direct(bac)
        bac.horloge.aller_a(instant)
        bac.salle.avancer(instant)        # les ordres en attente sont évalués jusqu'à la destination
        return bac.horloge.etat()


# ----------------------------------------------------------------------------- trading
class CorpsOrdre(BaseModel):
    symbole: str
    sens: Literal["achat", "vente"]
    quantite: float = Field(gt=0, allow_inf_nan=False)
    type: Literal["marche", "limite", "stop"] = "marche"
    prix_limite: float | None = Field(None, allow_inf_nan=False)
    prix_stop: float | None = Field(None, allow_inf_nan=False)


@app.post("/api/v1/ordres", status_code=201)
def passer_ordre(corps: CorpsOrdre, ctx: Contexte = Depends(obtenir_contexte),
                 u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    """Un ordre refusé pour une raison métier est renvoyé avec statut « rejete » et son motif."""
    with acces_bac(ctx, u) as (bac, t):
        ordre = bac.salle.passer_ordre(
            bac.compte_id, corps.symbole, corps.sens, corps.quantite, t,
            type=corps.type, prix_limite=corps.prix_limite, prix_stop=corps.prix_stop)
        return ordre_en_dict(ordre)


@app.get("/api/v1/ordres")
def lister_ordres(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    with acces_bac(ctx, u) as (bac, _t):
        return [ordre_en_dict(o) for o in bac.salle.compte(bac.compte_id).ordres.values()]


@app.delete("/api/v1/ordres/{ordre_id}")
def annuler_ordre(ordre_id: int, ctx: Contexte = Depends(obtenir_contexte),
                  u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    with acces_bac(ctx, u) as (bac, _t):
        try:
            return ordre_en_dict(bac.salle.annuler_ordre(bac.compte_id, ordre_id))
        except KeyError as exc:
            raise HTTPException(404, str(exc.args[0])) from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None


@app.get("/api/v1/executions")
def executions(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    """Les 200 dernières exécutions, la plus récente en premier."""
    with acces_bac(ctx, u) as (bac, _t):
        recentes = list(bac.salle.compte(bac.compte_id).executions[-200:])
    return [{"ordre_id": e.ordre_id, "symbole": e.symbole, "sens": e.sens, "quantite": e.quantite,
             "prix": e.prix, "frais": e.frais, "instant": e.instant.isoformat(timespec="seconds")}
            for e in reversed(recentes)]


@app.get("/api/v1/portefeuille")
def portefeuille(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    with acces_bac(ctx, u) as (bac, t):
        return bac.salle.valorisation(bac.compte_id, t)


@app.post("/api/v1/bac/reinitialiser")
def reinitialiser_bac(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    """Repart de zéro : capital initial, aucun ordre, horloge au début de la fenêtre et en pause."""
    with ctx.bac(u.id).verrou:
        bac = ctx.reinitialiser(u.id)
        return {"compte_id": bac.compte_id, **bac.horloge.etat()}
