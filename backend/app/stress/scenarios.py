"""Catalogue des scénarios de crise : un TYPE de crise et une INTENSITÉ (modérée, sévère, extrême).

Chaque scénario dit quels leviers il actionne, avec quelles valeurs, et d'où vient chaque valeur.
Le moteur (`credit.simuler_banque`) n'applique que trois leviers, tous sur le portefeuille de prêts :

    q   quantile de la crise générale (Vasicek)       → PD de la crise
    Δ   hausse supplémentaire des défauts, en points   → ajoutée à la PD de la crise
    LGD perte en cas de défaut                         → plus haute quand les garanties perdent de la valeur

    PD stressée = min(1, PD_crise + Δ)       avec PD_crise = Vasicek(PD de départ, q), ou PD de départ si q est absent
    Perte       = prêts bruts × (PD stressée − PD de départ) × LGD

Ajouter un scénario : ajouter une entrée à SCENARIOS. Un scénario qui demande un autre canal (taux, marchés) demande
d'abord des données que le CSV n'a pas : il va dans NON_CALCULABLES avec la liste de ce qui manque.

Statuts d'origine : « publiee » (référence publiée, à relire dans le document), « hypothese » (choix pédagogique de l'équipe),
« mesuree » (calculée sur nos données), « manuel » (réglage de l'utilisateur).
"""
from __future__ import annotations

import math

LGD_BASE = 0.45
LGD_MIN = 0.25
LGD_MAX = 0.75

INTENSITES = {
    "moderee": {"nom": "Modérée", "quantile": 0.95, "lecture": "une mauvaise année sur 20"},
    "severe": {"nom": "Sévère", "quantile": 0.99, "lecture": "une année sur 100"},
    "extreme": {"nom": "Extrême", "quantile": 0.999, "lecture": "une année sur 1 000, le niveau de confiance retenu par Bâle"},
}

ORIGINES = {
    "quantile_bale": ("publiee", "Le quantile 99,9 % est le niveau de confiance de la formule de Bâle (approche notations internes). "
                                 "Document à relire : https://www.bis.org/bcbs/irbriskweight.pdf"),
    "quantile_frequence": ("hypothese", "Une intensité « une année sur 20 » ou « une année sur 100 » : choix de l'équipe pour graduer la crise."),
    "lgd_base": ("publiee", "45 % : perte en cas de défaut de référence de Bâle pour une créance senior non garantie (approche fondation). "
                            "Valeur reprise de mémoire, à relire dans les textes de Bâle."),
    "lgd_75": ("publiee", "75 % : valeur de Bâle pour une créance subordonnée (approche fondation), utilisée ici comme plafond. "
                          "Valeur reprise de mémoire, à relire."),
    "lgd_palier": ("hypothese", "Palier intermédiaire choisi par l'équipe entre 45 % et 75 %."),
    "hausse": ("hypothese", "Hausse des défauts choisie par l'équipe. +5 points reprend l'exemple chiffré de la consigne (12 % → 9,75 %)."),
    "hausse_combinee": ("hypothese", "Défauts supplémentaires propres au choc combiné, choisis par l'équipe."),
    "manuel": ("manuel", "LGD imposée par l'utilisateur dans le réglage avancé."),
}


def _q(intensite: str) -> dict:
    q = INTENSITES[intensite]["quantile"]
    return {"valeur": q, "origine": "quantile_bale" if q == 0.999 else "quantile_frequence"}


def _lgd(v: float) -> dict:
    return {"valeur": v, "origine": "lgd_base" if v == LGD_BASE else "lgd_75" if v == 0.75 else "lgd_palier"}


SCENARIOS = (
    {
        "cle": "recession", "nom": "Récession économique",
        "phrase": "L'activité recule : toutes les entreprises et tous les ménages deviennent plus fragiles en même temps.",
        "leviers": "PD de la crise générale (Vasicek)",
        "intensites": {i: {"quantile": _q(i), "hausse": {"valeur": 0.0, "origine": None}, "lgd": _lgd(LGD_BASE)} for i in INTENSITES},
    },
    {
        "cle": "defauts", "nom": "Hausse des défauts",
        "phrase": "Une part fixe de prêts sains bascule en défaut, quelle que soit la banque.",
        "leviers": "Défauts en plus, en points",
        "intensites": {i: {"quantile": {"valeur": None, "origine": None}, "hausse": {"valeur": h, "origine": "hausse"}, "lgd": _lgd(LGD_BASE)}
                       for i, h in (("moderee", 0.02), ("severe", 0.05), ("extreme", 0.10))},
    },
    {
        "cle": "actifs", "nom": "Dégradation des actifs",
        "phrase": "Une récession modérée, et des garanties (immobilier, stocks, titres) qui valent moins : chaque défaut coûte plus cher.",
        "leviers": "PD d'une récession modérée, LGD plus haute",
        "intensites": {i: {"quantile": _q("moderee"), "hausse": {"valeur": 0.0, "origine": None}, "lgd": _lgd(l)}
                       for i, l in (("moderee", 0.55), ("severe", 0.65), ("extreme", 0.75))},
    },
    {
        "cle": "combine", "nom": "Choc combiné",
        "phrase": "Récession, défauts supplémentaires et garanties dévalorisées en même temps.",
        "leviers": "PD de la crise, puis défauts en plus, puis LGD plus haute",
        "intensites": {i: {"quantile": _q(i), "hausse": {"valeur": h, "origine": "hausse_combinee"}, "lgd": _lgd(l)}
                       for i, h, l in (("moderee", 0.01, 0.55), ("severe", 0.02, 0.65), ("extreme", 0.03, 0.75))},
    },
)
PAR_CLE = {s["cle"]: s for s in SCENARIOS}

NON_CALCULABLES = (
    {"nom": "Hausse des taux", "manque": "les titres et sukuk détenus, leur durée, et la marge d'intérêt de chaque banque"},
    {"nom": "Baisse des marchés", "manque": "les titres et actions détenus par chaque banque"},
    {"nom": "Hausse du chômage", "manque": "la part des prêts aux particuliers"},
    {"nom": "COVID-19, crise financière", "manque": "des taux de défaut saoudiens historiques pour calibrer ces épisodes"},
)


def parametres(type_: str, intensite: str, lgd_force: float | None = None) -> dict:
    """Les paramètres réellement appliqués, chacun avec sa valeur, son statut et sa justification. ValueError si invalide."""
    if type_ not in PAR_CLE:
        raise ValueError(f"Scénario inconnu : « {type_} ». Choix : {', '.join(PAR_CLE)}.")
    if intensite not in INTENSITES:
        raise ValueError(f"Intensité inconnue : « {intensite} ». Choix : {', '.join(INTENSITES)}.")
    p = {k: dict(v) for k, v in PAR_CLE[type_]["intensites"][intensite].items()}
    if lgd_force is not None:
        if not (isinstance(lgd_force, (int, float)) and math.isfinite(lgd_force) and LGD_MIN <= lgd_force <= LGD_MAX):
            raise ValueError(f"La LGD doit être comprise entre {LGD_MIN:.0%} et {LGD_MAX:.0%}.")
        p["lgd"] = {"valeur": float(lgd_force), "origine": "manuel"}
    for v in p.values():
        statut, justification = ORIGINES[v["origine"]] if v["origine"] else (None, None)
        v["statut"], v["justification"] = statut, justification
    return {"type": type_, "nom": PAR_CLE[type_]["nom"], "intensite": intensite, "nom_intensite": INTENSITES[intensite]["nom"],
            "quantile": p["quantile"], "hausse": p["hausse"], "lgd": p["lgd"]}


def catalogue() -> dict:
    """Ce que l'écran affiche pour choisir : types, intensités, paramètres par défaut et scénarios pas encore calculables."""
    return {"types": [{"cle": s["cle"], "nom": s["nom"], "phrase": s["phrase"], "leviers": s["leviers"],
                       "intensites": {i: parametres(s["cle"], i) for i in INTENSITES}} for s in SCENARIOS],
            "intensites": [{"cle": k, **v} for k, v in INTENSITES.items()],
            "non_calculables": list(NON_CALCULABLES), "lgd_min": LGD_MIN, "lgd_max": LGD_MAX, "lgd_base": LGD_BASE}
