"""Routes de l'assistant XAI. Lecture seule, sans internet. Les questions ne sont pas enregistrées."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..contexte import Contexte, acces_bac, instant_compte, obtenir_contexte
from ..ia import analyses
from ..utilisateurs.db import obtenir_session
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.roles import a_permission
from ..utilisateurs.routes import exiger
from . import couverture, reponses
from .comprendre import comprendre, normaliser

routeur = APIRouter(prefix="/api/v1/xai")

# Première partie du chemin de la page -> questions proposées. Un test vérifie qu'elles sont toutes comprises.
SUGGESTIONS = {
    "": ["Résume mon tableau de bord", "Pourquoi ai-je ce résultat ?", "Suis-je meilleur que l’indice ?"],
    "marche": ["Comment passer un ordre ?", "Parle-moi d’Apple", "C’est quoi un stop ?"],
    "actif": ["Explique-moi cet actif", "Et si cet actif baisse de 10 % ?", "C’est quoi le RSI ?"],
    "portefeuille": ["Pourquoi ce niveau de risque ?", "Quelle position pèse le plus ?", "Mes ordres en attente"],
    "strategies": ["Compare Apple et Microsoft", "C’est quoi le ratio de Sharpe ?", "C’est quoi un backtest ?"],
    "jeu": ["Explique ma note au jeu", "Qu’aurait donné un autre choix au jeu ?", "C’est quoi le VIX ?"],
    "stress": ["Quelle banque est la plus fragile ?", "Pourquoi AlJazira est la plus fragile ?", "C’est quoi le CET1 ?"],
    "actualites": ["Que dit la presse sur Apple ?", "C’est quoi le ton d’une actualité ?"],
    "credit": ["C’est quoi le Z-score ?", "C’est quoi la PD ?"],
    "compte": ["Explique cette page", "Pourquoi ce niveau de risque ?"],
    "formation": ["Par quelle leçon débuter ?", "C’est quoi le ratio de Sharpe ?"],
    "actuariat": ["Comment est calculée la prime ?", "C’est quoi une franchise ?"],
    "ia": ["C’est quoi une IA explicable ?", "Parle-moi d’Apple"],
    "xai": ["Pourquoi ce niveau de risque ?", "Pourquoi ai-je ce résultat ?", "Et si tout baisse de 10 % ?",
            "Quelle banque est la plus fragile ?", "Explique ma note au jeu", "Est-ce que Bitcoin va monter demain ?"],
}


class Contexte_(BaseModel):
    """La question précédente, renvoyée par le client pour les suites (« et pour Bitcoin ? »). Le serveur ne garde rien."""
    intention: str | None = Field(None, max_length=20)
    symbole: str | None = Field(None, max_length=40)
    banque: str | None = Field(None, max_length=20)
    symbole2: str | None = Field(None, max_length=40)


class CorpsQuestion(BaseModel):
    question: str = Field(max_length=300)
    symbole: str | None = Field(None, max_length=40)     # actif de la page ouverte, pour « cet actif »
    page: str | None = Field(None, max_length=20, pattern=r"^[a-z-]*$")   # première partie du chemin de la page ouverte
    contexte: Contexte_ | None = None

    @field_validator("question")
    @classmethod
    def non_vide(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question vide")
        return v.strip()


@routeur.get("/suggestions")
def suggestions(_u: Utilisateur = Depends(exiger("xai.demander"))):
    return SUGGESTIONS


@routeur.post("/question")
def question(corps: CorpsQuestion, ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("xai.demander")),
             session: Session = Depends(obtenir_session)):
    contexte = None
    if corps.contexte and corps.contexte.intention in reponses.REPONSES:      # contexte inconnu : ignoré, jamais une erreur
        contexte = {"intention": corps.contexte.intention,
                    "symbole": corps.contexte.symbole if corps.contexte.symbole in ctx.univers else None,
                    "banque": corps.contexte.banque,
                    "symbole2": corps.contexte.symbole2 if corps.contexte.symbole2 in ctx.univers else None}
    lecture = comprendre(corps.question, ctx.univers, corps.symbole, contexte, corps.page)
    if lecture.intention == "comparer" and lecture.symbole2 is None:              # suite sans second actif : on explique le premier
        lecture = type(lecture)("actif", symbole=lecture.symbole, suite=lecture.suite)
    if lecture.intention in ("actif", "modele", "comparer") and (lecture.symbole not in ctx.univers or
                                                                 (lecture.symbole2 is not None and lecture.symbole2 not in ctx.univers)):
        lecture = type(lecture)("inconnu")
    passe = None
    r = None
    with acces_bac(ctx, u) as (bac, t):
        t = instant_compte(bac, t)
        if lecture.intention != "modele":
            r = reponses.REPONSES[lecture.intention](reponses.Situation(ctx, bac, t, u, session, lecture, normaliser(corps.question)))
        elif not a_permission(u.role, "ia.utiliser"):
            r = reponses.reponse(
                "Le modèle statistique est réservé aux rôles trader, formateur et administrateur. Je peux vous expliquer cet actif sans lui.",
                reponses.preuve("Même permission que la page IA"))
        elif not ctx.magasin.a_des_donnees(lecture.symbole):
            r = reponses.reponse("Cet actif n’a pas de données.", reponses.preuve("Donnée absente"))
        else:
            passe = ctx.magasin.barres_terminees(lecture.symbole, t.date())
    if r is None:                                        # l'entraînement ne garde pas le verrou du compte
        try:
            r = reponses.expliquer_modele(ctx.univers[lecture.symbole].nom, analyses.predire(passe))
        except (ValueError, RuntimeError) as exc:
            r = reponses.reponse(f"Le modèle ne peut pas répondre : {exc}", reponses.preuve("Calcul impossible, rien n’est inventé"))
    return {"intention": lecture.intention, "instant": t.isoformat(timespec="seconds"), "symbole": lecture.symbole, "symbole2": lecture.symbole2, "banque": lecture.banque,
            "suite": lecture.suite, "suivantes": couverture.suites(lecture), **r}
