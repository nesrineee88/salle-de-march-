"""Règles du jeu : fonctions pures.

L'état n'est jamais stocké : il est RECALCULÉ depuis le journal de la partie (séance atteinte, ordres, choix). Le navigateur
ne peut donc ni l'écrire ni le falsifier, une partie reprend après un redémarrage, et le montage alternatif est simplement
le même calcul avec un choix remplacé.

 - À la séance i le joueur voit les clôtures jusqu'à i. Tout ce qu'il décide part à l'OUVERTURE de la séance i + 1.
 - Le même jour, les ventes passent avant les achats. Un achat est réduit aux liquidités disponibles.
 - Le double immobile garde les positions de départ jusqu'au générique.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .donnees import Bobine

CAPITAL = 100_000.0
MISE = 10_000.0                                  # montant d'un achat libre
PART_VENTE = 0.5                                 # part d'une vente libre
PART_REDUIRE = 0.25
PART_RENFORCER = 0.20
MAX_ORDRES_PAR_SEANCE = 8
PERTES_MAX = (5, 10, 15, 20, 25)                 # bornes du plan : 99 % donnerait des points gratuits
DELAI_LIMITE = 5                                 # séances pour réagir après avoir franchi sa limite
EPS = 1e-6
SEUIL_SORTI = 0.01                               # moins de 1 % en actifs risqués : le joueur est dehors

ACTES = {
    "tenir": {"nom": "Rester assis", "detail": "Vous ne touchez à rien."},
    "reduire": {"nom": "Réduire sans fuir", "detail": "25 % des positions risquées passent en liquidités."},
    "renforcer": {"nom": "Profiter de la baisse", "detail": "20 % de vos liquidités vont sur l’actif principal."},
    "sortir": {"nom": "Quitter la salle", "detail": "Vous vendez tout, quel que soit le prix."},
}
QUESTIONS = ("La salle murmure. Que faites-vous ?", "Les gens courent vers la sortie. Et vous ?", "Dernière décision avant le générique.")
PLAFOND_PLAN_NON_TENU = 55                       # sous 50 de sang-froid : avoir eu de la chance n'est pas avoir bien décidé
POIDS_NOTE = {"resultat": 0.40, "protection": 0.35, "plan": 0.25}


@dataclass
class Etat:
    cash: float
    q: dict[str, float]
    q0: dict[str, float]
    cash0: float
    valeurs: list[float] = field(default_factory=list)
    expositions: list[float] = field(default_factory=list)      # part risquée du portefeuille à chaque clôture
    frais: float = 0.0
    executions: list[dict] = field(default_factory=list)


def depart(b: Bobine) -> tuple[float, dict[str, float]]:
    q = {a.cle: CAPITAL * a.depart / b.clotures[a.cle][0] for a in b.film.actifs}
    return CAPITAL * (1 - sum(a.depart for a in b.film.actifs)), q


def _instructions(b: Bobine, acte: str, cash: float) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    """(ventes : clé et part, achats : clé et montant) d'un choix."""
    if acte == "reduire":
        return [(a.cle, PART_REDUIRE) for a in b.film.actifs if a.risque], []
    if acte == "sortir":
        return [(a.cle, 1.0) for a in b.film.actifs], []
    if acte == "renforcer":
        return [], [(b.film.cible_renforcer, cash * PART_RENFORCER)]
    if acte == "tenir":
        return [], []
    raise ValueError(f"choix inconnu : {acte}")


def rejouer(b: Bobine, jusqu_a: int, frais: float, ordres: list[dict], choix: list[dict]) -> Etat:
    """État à la clôture de la séance `jusqu_a`. Ne lit aucun cours au-delà."""
    cash, q = depart(b)
    risques = [a.cle for a in b.film.actifs if a.risque]
    e = Etat(cash, dict(q), dict(q), cash, [CAPITAL], [sum(a.depart for a in b.film.actifs if a.risque)])
    par_jour: dict[int, list[dict]] = {}
    for o in ordres:
        par_jour.setdefault(o["jour"], []).append(o)
    choix_jour = {c["jour"]: c["acte"] for c in choix}
    for i in range(1, jusqu_a + 1):
        ventes: list[tuple[str, float]] = []
        achats: list[tuple[str, float]] = []
        for o in par_jour.get(i - 1, []):
            if o["sens"] == "vente":
                ventes.append((o["cle"], PART_VENTE))
            else:
                achats.append((o["cle"], MISE))
        if i - 1 in choix_jour:
            v, a = _instructions(b, choix_jour[i - 1], e.cash)
            ventes += v
            achats += a
        for cle, part in ventes:
            px, qte = b.ouvertures[cle][i], e.q[cle] * part
            brut = qte * px
            if brut < EPS:
                continue
            e.q[cle] -= qte
            e.cash += brut * (1 - frais)
            e.frais += brut * frais
            e.executions.append({"jour": i, "cle": cle, "sens": "vente", "montant": brut, "prix": px})
        for cle, montant in achats:
            m = min(montant, e.cash)
            if m < 1:
                continue
            px = b.ouvertures[cle][i]
            brut = m / (1 + frais)
            e.q[cle] += brut / px
            e.cash -= m
            e.frais += m - brut
            e.executions.append({"jour": i, "cle": cle, "sens": "achat", "montant": m, "prix": px})
        valeur = e.cash + sum(qte * b.clotures[c][i] for c, qte in e.q.items())
        e.valeurs.append(valeur)
        e.expositions.append(sum(e.q[c] * b.clotures[c][i] for c in risques) / valeur if valeur > EPS else 0.0)
    return e


def double_immobile(b: Bobine, jusqu_a: int) -> list[float]:
    cash, q = depart(b)
    return [cash + sum(qte * b.clotures[c][i] for c, qte in q.items()) for i in range(jusqu_a + 1)]


def arret_en_attente(b: Bobine, jour: int, choix: list[dict]) -> int | None:
    """Numéro de l'arrêt qui attend une décision, ou None."""
    n = len(choix)
    return n if n < len(b.arrets) and jour >= b.arrets[n] else None


def pire_baisse(valeurs: list[float]) -> float:
    pic, pire = valeurs[0], 0.0
    for v in valeurs:
        pic = max(pic, v)
        pire = max(pire, 1 - v / pic)
    return pire


def baisses(valeurs: list[float]) -> list[float]:
    pic, out = valeurs[0], []
    for v in valeurs:
        pic = max(pic, v)
        out.append(1 - v / pic)
    return out


def respect_du_plan(b: Bobine, plan: dict, etat: Etat, ordres: list[dict], choix: list[dict]) -> dict:
    """Le sang-froid : le joueur a-t-il fait ce qu'il avait annoncé ? Jamais « a-t-il eu raison ».

     - à chaque arrêt : sous sa limite, sa réaction annoncée ; au-delà, réduire ou sortir ;
     - on regarde ce qu'il détient vraiment : « rester assis » sans plus aucun actif risqué, c'est être sorti ;
     - s'il franchit sa limite : avoir allégé ses actifs risqués, ou être déjà sorti, dans les cinq séances ;
     - ses ordres libres sur les actifs risqués ne contredisent pas le plan.
    """
    limite, reaction = plan["perte_max"] / 100, plan["reaction"]
    chute = baisses(etat.valeurs)
    risques = {a.cle for a in b.film.actifs if a.risque}
    franchie = next((i for i, x in enumerate(chute) if x >= limite), None)
    regles = []
    for k, c in enumerate(choix):
        j = c["jour"]
        au_dela = chute[j] >= limite
        attendu = ("reduire", "sortir") if au_dela else (reaction,)
        dehors = c["acte"] != "renforcer" and etat.expositions[j] < SEUIL_SORTI
        if dehors:
            tenu = reaction in ("reduire", "sortir") or (franchie is not None and franchie <= j)
        else:
            tenu = c["acte"] in attendu
        regles.append({
            "regle": f"Arrêt {k + 1}", "note": 1.0 if tenu else 0.0,
            "attendu": " ou ".join(ACTES[a]["nom"] for a in attendu),
            "fait": "Déjà sorti" if dehors else ACTES[c["acte"]]["nom"], "limite_franchie": au_dela,
        })
    if franchie is not None and franchie < len(chute) - 1:
        fin = franchie + DELAI_LIMITE
        allege = any(franchie <= o["jour"] <= fin and o["sens"] == "vente" and o["cle"] in risques for o in ordres) or any(
            franchie <= c["jour"] <= fin and c["acte"] in ("reduire", "sortir") for c in choix)
        deja_sorti = etat.expositions[franchie] < SEUIL_SORTI
        regles.append({"regle": f"Limite de {plan['perte_max']} % franchie", "note": 1.0 if allege or deja_sorti else 0.0,
                       "attendu": f"Alléger en {DELAI_LIMITE} séances", "fait": "Allégé" if allege or deja_sorti else "Rien",
                       "limite_franchie": True})
    contraires = 0
    for o in ordres:
        if o["cle"] not in risques:
            continue
        if chute[min(o["jour"], len(chute) - 1)] >= limite:
            contraires += o["sens"] == "achat"
        elif reaction in ("tenir", "renforcer"):
            contraires += o["sens"] == "vente"
        else:
            contraires += o["sens"] == "achat"
    regles.append({"regle": "Ordres libres", "note": max(0.0, 1 - contraires / 3), "attendu": "Aucun ordre contraire au plan",
                   "fait": f"{contraires} contraire{'s' if contraires > 1 else ''}" if contraires else "Aucun", "limite_franchie": False})
    return {"note": 100 * sum(r["note"] for r in regles) / len(regles), "regles": regles}


def noter(b: Bobine, frais: float, plan: dict | None, ordres: list[dict], choix: list[dict]) -> dict:
    """Le générique chiffré. Sans plan (le jury décide), pas de note : on ne note pas quelqu'un sur le plan d'un autre."""
    etat = rejouer(b, b.dernier, frais, ordres, choix)
    temoin = double_immobile(b, b.dernier)
    fin, pire = etat.valeurs[-1], pire_baisse(etat.valeurs)
    resultat = min(100.0, max(0.0, 50 + (fin / temoin[-1] - 1) * 250))
    protection = min(100.0, max(0.0, 100 - pire * 250))
    discipline = respect_du_plan(b, plan, etat, ordres, choix) if plan else None
    note, plafonnee = None, False
    if discipline:
        note = round(POIDS_NOTE["resultat"] * resultat + POIDS_NOTE["protection"] * protection + POIDS_NOTE["plan"] * discipline["note"])
        if discipline["note"] < 50 and note > PLAFOND_PLAN_NON_TENU:
            note, plafonnee = PLAFOND_PLAN_NON_TENU, True
    actes = [c["acte"] for c in choix]
    if discipline and discipline["note"] >= 99.9:
        profil = "Le Métronome"
    elif len(ordres) > 12:
        profil = "L’Agité"
    elif actes.count("renforcer") >= 2:
        profil = "Le Téméraire"
    elif "sortir" in actes:
        profil = "Le Fuyard"
    elif pire < 0.10:
        profil = "Le Gardien"
    elif "renforcer" in actes:
        profil = "Le Contrarien"
    else:
        profil = "Le Stoïque"
    if note is None:
        prix = "Verdict du jury"
    else:
        prix = ("Palme d’or" if note >= 78 else "Prix du jury" if note >= 62 else "Sélection officielle" if note >= 45
                else "À retourner au montage")
    return {"note": note, "prix": prix, "profil": profil, "valeur": fin, "double": temoin[-1], "rendement": fin / CAPITAL - 1,
            "pire_baisse": pire, "frais": etat.frais, "resultat": resultat, "protection": protection, "plan": discipline,
            "poids": POIDS_NOTE, "plafonnee": plafonnee, "plafond": PLAFOND_PLAN_NON_TENU}


def montage(b: Bobine, frais: float, ordres: list[dict], choix: list[dict]) -> list[dict]:
    """Pour chaque arrêt, les trois autres fins : on change UNE décision et on garde tout le reste."""
    reel = rejouer(b, b.dernier, frais, ordres, choix).valeurs[-1]
    sortie = []
    for k, c in enumerate(choix):
        autres = []
        for acte in ACTES:
            if acte == c["acte"]:
                continue
            variante = [*choix[:k], {**c, "acte": acte}, *choix[k + 1:]]
            valeurs = rejouer(b, b.dernier, frais, ordres, variante).valeurs
            autres.append({"acte": acte, "nom": ACTES[acte]["nom"], "valeur": valeurs[-1], "ecart": valeurs[-1] - reel,
                           "courbe": [round(v, 2) for v in valeurs]})
        sortie.append({"arret": k, "jour": c["jour"], "acte": c["acte"], "nom": ACTES[c["acte"]]["nom"], "autres": autres})
    return sortie
