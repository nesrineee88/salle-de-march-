"""Routes : scénarios de crise (administrateur) et actualités (administrateur : gestion ; tous : lecture à la date simulée)."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contexte import Contexte, acces_bac, obtenir_contexte
from ..utilisateurs.db import obtenir_session
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from ..utilisateurs.service import auditer
from . import faits, service
from .modeles import ActualiteDb, ScenarioDb
from .sentiment import analyser
from .surcouche import Parametres

routeur = APIRouter(prefix="/api/v1")

AVERTISSEMENT_REJOUE = ("Les utilisateurs qui ont déjà dépassé cette date verront leurs prix passés modifiés : leurs positions restent "
                        "enregistrées mais leur courbe de valeur passée ne sera plus cohérente. Idéalement, créez la crise avant les parcours à noter.")


class CorpsScenario(BaseModel):
    nom: str = Field(min_length=2, max_length=120)
    description: str = Field("", max_length=600)
    date_debut: date
    portee_type: Literal["tous", "classe", "secteur", "actifs"]
    portee_valeurs: list[str] = Field(default_factory=list, max_length=60)
    choc_pct: float = Field(ge=-95, le=300, description="−30 signifie une chute de 30 % dès l'ouverture")
    recuperation_pct: float = Field(0, ge=0, le=100)
    duree_recuperation_jours: int = Field(0, ge=0, le=1825)
    annonce: str | None = Field(None, max_length=1200, description="Texte d'une actualité publiée le jour du choc (facultatif)")


class CorpsMiseAJourScenario(BaseModel):
    actif: bool


class CorpsActualite(BaseModel):
    date: date
    titre: str = Field(min_length=3, max_length=200)
    texte: str = Field("", max_length=1200)
    symboles: list[str] = Field(default_factory=list, max_length=20)


class CorpsMiseAJourActualite(BaseModel):
    actif: bool


def _erreur(exc: ValueError) -> HTTPException:
    return HTTPException(422, str(exc))


# ------------------------------------------------------------------ administrateur : crises
@routeur.get("/admin/scenarios/modeles")
def modeles_scenarios(_a: Utilisateur = Depends(exiger("admin.crises"))):
    return faits.MODELES


@routeur.get("/admin/scenarios")
def lister_scenarios(ctx: Contexte = Depends(obtenir_contexte), _a: Utilisateur = Depends(exiger("admin.crises")),
                     session: Session = Depends(obtenir_session)):
    lignes = session.scalars(select(ScenarioDb).order_by(ScenarioDb.date_debut, ScenarioDb.id))
    secteurs = sorted({a.secteur for a in ctx.univers if a.tradable})
    return {"scenarios": [service.scenario_en_dict(s, ctx) for s in lignes], "secteurs": secteurs,
            "classes": ["action", "crypto", "matiere"],
            "actifs": [{"symbole": a.symbole, "nom": a.nom} for a in ctx.univers if a.tradable],
            "debut": ctx.univers.debut.isoformat(), "fin": ctx.univers.fin.isoformat()}


@routeur.post("/admin/scenarios", status_code=201)
def creer_scenario(corps: CorpsScenario, ctx: Contexte = Depends(obtenir_contexte), admin: Utilisateur = Depends(exiger("admin.crises")),
                   session: Session = Depends(obtenir_session)):
    try:
        valeurs = service.valider_perimetre(ctx, corps.portee_type, corps.portee_valeurs)
        p = Parametres(corps.date_debut, corps.portee_type, tuple(valeurs), corps.choc_pct / 100, corps.recuperation_pct / 100, corps.duree_recuperation_jours)
        service.verifier_scenario(ctx, p)
    except ValueError as exc:
        raise _erreur(exc) from None
    s = ScenarioDb(nom=" ".join(corps.nom.split()), description=corps.description.strip(), date_debut=corps.date_debut,
                   portee_type=corps.portee_type, portee_valeurs=valeurs, choc=p.choc, recuperation=p.recuperation,
                   duree_recuperation_jours=p.duree, actif=True, cree_par=admin.id)
    session.add(s)
    session.commit()
    if corps.annonce and corps.annonce.strip():
        from .surcouche import symboles_concernes
        concernes = sorted(x for x in symboles_concernes(ctx.univers, p.portee_type, p.portee_valeurs) if x != "^GSPC")
        session.add(ActualiteDb(date=corps.date_debut, titre=corps.annonce.strip()[:200], texte="", symboles=concernes[:20] if corps.portee_type == "actifs" else [],
                                type_source="scenario", note_source="Actualité fictive liée à un scénario de crise créé par l'administrateur.", scenario_id=s.id))
        session.commit()
    nb = service.reappliquer(ctx, session)
    auditer(session, "admin.scenario.creer", admin.id, {"id": s.id, "nom": s.nom, "debut": s.date_debut.isoformat(), "choc_pct": corps.choc_pct})
    return {"scenario": service.scenario_en_dict(s, ctx), "scenarios_appliques": nb, "avertissement": AVERTISSEMENT_REJOUE}


@routeur.patch("/admin/scenarios/{identifiant}")
def basculer_scenario(identifiant: int, corps: CorpsMiseAJourScenario, ctx: Contexte = Depends(obtenir_contexte),
                      admin: Utilisateur = Depends(exiger("admin.crises")), session: Session = Depends(obtenir_session)):
    s = session.get(ScenarioDb, identifiant)
    if s is None:
        raise HTTPException(404, "Scénario introuvable.")
    s.actif = corps.actif
    for a in session.scalars(select(ActualiteDb).where(ActualiteDb.scenario_id == s.id)):
        a.actif = corps.actif
    session.commit()
    nb = service.reappliquer(ctx, session)
    auditer(session, "admin.scenario.activer" if corps.actif else "admin.scenario.desactiver", admin.id, {"id": s.id})
    return {"scenario": service.scenario_en_dict(s, ctx), "scenarios_appliques": nb, "avertissement": AVERTISSEMENT_REJOUE}


@routeur.delete("/admin/scenarios/{identifiant}", status_code=204)
def supprimer_scenario(identifiant: int, ctx: Contexte = Depends(obtenir_contexte),
                       admin: Utilisateur = Depends(exiger("admin.crises")), session: Session = Depends(obtenir_session)):
    s = session.get(ScenarioDb, identifiant)
    if s is None:
        raise HTTPException(404, "Scénario introuvable.")
    for a in session.scalars(select(ActualiteDb).where(ActualiteDb.scenario_id == s.id)):
        session.delete(a)
    session.delete(s)
    session.commit()
    service.reappliquer(ctx, session)
    auditer(session, "admin.scenario.supprimer", admin.id, {"id": identifiant})


# ------------------------------------------------------------------ administrateur : actualités
@routeur.get("/admin/actualites")
def lister_actualites_admin(_a: Utilisateur = Depends(exiger("admin.crises")), session: Session = Depends(obtenir_session)):
    lignes = session.scalars(select(ActualiteDb).order_by(ActualiteDb.date.desc(), ActualiteDb.id.desc()))
    return [{**service.actualite_en_dict(a), "sentiment": analyser(f"{a.titre}. {a.texte}").en_dict()} for a in lignes]


@routeur.post("/admin/actualites", status_code=201)
def creer_actualite(corps: CorpsActualite, ctx: Contexte = Depends(obtenir_contexte), admin: Utilisateur = Depends(exiger("admin.crises")),
                    session: Session = Depends(obtenir_session)):
    if not ctx.univers.debut <= corps.date <= ctx.univers.fin:
        raise HTTPException(422, "La date doit être comprise dans la période rejouée.")
    inconnus = [s for s in corps.symboles if s not in ctx.univers]
    if inconnus:
        raise HTTPException(422, f"Actif inconnu : {', '.join(inconnus)}.")
    a = ActualiteDb(date=corps.date, titre=" ".join(corps.titre.split()), texte=corps.texte.strip(), symboles=corps.symboles, type_source="fictif",
                    note_source="Actualité fictive saisie par l'administrateur.")
    session.add(a)
    session.commit()
    auditer(session, "admin.actualite.creer", admin.id, {"id": a.id})
    return service.actualite_en_dict(a)


@routeur.post("/admin/actualites/reperes")
def charger_reperes(admin: Utilisateur = Depends(exiger("admin.crises")), session: Session = Depends(obtenir_session)):
    n = service.semer_reperes(session)
    auditer(session, "admin.actualite.reperes", admin.id, {"ajoutees": n})
    return {"ajoutees": n}


@routeur.patch("/admin/actualites/{identifiant}")
def basculer_actualite(identifiant: int, corps: CorpsMiseAJourActualite, admin: Utilisateur = Depends(exiger("admin.crises")),
                       session: Session = Depends(obtenir_session)):
    a = session.get(ActualiteDb, identifiant)
    if a is None:
        raise HTTPException(404, "Actualité introuvable.")
    a.actif = corps.actif
    session.commit()
    auditer(session, "admin.actualite.activer" if corps.actif else "admin.actualite.desactiver", admin.id, {"id": a.id})
    return service.actualite_en_dict(a)


@routeur.delete("/admin/actualites/{identifiant}", status_code=204)
def supprimer_actualite(identifiant: int, admin: Utilisateur = Depends(exiger("admin.crises")), session: Session = Depends(obtenir_session)):
    a = session.get(ActualiteDb, identifiant)
    if a is None:
        raise HTTPException(404, "Actualité introuvable.")
    session.delete(a)
    session.commit()
    auditer(session, "admin.actualite.supprimer", admin.id, {"id": identifiant})


# ------------------------------------------------------------------ lecture par tous, à la date simulée
@routeur.get("/actualites")
def actualites(symbole: str | None = Query(None, max_length=20), limite: int = Query(40, ge=1, le=200),
               ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire")),
               session: Session = Depends(obtenir_session)):
    """Actualités déjà parues à la date simulée de l'utilisateur, avec leur sentiment et ce que le marché a fait ensuite (séances terminées seulement)."""
    with acces_bac(ctx, u) as (_bac, t):
        pass
    if symbole is not None and symbole not in ctx.univers:
        raise HTTPException(404, f"Actif inconnu : {symbole}")
    requete = select(ActualiteDb).where(ActualiteDb.actif.is_(True), ActualiteDb.date <= t.date()).order_by(ActualiteDb.date.desc(), ActualiteDb.id.desc())
    sortie = []
    for a in session.scalars(requete):
        if not service.visible(a, t):
            continue
        if symbole is not None and a.symboles and symbole not in a.symboles:
            continue
        if symbole is not None and not a.symboles:
            pass                                    # nouvelle générale : concerne tous les actifs
        sentiment = analyser(f"{a.titre}. {a.texte}")
        sortie.append({**service.actualite_en_dict(a), "sentiment": sentiment.en_dict(), "impact": service.impact(ctx, a, t.date())})
        if len(sortie) >= limite:
            break
    return {"instant": t.isoformat(timespec="seconds"), "actualites": sortie}


@routeur.get("/actualites/etude")
def etude(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("marche.lire")),
          session: Session = Depends(obtenir_session)):
    with acces_bac(ctx, u) as (_bac, t):
        pass
    return service.etude_sentiment(ctx, session, t)
