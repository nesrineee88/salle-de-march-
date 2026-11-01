"""Formation : présentation des leçons (ordre des choix mélangé), correction côté serveur, progression, ligue, vue du formateur."""
from __future__ import annotations

import random
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..trading import persistance
from ..utilisateurs.modeles import Utilisateur, maintenant
from .contenu import INDEX, LECONS, SEUIL_REUSSITE
from .modeles import LeconDesactivee, ProgresLecon

MIN_POINTS_LIGUE = 5


def desactivees(session: Session) -> set[str]:
    return set(session.scalars(select(LeconDesactivee.lecon_id)))


def _permutation(utilisateur_id: int, lecon_id: str, q: int, n: int) -> list[int]:
    """Ordre d'affichage des choix, stable pour (utilisateur, leçon, question) : le choix affiché i est le choix d'origine perm[i]."""
    perm = list(range(n))
    random.Random(f"{utilisateur_id}:{lecon_id}:{q}").shuffle(perm)
    return perm


def progres_utilisateur(session: Session, utilisateur_id: int) -> dict[str, ProgresLecon]:
    return {p.lecon_id: p for p in session.scalars(select(ProgresLecon).where(ProgresLecon.utilisateur_id == utilisateur_id))}


def resume_lecon(l: dict, p: ProgresLecon | None, active: bool) -> dict:
    return {"id": l["id"], "titre": l["titre"], "niveau": l["niveau"], "minutes": l["minutes"], "resume": l["resume"], "nb_questions": len(l["questions"]),
            "active": active, "tentatives": p.tentatives if p else 0, "meilleur_score": p.meilleur_score if p else None,
            "reussie": bool(p and p.reussie_le)}


def lister(session: Session, utilisateur_id: int, role: str) -> list[dict]:
    off, prog = desactivees(session), progres_utilisateur(session, utilisateur_id)
    gestion = role in ("formateur", "admin")
    return [resume_lecon(l, prog.get(l["id"]), l["id"] not in off) for l in LECONS if l["id"] not in off or gestion]


def detail(session: Session, utilisateur_id: int, lecon_id: str) -> dict | None:
    l = INDEX.get(lecon_id)
    if l is None:
        return None
    questions = []
    for i, q in enumerate(l["questions"]):
        perm = _permutation(utilisateur_id, lecon_id, i, len(q["choix"]))
        questions.append({"index": i, "enonce": q["enonce"], "choix": [q["choix"][k] for k in perm]})
    return {**resume_lecon(l, progres_utilisateur(session, utilisateur_id).get(lecon_id), lecon_id not in desactivees(session)),
            "sections": l["sections"], "exercices": l["exercices"], "questions": questions, "seuil_reussite": SEUIL_REUSSITE}


def corriger(session: Session, utilisateur_id: int, lecon_id: str, reponses: list[int | None]) -> dict:
    l = INDEX[lecon_id]
    if len(reponses) != len(l["questions"]):
        raise ValueError(f"Il faut {len(l['questions'])} réponses (une par question, vide si vous ne savez pas).")
    corrections, bonnes = [], 0
    for i, (q, r) in enumerate(zip(l["questions"], reponses)):
        perm = _permutation(utilisateur_id, lecon_id, i, len(q["choix"]))
        if r is not None and not (isinstance(r, int) and 0 <= r < len(perm)):
            raise ValueError("Réponse invalide.")
        juste = r is not None and perm[r] == q["bonne"]
        bonnes += juste
        corrections.append({"index": i, "juste": juste, "repondu": r, "bonne_reponse": perm.index(q["bonne"]), "explication": q["explication"]})
    score = bonnes / len(l["questions"])
    p = session.get(ProgresLecon, (utilisateur_id, lecon_id)) or ProgresLecon(utilisateur_id=utilisateur_id, lecon_id=lecon_id, tentatives=0, meilleur_score=0.0)
    p.tentatives += 1
    p.dernier_score = score
    p.meilleur_score = max(p.meilleur_score or 0.0, score)
    p.derniere_tentative = maintenant()
    if score >= SEUIL_REUSSITE and p.reussie_le is None:
        p.reussie_le = maintenant()
    session.add(p)
    session.commit()
    return {"score": score, "bonnes": bonnes, "total": len(l["questions"]), "reussie": score >= SEUIL_REUSSITE, "corrections": corrections, "seuil_reussite": SEUIL_REUSSITE}


def progression(session: Session, utilisateur_id: int) -> dict:
    off, prog = desactivees(session), progres_utilisateur(session, utilisateur_id)
    actives = [l["id"] for l in LECONS if l["id"] not in off]
    reussies = [i for i in actives if prog.get(i) and prog[i].reussie_le]
    scores = [prog[i].meilleur_score for i in actives if i in prog]
    return {"lecons_actives": len(actives), "lecons_reussies": len(reussies), "score_moyen": (sum(scores) / len(scores)) if scores else None, "tentatives": sum(p.tentatives for p in prog.values())}


# ------------------------------------------------------------------ ligue
def _performance(points: list[dict], jusqu_au: date | None) -> dict | None:
    """Rendement et pire baisse d'un portefeuille, jusqu'à une date simulée (ou jusqu'à son dernier point)."""
    pts = [p for p in points if jusqu_au is None or p["jour"] <= jusqu_au.isoformat()]
    if len(pts) < MIN_POINTS_LIGUE:
        return None
    if jusqu_au is not None and pts[-1]["jour"] < jusqu_au.isoformat():
        return None                                    # l'utilisateur n'est pas encore arrivé à cette date : on ne le classe pas
    valeurs = [config.CAPITAL_INITIAL_DEFAUT] + [p["equity"] for p in pts]
    pic, pire = valeurs[0], 0.0
    for v in valeurs:
        pic = max(pic, v)
        pire = max(pire, (pic - v) / pic if pic > 0 else 0.0)
    rendement = valeurs[-1] / valeurs[0] - 1
    return {"rendement": rendement, "drawdown": pire, "score": rendement / max(pire, 0.05), "date_simulee": pts[-1]["jour"], "points": len(pts), "valeur": valeurs[-1]}


def ligue(session: Session, jusqu_au: date | None = None, limite: int = 50) -> list[dict]:
    """Classement par rendement ajusté du risque : rendement divisé par la pire baisse (au moins 5 %, pour qu'une période calme ne donne pas un score infini).
    Seuls comptent les portefeuilles ayant au moins 5 jours simulés. Sans date fixe, chacun est jugé sur sa propre période : à lire avec prudence."""
    ids = list(session.scalars(select(persistance.HistoriqueValeurDb.utilisateur_id).distinct()))
    noms = {u.id: u.nom for u in session.scalars(select(Utilisateur).where(Utilisateur.id.in_(ids), Utilisateur.actif.is_(True)))} if ids else {}
    lignes = []
    for uid, nom in noms.items():
        perf = _performance(persistance.lire_historique(session, uid), jusqu_au)
        if perf:
            lignes.append({"nom": nom, **perf})
    lignes.sort(key=lambda x: -x["score"])
    for i, l in enumerate(lignes[:limite], start=1):
        l["rang"] = i
    return lignes[:limite]


def classe(session: Session) -> list[dict]:
    """Vue du formateur : chaque apprenant ou trader, sa progression en formation et le résumé de son portefeuille."""
    off = desactivees(session)
    actives = [l["id"] for l in LECONS if l["id"] not in off]
    sortie = []
    for u in session.scalars(select(Utilisateur).where(Utilisateur.role.in_(("apprenant", "trader")), Utilisateur.actif.is_(True)).order_by(Utilisateur.nom)):
        prog = progres_utilisateur(session, u.id)
        perf = _performance(persistance.lire_historique(session, u.id), None)
        sortie.append({"id": u.id, "nom": u.nom, "role": u.role, "profil_risque": (u.profil_risque or {}).get("categorie"),
                       "lecons_reussies": sum(1 for i in actives if prog.get(i) and prog[i].reussie_le), "lecons_actives": len(actives),
                       "score_moyen": (sum(p.meilleur_score for p in prog.values()) / len(prog)) if prog else None, "portefeuille": perf})
    return sortie
