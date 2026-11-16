"""Route des indicateurs techniques d'un actif, à la date simulée de l'utilisateur."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..contexte import Contexte, acces_bac, donnees_ou_erreur, obtenir_contexte
from ..marche.stockage import DonneeIndisponible
from ..trading.carnet import FRAIS_BPS, SPREAD_BPS
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from . import backtest as bt
from . import bougies as bg
from . import niveaux as nv
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


@routeur.get("/bougies/{symbole:path}")
def bougies(symbole: str, unite: str = Query("1j", description="1min, 5min, 15min, 1h ou 1j"), barres: int = Query(300, ge=1, le=1000),
            ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    """Bougies de l'unité demandée jusqu'à l'instant simulé, avec les indicateurs calculés sur ces mêmes bougies.
    Temps `t` en secondes UTC. En intrajournalier, les bougies viennent des ticks simulés (voir analyse/bougies.py)."""
    if unite not in bg.UNITES:
        raise HTTPException(422, f"Unité inconnue : {unite}. Choisir parmi {', '.join(bg.UNITES)}.")
    donnees_ou_erreur(ctx, symbole)
    actif = ctx.univers[symbole]
    total = barres + CHAUFFE                                  # bougies de « chauffe » pour que les indicateurs soient prêts
    with acces_bac(ctx, u) as (_bac, t):
        try:
            if unite == "1j":
                lues = [{**b, "t": int(bg.secondes(datetime.fromisoformat(b["date"])))} for b in ctx.moteur.historique(symbole, t, total)]
            else:
                duree = bg.duree_seance(actif.session_utc)
                passees = ctx.magasin.barres_terminees(symbole, t.date(), n=bg.nb_seances_utiles(bg.UNITES[unite], total, duree))
                jours = [d.date() for d in passees.index] + [t.date()]
                lues = bg.bougies_intraday(ctx.moteur, symbole, jours, t, bg.UNITES[unite], total)
        except DonneeIndisponible as exc:
            raise HTTPException(409, str(exc)) from None
    tout = calculer_tout(lues) if lues else {}
    sortie = [{k: b[k] for k in ("t", "open", "high", "low", "close", "volume", "en_formation")} for b in lues[-barres:]]
    return {
        "symbole": symbole, "unite": unite, "intrajournalier": unite != "1j",
        "pas_ticks_s": bg.duree_seance(actif.session_utc) / (ctx.moteur.nb_ticks - 1) if unite != "1j" else None,
        "bougies": sortie, "indicateurs": {nom: v[-barres:] for nom, v in tout.items()}, "parametres": PARAMETRES,
        "niveaux": _niveaux(sortie),
    }


def _niveaux(b: list[dict]) -> dict:
    """Repères calculés sur les bougies affichées (sommets et creux confirmés seulement, voir analyse/niveaux.py)."""
    sr = nv.supports_resistances(b)
    return {"supports_resistances": [{k: v for k, v in x.items() if k != "dernier_indice"} for x in sr],
            "cassures": nv.cassures(b, sr), "tendances": nv.lignes_tendance(b), "fibonacci": nv.fibonacci(b)}


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
