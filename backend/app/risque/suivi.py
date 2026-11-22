"""Suivi du portefeuille depuis le début de la simulation : rendement total et indice de référence aux mêmes dates.

Le début est la PREMIÈRE TRANSACTION : avant elle, tout est en liquidités, et comparer à un indice qui aurait couru
pendant ce temps ferait perdre (ou gagner) l'élève contre un marché où il n'était pas encore.
Rendement total = valeur ÷ capital initial − 1 : latent, réalisé et frais compris (aucun versement n'existe dans le simulateur).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from ..marche.stockage import DonneeIndisponible

# Ordre d'affichage. `dividendes` : l'indice les réinvestit, comme les cours ajustés des actions du simulateur.
REFERENCES = (
    {"symbole": "^SP500TR", "nom": "S&P 500", "dividendes": True},
    {"symbole": "^GSPC", "nom": "S&P 500", "dividendes": False},          # secours si la série avec dividendes manque
    {"symbole": "^NDX", "nom": "Nasdaq 100", "dividendes": False},
    {"symbole": "^DJI", "nom": "Dow Jones", "dividendes": False},
    {"symbole": "^990100-USD-STRD", "nom": "MSCI World", "dividendes": False},
    {"symbole": "GC=F", "nom": "Or", "dividendes": False},
    {"symbole": "BTC-USD", "nom": "Bitcoin", "dividendes": False},
)


def references_disponibles(magasin) -> list[dict]:
    """Références qui ont des données ; le S&P 500 hors dividendes n'apparaît que si la version avec dividendes manque."""
    presentes = [r for r in REFERENCES if magasin.a_des_donnees(r["symbole"])]
    if any(r["symbole"] == "^SP500TR" for r in presentes):
        presentes = [r for r in presentes if r["symbole"] != "^GSPC"]
    return presentes


def debut_suivi(executions, t: datetime) -> datetime:
    """Instant de la première transaction connue à t ; sans transaction, la simulation commence à t."""
    return min((e.instant for e in executions if e.instant <= t), default=t)


def points_suivi(historique: list[dict], valo: dict, debut: datetime, t: datetime) -> list[dict]:
    """Courbe de valeur : capital au début, un point par jour passé, valeur actuelle à t."""
    actuel = {"jour": t.date().isoformat(), "instant": t.isoformat(timespec="seconds"), "equity": valo["equity"],
              "cash": valo["cash"], "valeur_positions": valo["valeur_positions"]}
    if debut >= t:
        return [actuel]
    capital = valo["capital_initial"]
    depart = {"jour": debut.date().isoformat(), "instant": debut.isoformat(timespec="seconds"), "equity": capital,
              "cash": capital, "valeur_positions": 0.0}
    milieu = [p for p in historique if depart["jour"] < p["jour"] < actuel["jour"]]
    return [depart, *milieu, actuel]


def valeur_reference(moteur, symbole: str, instant: datetime) -> float | None:
    """Niveau de la référence connu à cet instant précis : jamais la clôture d'une séance en cours."""
    try:
        return moteur.cotation(symbole, instant).prix
    except DonneeIndisponible:
        return None


def serie_reference(magasin, moteur, symbole: str, points: list[dict], capital: float) -> list[float | None]:
    """La référence ramenée au capital au premier point. Jours passés : clôture du jour. Début et maintenant : cours de l'instant."""
    if not points:
        return []
    base = valeur_reference(moteur, symbole, datetime.fromisoformat(points[0]["instant"]))
    if not base:
        return [None] * len(points)
    sortie: list[float | None] = []
    for i, p in enumerate(points):
        if i in (0, len(points) - 1):
            v = valeur_reference(moteur, symbole, datetime.fromisoformat(p["instant"]))
        else:
            v = magasin.derniere_cloture_avant(symbole, date.fromisoformat(p["jour"]) + timedelta(days=1))
        sortie.append(capital * v / base if v else None)
    return sortie


def resumer(ctx, points: list[dict], valo: dict, executions, debut: datetime, t: datetime,
            t_marche: datetime | None = None) -> dict:
    capital, equity = valo["capital_initial"], valo["equity"]
    rendement = equity / capital - 1 if capital else None
    references = []
    for r in references_disponibles(ctx.magasin):
        try:
            c = ctx.moteur.cotation(r["symbole"], t_marche or t)     # niveau affiché : marché du jour en Direct
        except DonneeIndisponible:
            continue
        base = valeur_reference(ctx.moteur, r["symbole"], debut)
        au_compte = valeur_reference(ctx.moteur, r["symbole"], t)     # comparaison : date du portefeuille
        depuis = au_compte / base - 1 if base and au_compte else None
        references.append({
            **r, "niveau": c.prix,
            "variation": c.prix / c.reference_variation - 1 if c.reference_variation else None,
            "depuis_debut": depuis,
            "ecart_points": (rendement - depuis) * 100 if rendement is not None and depuis is not None else None,
        })
    veille = next((p for p in reversed(points) if p["jour"] < t.date().isoformat()), None)
    return {
        "debut": debut.isoformat(timespec="seconds"),
        "a_commence": any(e.instant <= t for e in executions),
        "operations_futures": any(e.instant > t for e in executions),   # compte d'avant la règle « on ne recule pas »
        "jours": (t.date() - debut.date()).days,
        "capital_initial": capital, "valeur": equity, "gain": equity - capital, "rendement_total": rendement,
        "resultat_jour": equity - (veille["equity"] if veille else capital),
        "references": references,
    }


def mouvements(ctx, t: datetime, n: int = 3, seances: int = 30) -> list[dict]:
    """Les plus fortes hausses et baisses de la séance, avec une courte série passée pour la mini-courbe."""
    lignes = []
    for a in ctx.univers:
        if not a.tradable or not ctx.magasin.a_des_donnees(a.symbole):
            continue
        try:
            c = ctx.moteur.cotation(a.symbole, t)
        except DonneeIndisponible:
            continue
        if c.reference_variation:
            lignes.append({"symbole": a.symbole, "nom": a.nom, "classe": a.classe, "prix": c.prix,
                           "variation": (c.prix - c.reference_variation) / abs(c.reference_variation)})
    lignes.sort(key=lambda x: -x["variation"])
    choisis = lignes if len(lignes) <= 2 * n else lignes[:n] + lignes[-n:]
    for ligne in choisis:
        passe = ctx.magasin.barres_terminees(ligne["symbole"], t.date(), n=seances - 1)["close"]
        ligne["serie"] = [float(x) for x in passe] + [ligne["prix"]]
    return choisis
