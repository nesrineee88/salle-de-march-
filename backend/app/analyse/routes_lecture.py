"""Routes de la lecture d'un actif (technique et sentiment). Séances terminées seulement, avant la date simulée."""
from __future__ import annotations

from datetime import date
from functools import lru_cache

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from .. import config
from ..contexte import Contexte, acces_bac, donnees_ou_erreur, instant_compte, obtenir_contexte
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from . import lecture

routeur = APIRouter(prefix="/api/v1/lecture")
SOURCE_SENTIMENT = "GDELT Project, ton moyen quotidien des articles en anglais (https://www.gdeltproject.org)"


def fichier_sentiment():
    return config.DATA_DIR / "externes" / "sentiment_gdelt.csv"


@lru_cache(maxsize=2)
def _tons(chemin: str, taille: int) -> dict[str, pd.Series]:
    df = pd.read_csv(chemin, parse_dates=["date"])
    return {s: g.set_index("date")["ton"].astype(float) for s, g in df.groupby("symbole")}


def tons_du_symbole(symbole: str, avant: date) -> tuple[pd.Series, str | None]:
    f = fichier_sentiment()
    if not f.exists():
        return pd.Series(dtype=float), None
    tons = _tons(str(f), f.stat().st_size)
    serie = tons.get(symbole, pd.Series(dtype=float))
    requete = None
    if not serie.empty:
        brut = pd.read_csv(f, usecols=["symbole", "requete"], nrows=None)
        requete = brut.loc[brut["symbole"] == symbole, "requete"].iloc[0]
    return serie.loc[: pd.Timestamp(avant) - pd.Timedelta(days=1)], requete


def _passe(ctx: Contexte, u: Utilisateur, symbole: str):
    donnees_ou_erreur(ctx, symbole)
    if not ctx.univers[symbole].tradable:
        raise HTTPException(422, "Cet indice sert de référence : choisissez un actif négociable.")
    with acces_bac(ctx, u) as (bac, t):
        t = instant_compte(bac, t)
        return ctx.magasin.barres_terminees(symbole, t.date()), t


@routeur.get("/technique/{symbole:path}")
def technique(symbole: str, ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    df, t = _passe(ctx, u, symbole)
    try:
        return {"symbole": symbole, "nom": ctx.univers[symbole].nom, "instant": t.isoformat(timespec="seconds"), **lecture.lire(df)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@routeur.get("/sentiment/{symbole:path}")
def sentiment(symbole: str, ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire"))):
    df, t = _passe(ctx, u, symbole)
    tons, requete = tons_du_symbole(symbole, t.date())
    if tons.empty:
        raise HTTPException(422, "Aucun ton de presse collecté pour cet actif avant votre date.")
    try:
        r = lecture.sentiment(df, tons)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {"symbole": symbole, "nom": ctx.univers[symbole].nom, "instant": t.isoformat(timespec="seconds"),
            "requete": requete, "source": SOURCE_SENTIMENT, **r}
