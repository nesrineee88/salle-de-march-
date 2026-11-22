"""Contexte de l'application : données de marché partagées et bac à sable de chaque utilisateur."""
from __future__ import annotations

import logging
import threading
import time as temps
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache

from fastapi import HTTPException

from . import config
from .marche.catalogue import Univers, charger_univers
from .marche.horloge import HorlogeSimulation
from .marche.moteur import MoteurMarche
from .marche.stockage import Magasin
from .trading import persistance
from .trading.salle import SalleDeMarche
from .utilisateurs.db import BaseUtilisateurs, obtenir_base
from .utilisateurs.modeles import Utilisateur

journal = logging.getLogger("salle_de_marche")
INTERVALLE_SAUVEGARDE_HORLOGE_S = 30.0       # horloge en marche : instant enregistré au plus toutes les 30 s
FIN_DE_JOURNEE = time(23, 59, 59)
PAS_TRAVERSEE_S = 900.0                      # ordres et règles revus tous les quarts d'heure pendant un saut de plusieurs jours


def maintenant_utc() -> datetime:
    """Heure réelle en UTC, sans fuseau (l'horloge simulée est en UTC naïf). Remplaçable dans les tests."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def donnees_ou_erreur(ctx: "Contexte", symbole: str) -> None:
    """404 si l'actif n'existe pas, 503 (avec la commande à lancer) si ses données de prix sont absentes."""
    if symbole not in ctx.univers:
        raise HTTPException(404, f"Actif inconnu : {symbole}")
    if not ctx.magasin.a_des_donnees(symbole):
        raise HTTPException(
            503, f"Données absentes pour {symbole}. Lancer : python -m pipeline tout (depuis backend/).")


@dataclass
class Bac:
    """Bac à sable d'un utilisateur : horloge + marché + compte. Le verrou évite que deux requêtes
    simultanées (l'interface en envoie plusieurs par seconde) modifient le même compte en même temps."""
    horloge: HorlogeSimulation
    salle: SalleDeMarche
    compte_id: str
    verrou: threading.RLock = field(default_factory=threading.RLock)
    signature_sauvee: tuple | None = None
    executions_sauvees: int = 0
    derniere_sauvegarde: float = 0.0
    historique: list[dict] = field(default_factory=list)        # points de valeur du portefeuille, un par jour simulé
    version_historique: int = -1                                # version du compte au dernier point enregistré
    direct: bool = False                                        # mode Direct, en lecture seule : le marché suit l'heure réelle, le compte et l'horloge du rejeu sont figés
    etat_persistance: str = "nouveau"                           # nouveau, restauré, aucune_sauvegarde, erreur_lecture


@dataclass
class Contexte:
    univers: Univers
    magasin: Magasin
    moteur: MoteurMarche
    base: BaseUtilisateurs | None = None          # None : pas de sauvegarde (tests du moteur seul)
    bacs: dict[int, Bac] = field(default_factory=dict)
    direct: object | None = None                  # FournisseurDirect, créé à la première activation du mode Direct
    _verrou: threading.RLock = field(default_factory=threading.RLock)

    @property
    def fin_simulation(self) -> datetime:
        return datetime.combine(self.univers.fin, time(23, 59, 59))

    def bac(self, utilisateur_id: int) -> Bac:
        with self._verrou:
            if utilisateur_id not in self.bacs:
                self.bacs[utilisateur_id] = self._nouveau_bac(utilisateur_id, restaurer=True)
            return self.bacs[utilisateur_id]

    def reinitialiser(self, utilisateur_id: int) -> Bac:
        with self._verrou:
            if self.base is not None:
                with self.base.session() as session:
                    persistance.supprimer(session, utilisateur_id)
            self.bacs[utilisateur_id] = self._nouveau_bac(utilisateur_id, restaurer=False)
            return self.bacs[utilisateur_id]

    def _nouveau_bac(self, utilisateur_id: int, restaurer: bool) -> Bac:
        compte_id = f"u{utilisateur_id}"
        salle = SalleDeMarche(self.moteur, self.univers)
        salle.ouvrir_compte(compte_id, config.CAPITAL_INITIAL_DEFAUT)
        horloge = HorlogeSimulation(
            datetime.combine(self.univers.debut, time(0, 0)), facteur=config.FACTEUR_DEFAUT, en_pause=True)
        bac = Bac(horloge, salle, compte_id)
        etat, historique = None, []
        if restaurer and self.base is not None:
            try:
                with self.base.session() as session:
                    etat = persistance.charger(session, utilisateur_id)
                    historique = persistance.lire_historique(session, utilisateur_id)
            except Exception:
                journal.exception("Lecture du bac à sable impossible (utilisateur %s)", utilisateur_id)
                bac.etat_persistance = "erreur_lecture"
        if etat is not None:
            salle.importer(compte_id, etat)
            # Après un redémarrage, le temps simulé reprend à l'instant enregistré, en pause.
            instant = min(datetime.fromisoformat(etat["horloge_instant"]), self.fin_simulation)
            debut = datetime.combine(self.univers.debut, time(0, 0))
            if instant < debut and not etat["executions"]:         # compte jamais utilisé, enregistré avant que le rejeu commence en 2019
                instant = debut
            bac.horloge = HorlogeSimulation(instant, facteur=etat["horloge_facteur"], en_pause=True)
            bac.executions_sauvees = len(etat["executions"])
            bac.signature_sauvee = self._signature(bac)
            bac.historique = historique
            bac.version_historique = salle.version
            bac.etat_persistance = "restauré"
        elif bac.etat_persistance != "erreur_lecture":
            bac.etat_persistance = "aucune_sauvegarde" if restaurer and self.base is not None else "nouveau"
        return bac

    @staticmethod
    def _signature(bac: Bac) -> tuple:
        h = bac.horloge
        return (bac.salle.version, h.facteur, h.en_pause, h.maintenant() if h.en_pause else None)

    # ------------------------------------------------------------------ sauvegarde
    def sauver_si_modifie(self, utilisateur_id: int, bac: Bac) -> None:
        """Enregistre l'état s'il a changé (ordre, exécution, horloge). À appeler avec le verrou du bac."""
        if self.base is None:
            return
        if bac.etat_persistance == "erreur_lecture":
            return
        signature = self._signature(bac)
        maintenant = temps.monotonic()
        a_change = signature != bac.signature_sauvee
        horloge_en_marche = not bac.horloge.en_pause and maintenant - bac.derniere_sauvegarde > INTERVALLE_SAUVEGARDE_HORLOGE_S
        if not (a_change or horloge_en_marche):
            return
        etat = bac.salle.exporter(bac.compte_id)
        etat["horloge_instant"] = bac.horloge.maintenant().isoformat()
        etat["horloge_facteur"] = bac.horloge.facteur
        try:
            with self.base.session() as session:
                bac.executions_sauvees = persistance.sauvegarder(session, utilisateur_id, etat, bac.executions_sauvees)
            bac.signature_sauvee, bac.derniere_sauvegarde = signature, maintenant
        except Exception:
            journal.exception("Sauvegarde du bac à sable impossible (utilisateur %s) : nouvel essai à la prochaine requête", utilisateur_id)
            raise HTTPException(
                503,
                "La modification n'a pas pu être enregistrée durablement. Aucune confirmation de transaction ne peut être donnée.",
            ) from None

    # ------------------------------------------------------------------ historique de la valeur
    @staticmethod
    def _point(bac: Bac, t: datetime) -> dict:
        valo = bac.salle.valorisation(bac.compte_id, t)
        return {"jour": t.date().isoformat(), "instant": t.isoformat(timespec="seconds"), "equity": valo["equity"],
                "cash": valo["cash"], "valeur_positions": valo["valeur_positions"]}

    def avancer(self, utilisateur_id: int, bac: Bac, t: datetime) -> None:
        """Amène le compte à t en passant par CHAQUE jour : un saut d'un an donne un an de courbe, pas deux points.
        Sans transaction ni ordre en attente, la valeur est le capital : il n'y a rien à enregistrer."""
        dernier = bac.salle.dernier_instant
        compte = bac.salle.compte(bac.compte_id)
        if (dernier is None or t.date() <= dernier.date()
                or not (compte.executions or any(o.ouvert for o in compte.ordres.values()))):
            bac.salle.avancer(t)
            return
        points, jour = [], dernier.date()
        while jour < t.date():
            fin_jour = datetime.combine(jour, FIN_DE_JOURNEE)
            if fin_jour > dernier:
                bac.salle.avancer_journee(fin_jour, pas_s=PAS_TRAVERSEE_S)
            points.append(self._point(bac, fin_jour))
            jour += timedelta(days=1)
        bac.salle.avancer(t)
        bac.historique.extend(points)
        if self.base is None:
            return
        try:
            with self.base.session() as session:
                persistance.enregistrer_points(session, utilisateur_id, points)
        except Exception:
            journal.exception("Enregistrement des jours traversés impossible (utilisateur %s)", utilisateur_id)

    def enregistrer_valeur(self, utilisateur_id: int, bac: Bac, t: datetime) -> None:
        """Ajoute un point à la courbe de valeur : un par jour simulé, remplacé après chaque transaction du même jour."""
        dernier = bac.historique[-1] if bac.historique else None
        nouveau_jour = dernier is None or dernier["jour"] != t.date().isoformat()
        transaction = bac.salle.version != bac.version_historique
        if not (nouveau_jour or transaction):
            return
        point = self._point(bac, t)
        if not nouveau_jour:
            bac.historique[-1] = point                      # même jour : on remplace par la valeur la plus récente
        else:
            bac.historique.append(point)
        bac.version_historique = bac.salle.version
        if self.base is None:
            return
        try:
            with self.base.session() as session:
                persistance.enregistrer_point(session, utilisateur_id, point)
        except Exception:
            journal.exception("Enregistrement de l'historique impossible (utilisateur %s)", utilisateur_id)

    def historique_visible(self, bac: Bac, t: datetime) -> list[dict]:
        """Les points jusqu'à l'instant simulé courant (après un retour en arrière, le « futur » est masqué).
        Un seul point par jour, triés par date : après des allers-retours dans le temps, un même jour peut avoir été
        enregistré deux fois ; on garde le plus récemment enregistré, comme la base (clé utilisateur + jour)."""
        limite = t.isoformat(timespec="seconds")
        par_jour = {p["jour"]: p for p in bac.historique if p["instant"] <= limite}
        return [par_jour[j] for j in sorted(par_jour)]


def refuser_en_direct(bac: Bac, action: str = "piloter le temps") -> None:
    if bac.direct:
        raise HTTPException(409, f"Le mode Direct est en lecture seule et suit l'heure réelle : revenez au rejeu pour {action}.")


def instant_compte(bac: Bac, t: datetime) -> datetime:
    """Instant auquel se lit le PORTEFEUILLE : en Direct il reste figé à la date du rejeu, seul le marché est à l'heure réelle."""
    return bac.horloge.maintenant() if bac.direct else t


@contextmanager
def verrouiller_bac(ctx: Contexte, utilisateur_id: int):
    """Verrou du bac COURANT. Une requête qui attendait pendant une réinitialisation ne doit pas retrouver
    l'ancien bac, puis le réenregistrer par-dessus le nouveau."""
    while True:
        bac = ctx.bac(utilisateur_id)
        with bac.verrou:
            if ctx.bac(utilisateur_id) is bac:
                yield bac
                return


@contextmanager
def acces_bac(ctx: Contexte, utilisateur: Utilisateur):
    """Accès exclusif au bac de l'utilisateur, ordres en attente évalués à son instant simulé, sauvegarde à la sortie.
    En Direct, t est l'heure réelle et le bac n'avance pas."""
    with verrouiller_bac(ctx, utilisateur.id) as bac:
        if bac.etat_persistance == "erreur_lecture":
            raise HTTPException(
                503,
                "Le portefeuille sauvegardé n'a pas pu être restauré. Le portefeuille n'est pas modifiable tant que la base est inaccessible.",
            )
        if bac.direct:
            t = maintenant_utc()
        else:
            t = bac.horloge.maintenant()
            fin = ctx.fin_simulation
            if t >= fin:                               # fin de la période rejouée : le temps s'arrête
                bac.horloge.aller_a(fin)
                bac.horloge.pause()
                t = fin
            ctx.avancer(utilisateur.id, bac, t)
        try:
            if not bac.direct:
                ctx.enregistrer_valeur(utilisateur.id, bac, t)
            yield bac, t
        finally:
            if not bac.direct:
                # jamais au-delà de la fin : une horloge en marche peut la dépasser pendant la requête
                ctx.enregistrer_valeur(utilisateur.id, bac, min(bac.horloge.maintenant(), ctx.fin_simulation))
            ctx.sauver_si_modifie(utilisateur.id, bac)


@lru_cache
def obtenir_contexte() -> Contexte:
    univers = charger_univers(config.UNIVERS_YAML)
    magasin = Magasin.charger(config.CLEAN_DIR, univers)
    ctx = Contexte(univers, magasin, MoteurMarche(magasin, univers, config.NB_TICKS_PAR_BARRE), base=obtenir_base())
    initialiser_scenarios(ctx)
    return ctx


def initialiser_scenarios(ctx: Contexte) -> None:
    """Au démarrage : applique les scénarios de crise actifs aux prix et, la toute première fois, charge les repères historiques.
    Une erreur ici (base pas encore migrée, par exemple) est journalisée sans empêcher le serveur de démarrer."""
    if ctx.base is None:
        return
    from sqlalchemy import func, select

    from .scenarios import service
    from .scenarios.modeles import ActualiteDb

    try:
        with ctx.base.session() as session:
            service.reappliquer(ctx, session)
            if session.scalar(select(func.count()).select_from(ActualiteDb)) == 0:
                service.semer_reperes(session)
    except Exception:
        journal.exception("Scénarios de crise et actualités indisponibles au démarrage (lancer : alembic upgrade head)")
