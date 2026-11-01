"""Routes IA : prédiction, anomalies, régimes, optimiseur de portefeuille, agent. Toutes à la date simulée de l'utilisateur, sur le passé seulement."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from ..contexte import Contexte, acces_bac, donnees_ou_erreur, obtenir_contexte
from ..trading.carnet import FRAIS_BPS, SPREAD_BPS
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from . import analyses

routeur = APIRouter(prefix="/api/v1/ia")


def _passe(ctx: Contexte, u: Utilisateur, symbole: str) -> tuple[pd.DataFrame, object]:
    donnees_ou_erreur(ctx, symbole)
    if not ctx.univers[symbole].tradable:
        raise HTTPException(422, "Cet indice sert de référence : choisissez un actif négociable.")
    with acces_bac(ctx, u) as (_bac, t):
        return ctx.magasin.barres_terminees(symbole, t.date()), t


def _executer(f, *args, **kw):
    try:
        return f(*args, **kw)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None


@routeur.get("/predire/{symbole:path}")
def predire(symbole: str, ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("ia.utiliser"))):
    df, t = _passe(ctx, u, symbole)
    return {"symbole": symbole, "instant": t.isoformat(timespec="seconds"), **_executer(analyses.predire, df)}


@routeur.get("/anomalies/{symbole:path}")
def anomalies(symbole: str, seuil: float = Query(4.0, ge=2.0, le=10.0), ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("ia.utiliser"))):
    df, _t = _passe(ctx, u, symbole)
    return {"symbole": symbole, **_executer(analyses.anomalies, df, seuil=seuil)}


@routeur.get("/regimes/{symbole:path}")
def regimes(symbole: str, ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("ia.utiliser"))):
    df, _t = _passe(ctx, u, symbole)
    return {"symbole": symbole, **_executer(analyses.regimes, df)}


@routeur.get("/agent/{symbole:path}")
def agent(symbole: str, ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("ia.utiliser"))):
    df, _t = _passe(ctx, u, symbole)
    classe = ctx.univers[symbole].classe
    return {"symbole": symbole, **_executer(analyses.agent, df, cout_bps=FRAIS_BPS[classe] + SPREAD_BPS[classe] / 2)}


@routeur.get("/optimiser")
def optimiser(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("ia.utiliser"))):
    with acces_bac(ctx, u) as (bac, t):
        positions = [p for p in bac.salle.valorisation(bac.compte_id, t)["positions"] if p["valeur"] > 0 and ctx.magasin.a_des_donnees(p["symbole"])]
        series = {p["symbole"]: ctx.magasin.barres_terminees(p["symbole"], t.date(), n=251)["close"] for p in positions}
    if len(positions) < 2:
        raise HTTPException(422, "Il faut au moins deux positions ouvertes pour comparer des répartitions : achetez deux actifs, puis revenez.")
    retours = pd.DataFrame({s: v.pct_change() for s, v in series.items()})
    total = sum(p["valeur"] for p in positions)
    return _executer(analyses.optimiser, retours, {p["symbole"]: p["valeur"] / total for p in positions})
