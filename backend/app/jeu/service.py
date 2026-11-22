"""Parties : création, actions, et surtout CE QUE LE NAVIGATEUR A LE DROIT DE VOIR.

`vue` est la seule porte de sortie. Elle ne contient aucun cours, événement, arrêt, date ni longueur de film au-delà de la
séance atteinte. En séance mystère elle ne contient ni titre, ni date, ni nom d'actif tant que la crise n'est pas devinée.
"""
from __future__ import annotations

import math
import secrets
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..utilisateurs.modeles import Utilisateur, maintenant
from ..utilisateurs.service import ErreurMetier
from . import moteur
from .catalogue import DIFFICULTES, FILMS
from .donnees import Bobine, cinematheque
from .modeles import PartieJeu

SOLO, MYSTERE, JURY = "solo", "mystere", "jury"
EN_COURS, TERMINEE, ABANDONNEE = "en_cours", "terminee", "abandonnee"
DUREE_SOUS_TITRE = 14                            # séances pendant lesquelles un événement reste en sous-titre
SOUS_TITRES_NEUTRES = ("La salle retient son souffle.", "Un murmure parcourt les rangs.",
                       "Des spectateurs se lèvent.", "Les sorties sont prises d’assaut.")


def erreur(statut: int, message: str, code: str = "jeu") -> ErreurMetier:
    return ErreurMetier(code, message, statut)


def _bobine(film_id: str) -> Bobine:
    b = cinematheque().bobines.get(film_id)
    if b is None:
        raise erreur(503, "Ce film est indisponible : ses données n'ont pas passé les contrôles.", "film_indisponible")
    return b


def lire_partie(session: Session, utilisateur_id: int, partie_id: str) -> PartieJeu:
    p = session.get(PartieJeu, partie_id)
    if p is None or p.utilisateur_id != utilisateur_id:
        raise erreur(404, "Partie introuvable.", "partie_introuvable")
    return p


def _ecrire(session: Session, p: PartieJeu, version: int, **champs) -> PartieJeu:
    """Écriture conditionnelle : deux actions parties du même état ne passent pas toutes les deux."""
    r = session.execute(
        update(PartieJeu).where(PartieJeu.id == p.id, PartieJeu.version == version)
        .values(version=version + 1, maj_le=maintenant(), **champs).execution_options(synchronize_session=False))
    if r.rowcount != 1:
        session.rollback()
        raise erreur(409, "La partie a changé entre-temps : elle est rechargée.", "version_perimee")
    session.commit()
    session.refresh(p)
    return p


def _en_cours(p: PartieJeu, version: int) -> Bobine:
    if p.statut != EN_COURS:
        raise erreur(409, "Cette partie est terminée.", "partie_finie")
    if p.version != version:
        raise erreur(409, "La partie a changé entre-temps : elle est rechargée.", "version_perimee")
    return _bobine(p.film)


# ------------------------------------------------------------------ création
def creer(session: Session, utilisateur_id: int, mode: str, film: str | None, difficulte: str, plan: dict | None) -> PartieJeu:
    prets = cinematheque().bobines
    deja = set(session.scalars(select(PartieJeu.film).where(PartieJeu.utilisateur_id == utilisateur_id).distinct()))
    tirage = secrets.SystemRandom()
    if mode == MYSTERE:
        if film:
            raise erreur(422, "La séance mystère tire le film au sort.")
        if not prets:
            raise erreur(503, "Aucun film n'est disponible.", "film_indisponible")
        film = tirage.choice(list(prets))      # parmi tous : ne tirer qu'un film jamais vu le révélerait
    elif film not in FILMS:
        raise erreur(422, "Choisissez un film.")
    b = _bobine(film)
    if mode == JURY:
        plan, difficulte = None, "acteur"
    elif not plan:
        raise erreur(422, "Écrivez votre plan avant le film : perte maximale et réaction en cas de krach.", "plan_absent")

    presentation = [a.cle for a in b.film.actifs]
    if mode == MYSTERE:
        tirage.shuffle(presentation)
    session.execute(
        update(PartieJeu).where(PartieJeu.utilisateur_id == utilisateur_id, PartieJeu.statut == EN_COURS)
        .values(statut=ABANDONNEE, version=PartieJeu.version + 1, maj_le=maintenant()))
    p = PartieJeu(id=uuid.uuid4().hex, utilisateur_id=utilisateur_id, film=film, mode=mode, difficulte=difficulte,
                  statut=EN_COURS, premiere=film not in deja, seance=0, version=0, plan=plan,
                  presentation=presentation, ordres=[], choix=[])
    session.add(p)
    session.commit()
    return p


# ------------------------------------------------------------------ actions
def avancer(session: Session, p: PartieJeu, version: int, jusqu_a_l_arret: bool = False) -> PartieJeu:
    b = _en_cours(p, version)
    if moteur.arret_en_attente(b, p.seance, p.choix) is not None:
        raise erreur(409, "Le film est arrêté : décidez d'abord.", "decision_attendue")
    cible = p.seance + 1
    if jusqu_a_l_arret:
        if p.mode != JURY:
            raise erreur(409, "Seul le mode jury peut sauter jusqu'à l'arrêt suivant.")
        cible = b.arrets[len(p.choix)] if len(p.choix) < len(b.arrets) else b.dernier
    champs: dict = {"seance": min(max(cible, p.seance + 1), b.dernier)}
    if champs["seance"] >= b.dernier:
        r = moteur.noter(b, DIFFICULTES[p.difficulte]["frais"], p.plan, p.ordres, p.choix)
        champs.update(statut=TERMINEE, note=r["note"])
    return _ecrire(session, p, version, **champs)


def ordonner(session: Session, p: PartieJeu, version: int, rang: int, sens: str) -> PartieJeu:
    b = _en_cours(p, version)
    if moteur.arret_en_attente(b, p.seance, p.choix) is not None:
        raise erreur(409, "Le film est arrêté : décidez d'abord.", "decision_attendue")
    if not 0 <= rang < len(p.presentation):
        raise erreur(422, "Actif inconnu.")
    cle = p.presentation[rang]
    du_jour = [o for o in p.ordres if o["jour"] == p.seance]
    if len(du_jour) >= moteur.MAX_ORDRES_PAR_SEANCE:
        raise erreur(409, "Trop d'ordres pour une seule séance.")
    etat = moteur.rejouer(b, p.seance, DIFFICULTES[p.difficulte]["frais"], p.ordres, p.choix)
    if sens == "achat":
        engage = moteur.MISE * sum(o["sens"] == "achat" for o in du_jour)
        if etat.cash - engage < 1:
            raise erreur(409, "Plus de liquidités à engager.", "liquidites")
    elif etat.q[cle] * b.clotures[cle][p.seance] < 1:
        raise erreur(409, "Vous ne détenez pas cet actif.", "position")
    return _ecrire(session, p, version, ordres=[*p.ordres, {"jour": p.seance, "cle": cle, "sens": sens}])


def choisir(session: Session, p: PartieJeu, version: int, acte: str) -> PartieJeu:
    b = _en_cours(p, version)
    if moteur.arret_en_attente(b, p.seance, p.choix) is None:
        raise erreur(409, "Aucune décision n'est attendue.", "pas_d_arret")
    if acte not in moteur.ACTES:
        raise erreur(422, "Choix inconnu.")
    return _ecrire(session, p, version, choix=[*p.choix, {"jour": p.seance, "acte": acte}])


def deviner(session: Session, p: PartieJeu, version: int, film: str) -> PartieJeu:
    if p.mode != MYSTERE or p.statut != TERMINEE or p.devine is not None:
        raise erreur(409, "Il n'y a rien à deviner ici.")
    if film not in cinematheque().bobines:
        raise erreur(422, "Film inconnu.")
    return _ecrire(session, p, version, devine=film)


def abandonner(session: Session, p: PartieJeu, version: int) -> PartieJeu:
    _en_cours(p, version)
    return _ecrire(session, p, version, statut=ABANDONNEE)


# ------------------------------------------------------------------ ce que voit le navigateur
def _masquee(p: PartieJeu) -> bool:
    return p.mode == MYSTERE and not (p.statut == TERMINEE and p.devine is not None)


def vue(p: PartieJeu) -> dict:
    b = _bobine(p.film)
    i, film, reglage = p.seance, b.film, DIFFICULTES[p.difficulte]
    cache = _masquee(p)
    fini = p.statut == TERMINEE
    etat = moteur.rejouer(b, i, reglage["frais"], p.ordres, p.choix)
    temoin = moteur.double_immobile(b, i)
    attente = moteur.arret_en_attente(b, i, p.choix) if p.statut == EN_COURS else None
    du_jour = [o for o in p.ordres if o["jour"] == i] if p.statut == EN_COURS else []
    par_cle = {a.cle: a for a in film.actifs}

    actifs = []
    for rang, cle in enumerate(p.presentation):
        a, clo = par_cle[cle], b.clotures[cle][:i + 1]
        actifs.append({
            "rang": rang,
            "nom": f"Actif {'ABCD'[rang]}" if cache else a.nom,
            "detail": None if cache else a.detail,
            # la première ouverture n'est jamais jouée : on ne la donne pas
            "ouvertures": [100.0, *(round(x, 3) for x in b.ouvertures[cle][1:i + 1])],
            "clotures": [round(x, 3) for x in clo],
            "valeur": round(etat.q[cle] * clo[-1], 2),
            "en_attente": [o["sens"] for o in du_jour if o["cle"] == cle],
        })

    passees = [s for s in b.scenes if s[0] <= i]
    recente = passees[-1] if passees and i - passees[-1][0] <= DUREE_SOUS_TITRE else None
    sous_titre = recente[1] if recente and not cache else SOUS_TITRES_NEUTRES[min(3, int(b.peur[i] / 25))]

    if cache:
        mesure = None
    elif film.peur[0] == "vix":
        mesure = {"nom": "VIX", "valeur": b.peur_mesure[i], "unite": "points"}
    else:
        mesure = {"nom": "Bitcoin sous son plus haut de 30 jours", "valeur": b.peur_mesure[i], "unite": "part"}

    arret = None
    if attente is not None:
        evenement = next((t for s, t in reversed(b.scenes) if s <= b.arrets[attente]), None)
        arret = {
            "numero": attente, "question": moteur.QUESTIONS[attente],
            "evenement": "Un événement majeur secoue le marché." if cache else evenement,
            "options": [{"acte": k, **v} for k, v in moteur.ACTES.items()],
            "conseil": "Décidez selon votre plan, pas selon le bruit de la salle." if reglage["conseils"] else None,
        }

    vedette = p.presentation.index(film.vedette)
    sortie = {
        "id": p.id, "version": p.version, "mode": p.mode, "statut": p.statut, "seance": i,
        "titre": "Bobine Sans Titre" if cache else film.titre,
        "sujet": "Séance mystère" if cache else film.sujet,
        "film": None if cache else film.id,
        "date": None if cache else b.jours[i].isoformat(),
        "difficulte": {"cle": p.difficulte, "nom": reglage["nom"], "ms": reglage["ms"], "pause": reglage["pause"],
                       "frais": reglage["frais"]},
        "plan": p.plan, "capital": moteur.CAPITAL, "mise": moteur.MISE,
        "vedette": 0 if cache else vedette,
        "actifs": actifs,
        "liquidites": round(etat.cash, 2),
        "engage": min(etat.cash, moteur.MISE * sum(o["sens"] == "achat" for o in du_jour)),
        "valeur": etat.valeurs[-1],
        "double": temoin[-1],
        "baisse": moteur.baisses(etat.valeurs)[-1],
        "peur": round(b.peur[i], 1), "peur_mesure": mesure,
        "sous_titre": sous_titre,
        "arret": arret, "arrets_passes": [c["jour"] for c in p.choix],
        "classable": None if cache else p.mode == MYSTERE and p.premiere,       # « jamais vu » serait un indice
        "generique": None,
    }
    if fini:
        r = moteur.noter(b, reglage["frais"], p.plan, p.ordres, p.choix)
        sortie["generique"] = {
            **r,
            "courbe": [round(v, 2) for v in etat.valeurs],
            "courbe_double": [round(v, 2) for v in temoin],
            "montage": [{**m, "date": None if cache else b.jours[m["jour"]].isoformat(),
                         "evenement": None if cache else next((t for s, t in reversed(b.scenes) if s <= b.arrets[m["arret"]]), None)}
                        for m in moteur.montage(b, reglage["frais"], p.ordres, p.choix)],
            "a_deviner": ([{"film": f, "sujet": x.film.sujet} for f, x in cinematheque().bobines.items()] if cache else None),
            "devine": None if cache or p.devine is None else {"juste": p.devine == p.film, "sujet": film.sujet},
            "lecon": None if cache else film.lecon,
            "classee": p.mode == MYSTERE and p.premiere,
        }
    return sortie


# ------------------------------------------------------------------ accueil et classement
def classement(session: Session, limite: int = 10) -> list[dict]:
    """Séances mystère terminées, uniquement à la première rencontre du joueur avec le film. Moyenne par joueur."""
    lignes = session.execute(
        select(Utilisateur.id, Utilisateur.nom, PartieJeu.note).join(PartieJeu, PartieJeu.utilisateur_id == Utilisateur.id)
        .where(PartieJeu.mode == MYSTERE, PartieJeu.statut == TERMINEE, PartieJeu.premiere.is_(True),
               PartieJeu.note.is_not(None), Utilisateur.actif.is_(True))).all()
    par: dict[int, dict] = {}
    for uid, nom, note in lignes:
        par.setdefault(uid, {"nom": nom, "notes": []})["notes"].append(note)
    tri = sorted(({"nom": v["nom"], "note": math.floor(sum(v["notes"]) / len(v["notes"]) + 0.5), "parties": len(v["notes"])}
                  for v in par.values()), key=lambda x: (-x["note"], -x["parties"], x["nom"]))
    return [{"rang": i + 1, **x} for i, x in enumerate(tri[:limite])]


def accueil(session: Session, utilisateur_id: int) -> dict:
    c = cinematheque()
    parties = session.scalars(
        select(PartieJeu).where(PartieJeu.utilisateur_id == utilisateur_id).order_by(PartieJeu.cree_le.desc())).all()
    meilleurs: dict[str, int] = {}
    for p in parties:
        if p.statut == TERMINEE and p.note is not None and not _masquee(p):
            cle = MYSTERE if p.mode == MYSTERE else p.film
            meilleurs[cle] = max(meilleurs.get(cle, 0), p.note)
    reprise = next((p for p in parties if p.statut == EN_COURS and p.film in c.bobines), None)
    vus = {p.film for p in parties if not _masquee(p)}          # un film encore masqué ne doit pas se lire ici
    return {
        "films": [{"id": f.id, "titre": f.titre, "sujet": f.sujet, "accroche": f.accroche, "intensite": f.intensite,
                   "disponible": f.id in c.bobines,
                   "indisponible": "Données non conformes aux contrôles" if f.id in c.defauts else None,
                   "meilleur": meilleurs.get(f.id)} for f in FILMS.values()],
        "mystere": {"disponible": bool(c.bobines), "meilleur": meilleurs.get(MYSTERE),
                    "classable": bool(set(c.bobines) - vus)},
        "difficultes": [{"cle": k, "nom": v["nom"], "detail": v["detail"]} for k, v in DIFFICULTES.items()],
        "reactions": [{"acte": k, **v} for k, v in moteur.ACTES.items()],
        "pertes_max": list(moteur.PERTES_MAX),
        "capital": moteur.CAPITAL,
        "reprise": ({"id": reprise.id, "titre": "Bobine Sans Titre" if _masquee(reprise) else FILMS[reprise.film].titre,
                     "mode": reprise.mode} if reprise else None),
        "classement": classement(session),
    }
