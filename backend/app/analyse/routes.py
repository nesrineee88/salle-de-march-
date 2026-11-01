"""Route des indicateurs techniques d'un actif, à la date simulée de l'utilisateur."""
from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..contexte import Contexte, acces_bac, donnees_ou_erreur, obtenir_contexte
from ..marche.stockage import DonneeIndisponible
from ..trading.carnet import FRAIS_BPS, SPREAD_BPS
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from . import backtest as bt
from .indicateurs import PARAMETRES, calculer_tout

routeur = APIRouter(prefix="/api/v1")
CHAUFFE = 300      # bougies supplémentaires lues avant le début du graphique, pour que les indicateurs soient déjà « chauds »


@routeur.get("/indicateurs/{symbole:path}")
def indicateurs(symbole: str, barres: int = Query(250, ge=1, le=2000),
                ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    """Séries alignées sur les bougies de /historique : `dates[i]` correspond à `series[nom][i]`. Valeur absente = null."""
    donnees_ou_erreur(ctx, symbole)
    with acces_bac(ctx, u) as (_bac, t):
        try:
            lues = ctx.moteur.historique(symbole, t, barres + CHAUFFE)
        except DonneeIndisponible as exc:
            raise HTTPException(409, str(exc)) from None
    if not lues:
        return {"symbole": symbole, "dates": [], "series": {}, "parametres": PARAMETRES}
    tout = calculer_tout(lues)
    return {
        "symbole": symbole,
        "dates": [b["date"] for b in lues][-barres:],
        "series": {nom: valeurs[-barres:] for nom, valeurs in tout.items()},
        "parametres": PARAMETRES,
    }


# ------------------------------------------------------------------ backtesting
class CorpsStrategie(BaseModel):
    nom: str = Field(max_length=40)
    parametres: dict[str, float] = Field(default_factory=dict)


class CorpsBacktest(BaseModel):
    symbole: str = Field(max_length=20)
    strategies: list[CorpsStrategie] = Field(min_length=1, max_length=8)
    debut: date | None = None
    cout_bps: float | None = Field(None, ge=0, le=200, description="Coût par côté, en points de base (défaut : frais plus demi-écart du marché)")


@routeur.get("/backtest/strategies")
def liste_strategies(u: Utilisateur = Depends(exiger("marche.lire"))):
    return [{"nom": s.nom, "libelle": s.libelle, "description": s.description, "parametres": s.parametres}
            for s in bt.CATALOGUE.values()]


@routeur.post("/backtest")
def lancer_backtest(corps: CorpsBacktest, ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    """Compare des stratégies sur l'historique PASSÉ de l'actif (jamais au-delà de la date simulée de l'utilisateur)."""
    donnees_ou_erreur(ctx, corps.symbole)
    actif = ctx.univers[corps.symbole]
    if not actif.tradable:
        raise HTTPException(422, "Cet indice sert de référence : choisissez un actif négociable.")
    with acces_bac(ctx, u) as (_bac, t):
        df = ctx.magasin.barres_terminees(corps.symbole, t.date())
    debut = pd.Timestamp(corps.debut or ctx.univers.debut)
    if len(df) < 30 or debut >= df.index[-1]:
        raise HTTPException(422, "Pas assez d'historique avant la date simulée : avancez dans le temps ou choisissez un début plus ancien.")
    cout = corps.cout_bps if corps.cout_bps is not None else FRAIS_BPS[actif.classe] + SPREAD_BPS[actif.classe] / 2
    noms = [x.nom for x in corps.strategies]
    if len(set(noms)) != len(noms):
        raise HTTPException(422, "Une stratégie ne peut être choisie qu'une fois.")
    demandees = [(x.nom, x.parametres) for x in corps.strategies]
    if "achat_conservation" not in noms:
        demandees.insert(0, ("achat_conservation", {}))                 # la référence est toujours calculée
    sortie = []
    for nom, params in demandees:
        try:
            r = bt.executer(df, nom, params, cout, debut)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        sortie.append({"nom": nom, "libelle": bt.CATALOGUE[nom].libelle, "description": bt.CATALOGUE[nom].description,
                       "parametres": {**bt.CATALOGUE[nom].parametres, **params}, **r})
    premiere = sortie[0]["courbe"]["dates"]
    avertissements = ["Le passé ne prédit pas l'avenir : un bon résultat passé n'est pas une promesse."]
    if len(sortie) > 2:
        avertissements.append(
            f"Vous comparez {len(sortie) - 1} stratégies sur le même historique : la meilleure peut l'être par simple chance. "
            "Regardez si elle l'est aussi sur les deux moitiés de la période.")
    if premiere and (date.fromisoformat(premiere[-1]) - date.fromisoformat(premiere[0])).days < 365:
        avertissements.append("Période de moins d'un an : les ratios annualisés sont peu fiables.")
    if actif.classe == "action":
        avertissements.append("Prix ajustés des dividendes et des divisions d'actions (source Yahoo Finance).")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        avertissements.append("Cet actif a eu des prix négatifs ou nuls : les rendements sont calculés sur la valeur absolue du prix précédent et les résultats sont à prendre avec prudence.")
    return {
        "symbole": corps.symbole, "debut": premiere[0] if premiere else None, "fin": premiere[-1] if premiere else None,
        "cout_bps": cout, "reference": "achat_conservation", "strategies": sortie, "avertissements": avertissements,
    }
