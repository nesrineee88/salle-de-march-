"""Salle de marché : comptes, ordres (marché / limite / stop), exécution contre le carnet synthétique.

Règles de la version 1 (documentées dans docs/DECISIONS.md) :
- pas de vente à découvert, pas de levier (prévus au Sprint 3) ;
- un ordre au marché n'est accepté que si le marché est ouvert ; limites et stops peuvent attendre ;
- un ordre au marché consomme les niveaux du carnet : le prix moyen d'exécution dépend de la quantité (slippage) ;
- un stop déclenché devient un ordre au marché : sur un gap, il s'exécute AU PRIX DU MARCHÉ, pas au prix du stop ;
- le cash est réservé pour les achats en attente, la quantité pour les ventes en attente ;
- l'impact de marché déplace temporairement le prix de référence et se résorbe avec le temps simulé ;
- règles automatiques (stop-loss en %, prise de profit partielle, stop suiveur, achat complémentaire) : voir `poser_regle` ;
- l'état est enregistré en base par `exporter` / `importer` (voir persistance.py).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from ..marche.catalogue import Actif, Univers
from ..marche.moteur import MoteurMarche
from ..marche.stockage import DonneeIndisponible
from .carnet import (
    FRAIS_BPS,
    PROFONDEUR_NIVEAU_USD,
    Carnet,
    construire_carnet,
    echelle,
    frais,
)
from .modeles import (
    ACHAT, ACHAT_COMPLEMENTAIRE, ACTIVE, ANNULE, ANNULEE, DECLENCHEE, ECHEC, EN_ATTENTE, EPS, EXECUTE, LIMITE, MARCHE,
    PARTIEL, REJETE, STOP, STOP_LOSS, STOP_SUIVEUR, TAKE_PROFIT, TYPES_REGLE, VENTE,
    Compte, Execution, Ordre, Position, Regle,
)

DEMI_VIE_IMPACT_S = 1800.0           # l'impact de marché diminue de moitié en 30 minutes simulées
COEF_IMPACT = 0.0005                 # 5 points de base de déplacement par « niveau 1 » consommé
IMPACT_MAX = 0.05                    # plafonné à 5 % du prix


class SalleDeMarche:
    def __init__(
        self,
        moteur: MoteurMarche,
        univers: Univers,
        liquidites: dict[str, float] | None = None,
        pas_echantillon_s: float = 300.0,
        max_echantillons: int = 600,
    ):
        self._moteur = moteur
        self._univers = univers
        self._liquidites = liquidites or {}
        self._pas = pas_echantillon_s
        self._max_echantillons = max_echantillons
        self._comptes: dict[str, Compte] = {}
        self._prochain_id = 1
        self._prochaine_regle = 1
        self._impacts: dict[str, tuple[float, datetime]] = {}
        self._dernier_t: datetime | None = None
        self.version = 0          # augmente à chaque changement d'état : sert à savoir quand sauvegarder

    # ------------------------------------------------------------------ comptes
    def ouvrir_compte(self, compte_id: str, capital: float = 100_000.0) -> Compte:
        if compte_id in self._comptes:
            raise ValueError(f"le compte {compte_id} existe déjà")
        if not (capital > 0 and math.isfinite(capital)):
            raise ValueError("le capital doit être un nombre positif")
        self._comptes[compte_id] = Compte(compte_id, capital, capital)
        return self._comptes[compte_id]

    def compte(self, compte_id: str) -> Compte:
        try:
            return self._comptes[compte_id]
        except KeyError:
            raise KeyError(f"compte inconnu : {compte_id}") from None

    # ------------------------------------------------------------------ impact de marché
    def _impact(self, symbole: str, t: datetime) -> float:
        if symbole not in self._impacts:
            return 0.0
        valeur, t0 = self._impacts[symbole]
        if t < t0:                                   # le temps a reculé (aller à une date antérieure)
            del self._impacts[symbole]
            return 0.0
        return valeur * 0.5 ** ((t - t0).total_seconds() / DEMI_VIE_IMPACT_S)

    def _ajouter_impact(self, symbole: str, sens: str, notionnel: float, prix_ref: float, t: datetime) -> None:
        classe = self._univers[symbole].classe
        niveau_1 = PROFONDEUR_NIVEAU_USD[classe] * self._liquidites.get(symbole, 1.0)
        fraction = min(IMPACT_MAX, COEF_IMPACT * notionnel / niveau_1)
        delta = (1 if sens == ACHAT else -1) * echelle(prix_ref) * fraction
        self._impacts[symbole] = (self._impact(symbole, t) + delta, t)

    # ------------------------------------------------------------------ prix et carnet
    def _cotation(self, symbole: str, t: datetime):
        try:
            return self._moteur.cotation(symbole, t)
        except DonneeIndisponible:
            return None

    def carnet(self, symbole: str, t: datetime) -> tuple[Carnet, str]:
        if symbole not in self._univers:
            raise KeyError(symbole)
        cot = self._moteur.cotation(symbole, t)
        ref = cot.prix + self._impact(symbole, t)
        carnet = construire_carnet(
            symbole, self._univers[symbole].classe, ref, self._liquidites.get(symbole, 1.0)
        )
        return carnet, cot.statut

    # ------------------------------------------------------------------ réserves
    def _cash_reserve(self, compte: Compte, sauf: int | None = None) -> float:
        total = 0.0
        for o in compte.ordres.values():
            if not o.ouvert or o.sens != ACHAT or o.id == sauf:
                continue
            ref = o.prix_limite if o.type == LIMITE else o.prix_stop
            unite = max(ref, 0.0) * (1 + FRAIS_BPS[self._univers[o.symbole].classe] / 1e4)
            total += o.reste * unite
        return total

    def _quantite_reservee(self, compte: Compte, symbole: str, sauf: int | None = None) -> float:
        return sum(
            o.reste for o in compte.ordres.values()
            if o.ouvert and o.sens == VENTE and o.symbole == symbole and o.id != sauf
        )

    # ------------------------------------------------------------------ passage d'ordre
    def passer_ordre(
        self,
        compte_id: str,
        symbole: str,
        sens: str,
        quantite: float,
        t: datetime,
        type: str = MARCHE,
        prix_limite: float | None = None,
        prix_stop: float | None = None,
    ) -> Ordre:
        compte = self.compte(compte_id)
        ordre = Ordre(self._prochain_id, compte_id, symbole, sens, type, quantite,
                      prix_limite, prix_stop, cree_le=t)
        self._prochain_id += 1
        self.version += 1
        compte.ordres[ordre.id] = ordre
        self._dernier_t = t if self._dernier_t is None else max(self._dernier_t, t)

        motif = self._valider(compte, ordre, t)
        if motif:
            ordre.statut, ordre.motif = REJETE, motif
            return ordre

        if ordre.type == MARCHE:
            self._executer(compte, ordre, t, limite=None)
            if ordre.reste <= EPS:
                ordre.statut = EXECUTE
            elif ordre.quantite_executee > 0:
                ordre.statut, ordre.motif = ANNULE, "reste annulé : liquidité ou liquidités insuffisantes"
            else:
                ordre.statut, ordre.motif = REJETE, "aucune exécution possible (liquidité ou liquidités)"
        elif ordre.type == LIMITE:
            self._executer(compte, ordre, t, limite=ordre.prix_limite)
            self._finaliser(ordre)
        return ordre

    def _valider(self, compte: Compte, o: Ordre, t: datetime) -> str | None:
        if o.symbole not in self._univers:
            return "actif inconnu"
        actif = self._univers[o.symbole]
        if not actif.tradable:
            return "actif non négociable (indice de référence)"
        if o.sens not in (ACHAT, VENTE):
            return "sens invalide (achat ou vente)"
        if o.type not in (MARCHE, LIMITE, STOP):
            return "type d'ordre invalide (marche, limite ou stop)"
        if not (isinstance(o.quantite, (int, float)) and math.isfinite(o.quantite) and o.quantite > 0):
            return "la quantité doit être un nombre positif"

        for nom, valeur, requis in (("prix_limite", o.prix_limite, o.type == LIMITE),
                                    ("prix_stop", o.prix_stop, o.type == STOP)):
            if requis:
                if valeur is None or not math.isfinite(valeur):
                    return f"{nom} obligatoire pour ce type d'ordre"
                if valeur <= 0 and not actif.negatif_ok:
                    return f"{nom} doit être positif"

        cot = self._cotation(o.symbole, t)
        if cot is None:
            return "aucune cotation disponible pour cet actif à cette date"
        ref = cot.prix + self._impact(o.symbole, t)

        if o.type == MARCHE and cot.statut != "ouvert":
            return "marché fermé : un ordre au marché n'est pas possible (utiliser un ordre limite ou stop)"

        if o.type == STOP:
            if o.sens == VENTE and not o.prix_stop < ref:
                return "stop déjà atteint : un stop de vente doit être sous le prix actuel"
            if o.sens == ACHAT and not o.prix_stop > ref:
                return "stop déjà atteint : un stop d'achat doit être au-dessus du prix actuel"

        if o.sens == VENTE:
            pos = compte.positions.get(o.symbole)
            disponible = (pos.quantite if pos else 0.0) - self._quantite_reservee(compte, o.symbole, sauf=o.id)
            if o.quantite > disponible + EPS:
                return "position insuffisante (la vente à découvert n'est pas disponible)"
        else:
            unite_frais = FRAIS_BPS[actif.classe] / 1e4
            if o.type == MARCHE:
                estimation = self._cout_estime_marche(o, actif, ref)
            else:
                prix = o.prix_limite if o.type == LIMITE else o.prix_stop
                estimation = o.quantite * max(prix, 0.0) * (1 + unite_frais)
            if estimation > compte.cash - self._cash_reserve(compte, sauf=o.id) + EPS:
                return "liquidités insuffisantes"
        return None

    def _cout_estime_marche(self, o: Ordre, actif: Actif, ref: float) -> float:
        carnet = construire_carnet(o.symbole, actif.classe, ref, self._liquidites.get(o.symbole, 1.0))
        restant, cout = o.quantite, 0.0
        for n in carnet.ventes:
            q = min(restant, n.quantite)
            cout += q * (n.prix + FRAIS_BPS[actif.classe] * abs(n.prix) / 1e4)
            restant -= q
            if restant <= EPS:
                return cout
        derniere = carnet.ventes[-1].prix                  # carnet épuisé : on suppose le dernier prix
        return cout + restant * (derniere + FRAIS_BPS[actif.classe] * abs(derniere) / 1e4)

    # ------------------------------------------------------------------ exécution
    def _executer(self, compte: Compte, o: Ordre, t: datetime, limite: float | None) -> float:
        cot = self._cotation(o.symbole, t)
        if cot is None or cot.statut != "ouvert":
            return 0.0
        actif = self._univers[o.symbole]
        ref = cot.prix + self._impact(o.symbole, t)
        carnet = construire_carnet(o.symbole, actif.classe, ref, self._liquidites.get(o.symbole, 1.0))
        niveaux = carnet.ventes if o.sens == ACHAT else carnet.achats

        total, notionnel = 0.0, 0.0
        for n in niveaux:
            if o.reste <= EPS:
                break
            if limite is not None and ((o.sens == ACHAT and n.prix > limite) or (o.sens == VENTE and n.prix < limite)):
                break
            q = min(o.reste, n.quantite)
            if o.sens == ACHAT:
                cout_unitaire = n.prix + FRAIS_BPS[actif.classe] * abs(n.prix) / 1e4
                if cout_unitaire > 0:
                    dispo = compte.cash - self._cash_reserve(compte, sauf=o.id)
                    q = min(q, max(dispo, 0.0) / cout_unitaire)
            else:
                pos = compte.positions.get(o.symbole)
                q = min(q, pos.quantite if pos else 0.0)
            if q <= EPS:
                break
            self._fill(compte, o, actif, n.prix, q, t)
            total += q
            notionnel += abs(n.prix) * q
        if total > 0:
            self._ajouter_impact(o.symbole, o.sens, notionnel, ref, t)
        return total

    def _fill(self, compte: Compte, o: Ordre, actif: Actif, prix: float, q: float, t: datetime) -> None:
        f = frais(actif.classe, prix, q)
        pnl: float | None = None
        if o.sens == ACHAT:
            compte.cash -= prix * q + f
            pos = compte.positions.get(o.symbole)
            if pos is None:
                compte.positions[o.symbole] = Position(o.symbole, q, prix)
            else:
                nouvelle = pos.quantite + q
                pos.prix_moyen = (pos.quantite * pos.prix_moyen + q * prix) / nouvelle
                pos.quantite = nouvelle
        else:
            pos = compte.positions[o.symbole]
            compte.cash += prix * q - f
            pnl = (prix - pos.prix_moyen) * q
            compte.pnl_realise += pnl
            pos.quantite -= q
            if pos.quantite <= EPS:
                del compte.positions[o.symbole]
        compte.frais_cumules += f
        self.version += 1
        total = o.quantite_executee + q
        o.prix_moyen = ((o.prix_moyen or 0.0) * o.quantite_executee + prix * q) / total
        o.quantite_executee = total
        compte.executions.append(Execution(o.id, compte.id, o.symbole, o.sens, q, prix, f, t, pnl))

    @staticmethod
    def _finaliser(o: Ordre) -> None:
        if o.reste <= EPS:
            o.statut = EXECUTE
        elif o.quantite_executee > 0:
            o.statut = PARTIEL

    def annuler_ordre(self, compte_id: str, ordre_id: int) -> Ordre:
        compte = self.compte(compte_id)
        try:
            o = compte.ordres[ordre_id]
        except KeyError:
            raise KeyError(f"ordre inconnu : {ordre_id}") from None
        if not o.ouvert:
            raise ValueError(f"l'ordre {ordre_id} n'est plus annulable (statut : {o.statut})")
        o.statut, o.motif = ANNULE, "annulé par l'utilisateur"
        self.version += 1
        return o

    # ------------------------------------------------------------------ avancement du temps
    def avancer(self, t: datetime) -> list[Execution]:
        """Évalue les ordres en attente jusqu'à l'instant t, en échantillonnant le temps simulé."""
        if self._dernier_t is None or t <= self._dernier_t:
            if self._dernier_t is not None and t < self._dernier_t:
                self._impacts.clear()
            self._dernier_t = t
            return []
        ecart = (t - self._dernier_t).total_seconds()
        pas = max(self._pas, ecart / self._max_echantillons)
        n = max(1, math.ceil(ecart / pas))
        debut, nouvelles = self._dernier_t, []
        for i in range(1, n + 1):
            ts = debut + timedelta(seconds=min(i * pas, ecart))
            nouvelles += self._passe(ts)
        self._dernier_t = t
        return nouvelles

    def _passe(self, ts: datetime) -> list[Execution]:
        nouvelles: list[Execution] = []
        for compte in self._comptes.values():
            avant = len(compte.executions)
            for o in list(compte.ordres.values()):
                if o.ouvert and o.cree_le is not None and o.cree_le <= ts:
                    self._traiter_attente(compte, o, ts)
            self._traiter_regles(compte, ts)
            nouvelles += compte.executions[avant:]
        return nouvelles

    def _traiter_attente(self, compte: Compte, o: Ordre, ts: datetime) -> None:
        cot = self._cotation(o.symbole, ts)
        if cot is None or cot.statut != "ouvert":
            return
        ref = cot.prix + self._impact(o.symbole, ts)
        limite = None
        if o.type == STOP and not o.declenche:
            atteint = ref <= o.prix_stop if o.sens == VENTE else ref >= o.prix_stop
            if not atteint:
                return
            o.declenche = True                       # devient un ordre au marché
            self.version += 1
        elif o.type == LIMITE:
            limite = o.prix_limite
        self._executer(compte, o, ts, limite)
        self._finaliser(o)

    # ------------------------------------------------------------------ règles automatiques
    @staticmethod
    def _pct(x: float) -> str:
        return f"{abs(x) * 100:.1f}".replace(".", ",") + " %"

    def poser_regle(self, compte_id: str, symbole: str, type: str, seuil: float, part: float, t: datetime) -> Regle:
        """Pose (ou remplace) une règle automatique sur une position. Lève ValueError avec un message à afficher tel quel."""
        compte = self.compte(compte_id)
        if type not in TYPES_REGLE:
            raise ValueError("type de règle invalide")
        if symbole not in self._univers or not self._univers[symbole].tradable:
            raise ValueError("actif non négociable")
        pos = compte.positions.get(symbole)
        if pos is None:
            raise ValueError("aucune position sur cet actif : achetez d'abord, puis posez la règle")
        if pos.prix_moyen <= 0:
            raise ValueError("prix de revient non positif : une règle en pourcentage n'a pas de sens ici")
        if not (isinstance(seuil, (int, float)) and math.isfinite(seuil)):
            raise ValueError("seuil invalide")
        if not (isinstance(part, (int, float)) and math.isfinite(part) and 0 < part <= 1):
            raise ValueError("la part doit être comprise entre 0 et 100 % (0 exclu)")
        bornes = {STOP_LOSS: (-0.95, 0.0), TAKE_PROFIT: (0.0, 10.0), ACHAT_COMPLEMENTAIRE: (0.0, 10.0), STOP_SUIVEUR: (0.0, 0.95)}[type]
        if not (bornes[0] < seuil < bornes[1] or (type == STOP_LOSS and seuil == bornes[0])):
            raise ValueError("seuil hors limites (stop-loss et stop suiveur : moins de 95 % ; objectif : jusqu'à 1 000 %)")
        cot = self._cotation(symbole, t)
        if cot is None:
            raise ValueError("aucune cotation disponible pour cet actif à cette date")
        ref = cot.prix + self._impact(symbole, t)
        niveau = pos.prix_moyen * (1 + seuil)
        if type == STOP_LOSS and ref <= niveau:
            raise ValueError(f"stop-loss déjà dépassé : la position perd déjà {self._pct(ref / pos.prix_moyen - 1)}")
        if type in (TAKE_PROFIT, ACHAT_COMPLEMENTAIRE) and ref >= niveau:
            raise ValueError(f"objectif déjà atteint : la position gagne déjà {self._pct(ref / pos.prix_moyen - 1)}")
        for r in compte.regles.values():                      # une seule règle active par actif et par type
            if r.active and r.symbole == symbole and r.type == type:
                r.statut, r.motif = ANNULEE, "remplacée par une nouvelle règle"
        regle = Regle(self._prochaine_regle, compte_id, symbole, type, seuil, part, ACTIVE, t,
                      plus_haut=ref if type == STOP_SUIVEUR else None)
        self._prochaine_regle += 1
        compte.regles[regle.id] = regle
        self.version += 1
        return regle

    def annuler_regle(self, compte_id: str, regle_id: int) -> Regle:
        compte = self.compte(compte_id)
        try:
            r = compte.regles[regle_id]
        except KeyError:
            raise KeyError(f"règle inconnue : {regle_id}") from None
        if not r.active:
            raise ValueError(f"la règle {regle_id} n'est plus active (statut : {r.statut})")
        r.statut, r.motif = ANNULEE, "supprimée par l'utilisateur"
        self.version += 1
        return r

    def _traiter_regles(self, compte: Compte, ts: datetime) -> None:
        for r in list(compte.regles.values()):
            if not r.active or r.cree_le is None or r.cree_le > ts:
                continue
            pos = compte.positions.get(r.symbole)
            if pos is None:
                r.statut, r.motif = ANNULEE, "plus de position sur cet actif"
                self.version += 1
                continue
            cot = self._cotation(r.symbole, ts)
            if cot is None or cot.statut != "ouvert":
                continue                                       # comme un stop : la règle attend l'ouverture du marché
            ref = cot.prix + self._impact(r.symbole, ts)
            if r.type == STOP_SUIVEUR:
                if r.plus_haut is None or ref > r.plus_haut:
                    r.plus_haut = ref
                    self.version += 1
                atteint = ref <= r.plus_haut * (1 - r.seuil)
            elif r.type == STOP_LOSS:
                atteint = ref <= pos.prix_moyen * (1 + r.seuil)
            else:                                              # prise de profit ou achat complémentaire
                atteint = ref >= pos.prix_moyen * (1 + r.seuil)
            if atteint:
                self._declencher(compte, r, pos, ts)

    def _declencher(self, compte: Compte, r: Regle, pos: Position, ts: datetime) -> None:
        """Place l'ordre au marché de la règle (comme un stop : sur un gap, au prix du marché, pas au prix du seuil)."""
        if r.type == ACHAT_COMPLEMENTAIRE:
            sens, quantite = ACHAT, pos.quantite * r.part
        else:
            sens, quantite = VENTE, (pos.quantite if r.part >= 1 - EPS else pos.quantite * r.part)
            if r.type in (STOP_LOSS, STOP_SUIVEUR):            # sortie de protection : elle passe avant les ventes en attente
                for o in compte.ordres.values():
                    if o.ouvert and o.sens == VENTE and o.symbole == r.symbole:
                        o.statut, o.motif = ANNULE, "annulé : une règle de protection a vendu la position"
            else:
                quantite = min(quantite, pos.quantite - self._quantite_reservee(compte, r.symbole))
                if quantite <= EPS:
                    return                                     # quantité réservée par un autre ordre : on réessaiera
        ordre = Ordre(self._prochain_id, compte.id, r.symbole, sens, MARCHE, quantite, cree_le=ts, origine=f"regle:{r.id}")
        self._prochain_id += 1
        compte.ordres[ordre.id] = ordre
        self.version += 1
        motif = self._valider(compte, ordre, ts)
        if motif:
            ordre.statut, ordre.motif = REJETE, motif
            r.statut, r.declenchee_le, r.motif = ECHEC, ts, f"ordre refusé : {motif}"
            return
        self._executer(compte, ordre, ts, limite=None)
        if ordre.reste <= EPS:
            ordre.statut = EXECUTE
        elif ordre.quantite_executee > 0:
            ordre.statut, ordre.motif = ANNULE, "reste annulé : liquidité ou liquidités insuffisantes"
        else:
            ordre.statut, ordre.motif = REJETE, "aucune exécution possible (liquidité ou liquidités)"
        r.declenchee_le = ts
        if ordre.quantite_executee > EPS:
            r.statut = DECLENCHEE
            fr = lambda x, f: format(x, f).replace(".", ",")  # noqa: E731  (décimales à la française)
            r.motif = f"{'vendu' if sens == VENTE else 'acheté'} {fr(ordre.quantite_executee, 'g')} à {fr(ordre.prix_moyen, '.4f')} en moyenne"
        else:
            r.statut, r.motif = ECHEC, "aucune exécution possible (liquidité)"
        if r.symbole not in compte.positions:                  # position soldée : les autres règles n'ont plus d'objet (OCO)
            for autre in compte.regles.values():
                if autre.active and autre.symbole == r.symbole:
                    autre.statut, autre.motif = ANNULEE, "position clôturée par une autre règle"

    # ------------------------------------------------------------------ export / import (persistance)
    def exporter(self, compte_id: str) -> dict:
        """État du compte et du marché de ce bac, en types simples (JSON, base de données)."""
        c = self.compte(compte_id)
        iso = lambda d: d.isoformat() if d else None  # noqa: E731
        return {
            "capital_initial": c.capital_initial, "cash": c.cash, "pnl_realise": c.pnl_realise,
            "frais_cumules": c.frais_cumules, "prochain_ordre_id": self._prochain_id,
            "prochaine_regle_id": self._prochaine_regle,
            "dernier_t": iso(self._dernier_t),
            "impacts": {s: [v, iso(t)] for s, (v, t) in self._impacts.items()},
            "positions": [{"symbole": p.symbole, "quantite": p.quantite, "prix_moyen": p.prix_moyen}
                          for p in c.positions.values()],
            "ordres": [{"id": o.id, "symbole": o.symbole, "sens": o.sens, "type": o.type, "quantite": o.quantite,
                        "prix_limite": o.prix_limite, "prix_stop": o.prix_stop, "statut": o.statut,
                        "quantite_executee": o.quantite_executee, "prix_moyen": o.prix_moyen,
                        "declenche": o.declenche, "motif": o.motif, "origine": o.origine, "cree_le": iso(o.cree_le)}
                       for o in c.ordres.values()],
            "regles": [{"id": r.id, "symbole": r.symbole, "type": r.type, "seuil": r.seuil, "part": r.part,
                        "statut": r.statut, "cree_le": iso(r.cree_le), "declenchee_le": iso(r.declenchee_le),
                        "plus_haut": r.plus_haut, "motif": r.motif}
                       for r in c.regles.values()],
            "executions": [{"ordre_id": e.ordre_id, "symbole": e.symbole, "sens": e.sens, "quantite": e.quantite,
                            "prix": e.prix, "frais": e.frais, "instant": iso(e.instant), "pnl": e.pnl}
                           for e in c.executions],
        }

    def importer(self, compte_id: str, etat: dict) -> None:
        """Remplace l'état du compte par un état exporté plus tôt (restauration après redémarrage)."""
        c = self.compte(compte_id)
        dt = lambda s: datetime.fromisoformat(s) if s else None  # noqa: E731
        c.capital_initial, c.cash = etat["capital_initial"], etat["cash"]
        c.pnl_realise, c.frais_cumules = etat["pnl_realise"], etat["frais_cumules"]
        c.positions = {p["symbole"]: Position(p["symbole"], p["quantite"], p["prix_moyen"]) for p in etat["positions"]}
        c.ordres = {
            o["id"]: Ordre(o["id"], compte_id, o["symbole"], o["sens"], o["type"], o["quantite"], o["prix_limite"],
                           o["prix_stop"], o["statut"], o["quantite_executee"], o["prix_moyen"], o["declenche"],
                           dt(o["cree_le"]), o["motif"], o.get("origine"))
            for o in etat["ordres"]
        }
        c.regles = {
            r["id"]: Regle(r["id"], compte_id, r["symbole"], r["type"], r["seuil"], r["part"], r["statut"],
                           dt(r["cree_le"]), dt(r["declenchee_le"]), r.get("plus_haut"), r.get("motif"))
            for r in etat.get("regles", [])
        }
        self._prochaine_regle = max([etat.get("prochaine_regle_id", 1)] + [i + 1 for i in c.regles])
        c.executions = [
            Execution(e["ordre_id"], compte_id, e["symbole"], e["sens"], e["quantite"], e["prix"], e["frais"],
                      dt(e["instant"]), e.get("pnl"))
            for e in etat["executions"]
        ]
        self._prochain_id = etat["prochain_ordre_id"]
        self._dernier_t = dt(etat["dernier_t"])
        self._impacts = {s: (v, dt(t)) for s, (v, t) in etat["impacts"].items()}

    # ------------------------------------------------------------------ valorisation
    def valorisation(self, compte_id: str, t: datetime) -> dict:
        compte = self.compte(compte_id)
        positions, valeur_positions, pnl_latent = [], 0.0, 0.0
        for pos in compte.positions.values():
            cot = self._cotation(pos.symbole, t)
            marque = (cot.prix + self._impact(pos.symbole, t)) if cot else pos.prix_moyen
            valeur = pos.quantite * marque
            latent = (marque - pos.prix_moyen) * pos.quantite
            valeur_positions += valeur
            pnl_latent += latent
            positions.append({
                "symbole": pos.symbole, "quantite": pos.quantite, "prix_moyen": pos.prix_moyen,
                "prix_marche": marque, "valeur": valeur, "pnl_latent": latent,
            })
        equity = compte.cash + valeur_positions
        for p in positions:
            p["poids"] = p["valeur"] / equity if equity else 0.0
        return {
            "compte_id": compte.id,
            "instant": t.isoformat(timespec="seconds"),
            "capital_initial": compte.capital_initial,
            "cash": compte.cash,
            "cash_disponible": compte.cash - self._cash_reserve(compte),
            "valeur_positions": valeur_positions,
            "equity": equity,
            "pnl_total": equity - compte.capital_initial,
            "pnl_realise": compte.pnl_realise,
            "pnl_latent": pnl_latent,
            "frais_cumules": compte.frais_cumules,
            "positions": positions,
        }


def ordre_en_dict(o: Ordre) -> dict:
    return {
        "id": o.id, "compte_id": o.compte_id, "symbole": o.symbole, "sens": o.sens, "type": o.type,
        "quantite": o.quantite, "prix_limite": o.prix_limite, "prix_stop": o.prix_stop,
        "statut": o.statut, "quantite_executee": o.quantite_executee, "prix_moyen": o.prix_moyen,
        "declenche": o.declenche, "motif": o.motif, "origine": o.origine,
        "cree_le": o.cree_le.isoformat(timespec="seconds") if o.cree_le else None,
    }


def regle_en_dict(r: Regle) -> dict:
    iso = lambda d: d.isoformat(timespec="seconds") if d else None  # noqa: E731
    return {
        "id": r.id, "symbole": r.symbole, "type": r.type, "seuil": r.seuil, "part": r.part, "statut": r.statut,
        "cree_le": iso(r.cree_le), "declenchee_le": iso(r.declenchee_le), "plus_haut": r.plus_haut, "motif": r.motif,
    }
