"""Administration : statistiques globales, performance des utilisateurs, données et modèles d'IA, paramètres de simulation (lecture seule)."""
from __future__ import annotations

import json
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .contexte import Contexte, obtenir_contexte
from .formation import service as formation
from .formation.contenu import LECONS
from .formation.modeles import ProgresLecon
from .scenarios.modeles import ActualiteDb, ScenarioDb
from .trading import persistance
from .trading.carnet import FRAIS_BPS, SPREAD_BPS
from .utilisateurs.db import obtenir_session
from .utilisateurs.modeles import Utilisateur, maintenant
from .utilisateurs.routes import exiger

routeur = APIRouter(prefix="/api/v1/admin")


def modeles_enregistres() -> list[dict]:
    """Modèles entraînés enregistrés sur disque, avec leur origine (jeu réel ou synthétique) et leurs mesures clés."""
    dossier = config.DATA_DIR / "modeles"
    sortie = []
    for nom, titre, cle_metrique, route in [("pd_credit.json", "Probabilité de défaut (crédit aux particuliers)", "auc_logistique", "/api/v1/admin/credit/pd/entrainer"),
                                            ("tarif_auto.json", "Tarification assurance auto", "deviance_poisson", "/api/v1/actuariat/admin/entrainer")]:
        chemin = dossier / nom
        if not chemin.exists():
            sortie.append({"cle": nom, "titre": titre, "present": False, "route_entrainement": route})
            continue
        d = json.loads(chemin.read_text(encoding="utf-8"))
        sortie.append({"cle": nom, "titre": titre, "present": True, "source": d.get("source"), "mesure": cle_metrique, "valeur": d.get("metriques", {}).get(cle_metrique),
                       "modifie_le": chemin.stat().st_mtime, "route_entrainement": route})
    return sortie


@routeur.get("/statistiques")
def statistiques(ctx: Contexte = Depends(obtenir_contexte), _a: Utilisateur = Depends(exiger("admin.utilisateurs")), session: Session = Depends(obtenir_session)):
    maintenant_ = maintenant()
    par_role = dict(session.execute(select(Utilisateur.role, func.count()).group_by(Utilisateur.role)).all())
    n = lambda requete: int(session.scalar(requete) or 0)
    ordres = dict(session.execute(select(persistance.OrdreDb.statut, func.count()).group_by(persistance.OrdreDb.statut)).all())
    top = session.execute(select(persistance.ExecutionDb.symbole, func.count().label("n")).group_by(persistance.ExecutionDb.symbole).order_by(func.count().desc()).limit(8)).all()
    reussies = dict(session.execute(select(ProgresLecon.lecon_id, func.count()).where(ProgresLecon.reussie_le.is_not(None)).group_by(ProgresLecon.lecon_id)).all())
    scores = dict(session.execute(select(ProgresLecon.lecon_id, func.avg(ProgresLecon.meilleur_score)).group_by(ProgresLecon.lecon_id)).all())
    return {
        "utilisateurs": {"total": n(select(func.count()).select_from(Utilisateur)), "actifs": n(select(func.count()).select_from(Utilisateur).where(Utilisateur.actif.is_(True))),
                         "par_role": par_role,
                         "nouveaux_7_jours": n(select(func.count()).select_from(Utilisateur).where(Utilisateur.cree_le >= maintenant_ - timedelta(days=7))),
                         "connectes_7_jours": n(select(func.count()).select_from(Utilisateur).where(Utilisateur.derniere_connexion >= maintenant_ - timedelta(days=7)))},
        "trading": {"ordres_par_statut": ordres, "executions": n(select(func.count()).select_from(persistance.ExecutionDb)),
                    "frais_totaux": float(session.scalar(select(func.sum(persistance.ExecutionDb.frais))) or 0.0),
                    "comptes_avec_historique": n(select(func.count(func.distinct(persistance.HistoriqueValeurDb.utilisateur_id)))),
                    "regles_actives": n(select(func.count()).select_from(persistance.RegleDb).where(persistance.RegleDb.statut == "active")),
                    "actifs_les_plus_echanges": [{"symbole": s, "executions": c} for s, c in top]},
        "formation": [{"id": l["id"], "titre": l["titre"], "reussites": reussies.get(l["id"], 0), "score_moyen": float(scores[l["id"]]) if l["id"] in scores else None} for l in LECONS],
        "crises": {"scenarios": n(select(func.count()).select_from(ScenarioDb)), "scenarios_actifs": n(select(func.count()).select_from(ScenarioDb).where(ScenarioDb.actif.is_(True))),
                   "actualites": n(select(func.count()).select_from(ActualiteDb)), "actualites_fictives": n(select(func.count()).select_from(ActualiteDb).where(ActualiteDb.type_source.in_(("fictif", "scenario"))))},
        "donnees": {"actifs_charges": len(ctx.magasin.disponibles()), "actifs_total": len(ctx.univers.actifs), "debut": ctx.univers.debut.isoformat(), "fin": ctx.univers.fin.isoformat(),
                    "synthetiques": config.MARQUEUR_SYNTHETIQUE.exists(), "direct_actif": config.DIRECT_ACTIF, "direct_demo": config.DIRECT_DEMO,
                    "flux_direct": ctx.direct.etat() if ctx.direct is not None else None},
        "modeles": modeles_enregistres(),
        "parametres": {"capital_initial": config.CAPITAL_INITIAL_DEFAUT, "facteur_vitesse_par_defaut": config.FACTEUR_DEFAUT, "ticks_par_barre": config.NB_TICKS_PAR_BARRE,
                       "frais_points_de_base": FRAIS_BPS, "ecart_points_de_base": SPREAD_BPS, "duree_jeton_acces_minutes": config.ACCES_DUREE_MIN,
                       "duree_session_jours": config.REFRESH_DUREE_JOURS, "echecs_avant_verrouillage": config.MAX_ECHECS_CONNEXION,
                       "note": "Lecture seule : ces paramètres se règlent par variables d'environnement (SDM_*) puis redémarrage du serveur."},
    }


@routeur.get("/performances")
def performances(_a: Utilisateur = Depends(exiger("admin.utilisateurs")), session: Session = Depends(obtenir_session)):
    """Performance de chaque utilisateur (rendement, pire baisse, score de ligue), sans classement public."""
    lignes = []
    for u in session.scalars(select(Utilisateur).order_by(Utilisateur.nom)):
        perf = formation._performance(persistance.lire_historique(session, u.id), None)
        lignes.append({"id": u.id, "nom": u.nom, "email": u.email, "role": u.role, "actif": u.actif, "profil_risque": (u.profil_risque or {}).get("categorie"), "portefeuille": perf})
    return lignes
