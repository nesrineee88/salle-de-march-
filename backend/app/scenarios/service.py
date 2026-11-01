"""Logique des scénarios de crise et des actualités : base de données, application aux prix, impact observé."""
from __future__ import annotations

from datetime import date, datetime, time

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contexte import Contexte
from . import faits
from .modeles import ActualiteDb, ScenarioDb
from .sentiment import analyser
from .surcouche import BENCHMARK, Parametres, calculer, verifier

HEURE_PARUTION = time(8, 0)       # une actualité est visible à partir de 08:00 le jour de parution


# ------------------------------------------------------------------ scénarios
def en_parametres(s: ScenarioDb) -> Parametres:
    return Parametres(s.date_debut, s.portee_type, tuple(s.portee_valeurs or ()), s.choc, s.recuperation, s.duree_recuperation_jours)


def reappliquer(ctx: Contexte, session: Session) -> int:
    """Recalcule les prix servis à partir des prix d'origine et des scénarios actifs. Renvoie le nombre de scénarios appliqués."""
    actifs = list(session.scalars(select(ScenarioDb).where(ScenarioDb.actif.is_(True)).order_by(ScenarioDb.id)))
    mult = calculer([en_parametres(s) for s in actifs], ctx.univers, ctx.magasin.series_origine())
    ctx.magasin.appliquer_scenarios(mult)
    ctx.moteur.invalider()
    ctx.magasin.multiplicateurs_actifs = len(actifs)
    return len(actifs)


def valider_perimetre(ctx: Contexte, portee_type: str, valeurs: list[str]) -> list[str]:
    """Nettoie et vérifie le périmètre (messages en français)."""
    valeurs = [v.strip() for v in valeurs if v and v.strip()]
    if portee_type == "secteur":
        secteurs = {a.secteur for a in ctx.univers if a.tradable}
        inconnus = [v for v in valeurs if v not in secteurs]
        if inconnus:
            raise ValueError(f"Secteur inconnu : {', '.join(inconnus)}. Secteurs disponibles : {', '.join(sorted(secteurs))}.")
    if portee_type == "actifs":
        inconnus = [v for v in valeurs if v not in ctx.univers or not ctx.univers[v].tradable]
        if inconnus:
            raise ValueError(f"Actif inconnu ou non négociable : {', '.join(inconnus)}.")
    return valeurs


def verifier_scenario(ctx: Contexte, p: Parametres) -> None:
    verifier(p)
    if not ctx.univers.debut <= p.debut <= ctx.univers.fin:
        raise ValueError(f"La date de début doit être comprise entre le {ctx.univers.debut.strftime('%d/%m/%Y')} et le {ctx.univers.fin.strftime('%d/%m/%Y')} (période rejouée).")


def scenario_en_dict(s: ScenarioDb, ctx: Contexte | None = None) -> dict:
    d = {
        "id": s.id, "nom": s.nom, "description": s.description, "date_debut": s.date_debut.isoformat(),
        "portee_type": s.portee_type, "portee_valeurs": list(s.portee_valeurs or []),
        "choc_pct": round(s.choc * 100, 2), "recuperation_pct": round(s.recuperation * 100, 2),
        "duree_recuperation_jours": s.duree_recuperation_jours, "actif": s.actif,
        "cree_le": s.cree_le.isoformat() if s.cree_le else None,
    }
    if ctx is not None:
        from .surcouche import symboles_concernes
        d["nb_actifs"] = len(symboles_concernes(ctx.univers, s.portee_type, s.portee_valeurs))
    return d


# ------------------------------------------------------------------ actualités
def actualite_en_dict(a: ActualiteDb) -> dict:
    return {"id": a.id, "date": a.date.isoformat(), "titre": a.titre, "texte": a.texte, "symboles": list(a.symboles or []),
            "type_source": a.type_source, "note_source": a.note_source, "actif": a.actif, "scenario_id": a.scenario_id}


def semer_reperes(session: Session) -> int:
    """Ajoute les repères historiques absents (idempotent). Renvoie le nombre d'actualités créées."""
    existantes = {(a.date, a.titre) for a in session.scalars(select(ActualiteDb).where(ActualiteDb.type_source == "historique"))}
    n = 0
    for jour, titre, texte, symboles in faits.REPERES:
        d = date.fromisoformat(jour)
        if (d, titre) in existantes:
            continue
        session.add(ActualiteDb(date=d, titre=titre, texte=texte, symboles=symboles, type_source="historique", note_source=faits.NOTE_HISTORIQUE))
        n += 1
    session.commit()
    return n


def visible(a: ActualiteDb, t: datetime) -> bool:
    return a.date < t.date() or (a.date == t.date() and t.time() >= HEURE_PARUTION)


def _rendements(ctx: Contexte, symbole: str, jour: date, avant: date) -> dict[str, float | None]:
    """Rendement de la clôture précédant `jour` jusqu'à la clôture du jour de parution (1 j) puis de la 5e séance (5 j).
    N'utilise que des séances terminées avant `avant` (la date simulée) : aucun futur."""
    if not ctx.magasin.a_des_donnees(symbole):
        return {"rendement_1j": None, "rendement_5j": None}
    df = ctx.magasin.barres_terminees(symbole, avant)
    if len(df) < 2:
        return {"rendement_1j": None, "rendement_5j": None}
    cl = df["close"].to_numpy(dtype=float)
    i_jour = int(df.index.searchsorted(pd.Timestamp(jour)))          # première séance de parution ou suivante
    if i_jour < 1:
        return {"rendement_1j": None, "rendement_5j": None}
    base = cl[i_jour - 1]

    def rend(i: int) -> float | None:
        if i >= len(cl) or base == 0 or not np.isfinite(base):
            return None
        return float((cl[i] - base) / abs(base))

    return {"rendement_1j": rend(i_jour), "rendement_5j": rend(i_jour + 4)}


def impact(ctx: Contexte, a: ActualiteDb, avant: date) -> list[dict]:
    symboles = list(a.symboles or []) or [BENCHMARK]
    sortie = []
    for s in symboles:
        if s not in ctx.univers:
            continue
        sortie.append({"symbole": s, **_rendements(ctx, s, a.date, avant)})
    return sortie


def etude_sentiment(ctx: Contexte, session: Session, t: datetime) -> dict:
    """Le sentiment du texte annonce-t-il le sens du marché le jour de parution ? Calculé sur les seules actualités déjà parues."""
    lignes = []
    for a in session.scalars(select(ActualiteDb).where(ActualiteDb.actif.is_(True)).order_by(ActualiteDb.date)):
        if not visible(a, t):
            continue
        r = [x["rendement_1j"] for x in impact(ctx, a, t.date()) if x["rendement_1j"] is not None]
        if not r:
            continue
        sent = analyser(f"{a.titre}. {a.texte}")
        lignes.append((sent.score, sent.etiquette, float(np.mean(r))))
    n = len(lignes)
    utiles = [(e, r) for _, e, r in lignes if e != "neutre" and r != 0]
    concordance = (sum(1 for e, r in utiles if (e == "positif") == (r > 0)) / len(utiles)) if utiles else None
    correlation = None
    if n >= 8:
        s_, r_ = np.array([x[0] for x in lignes]), np.array([x[2] for x in lignes])
        if np.std(s_) > 0 and np.std(r_) > 0:
            correlation = float(np.corrcoef(s_, r_)[0, 1])
    return {
        "nb_actualites": n, "nb_non_neutres": len(utiles), "concordance": concordance, "correlation": correlation,
        "avertissement": ("Échantillon trop petit pour conclure : à partir d'une trentaine d'actualités seulement, ces chiffres commencent à signifier quelque chose."
                          if n < 30 else "Un lien observé ici ne prouve pas que l'actualité cause le mouvement : le marché peut avoir bougé pour d'autres raisons le même jour."),
    }
