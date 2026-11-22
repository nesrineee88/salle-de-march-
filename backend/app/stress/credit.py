"""Stress de crédit bancaire : PD, perte, CET1 après choc. Fonctions pures.

Question posée : le portefeuille de PRÊTS de chaque banque reste-t-il stable en crise ?

    1. PD de départ   = prêts en défaut / (prêts en défaut + prêts sains)
    2. PD stressée    = Vasicek au quantile du scénario
    3. Perte          = prêts bruts × (PD stressée − PD de départ) × LGD
    4. CET1 après     = (capital CET1 − perte) / actifs pondérés
    5. Pire cas       = (capital − seuil × actifs pondérés) / (prêts bruts × LGD)

Hypothèses : LGD et corrélation « entreprises » de Bâle appliquées à tous les prêts, actifs pondérés constants, un an,
pas de second tour, ni provisions existantes ni bénéfices futurs pour compenser. Ce n'est pas un test réglementaire.
"""
from __future__ import annotations

import math
from statistics import NormalDist

NORMALE = NormalDist()
LGD_DEFAUT = 0.45
LGD_MIN = 0.25
LGD_MAX = 0.75
SEUIL_MINIMUM = 0.045
SEUIL_COUSSIN = 0.07
QUANTILES = {"central": None, "adverse": 0.95, "severe": 0.99, "extreme": 0.999}
SCENARIOS = (
    {"cle": "central", "nom": "Central", "quantile": None, "phrase": "Aucun choc : les chiffres publiés."},
    {"cle": "adverse", "nom": "Adverse", "quantile": 0.95, "phrase": "Une mauvaise année sur 20."},
    {"cle": "severe", "nom": "Sévère", "quantile": 0.99, "phrase": "Une année sur 100."},
    {"cle": "extreme", "nom": "Extrême", "quantile": 0.999, "phrase": "Une année sur 1 000, le niveau de confiance de Bâle."},
)


def correlation(pd: float) -> float:
    """Corrélation d'actifs « entreprises » de Bâle : 24 % si la PD est très basse, 12 % si elle est haute."""
    w = (1 - math.exp(-50 * pd)) / (1 - math.exp(-50))
    return 0.12 * w + 0.24 * (1 - w)


def pd_stressee(pd: float, quantile: float | None) -> float:
    """Vasicek : la PD d'une année aussi mauvaise que le quantile demandé."""
    if quantile is None or pd <= 0:
        return pd
    r = correlation(pd)
    return NORMALE.cdf((NORMALE.inv_cdf(pd) + math.sqrt(r) * NORMALE.inv_cdf(quantile)) / math.sqrt(1 - r))


def cet1_apres(capital: float, rwa: float, prets: float, hausse_defauts: float, lgd: float = LGD_DEFAUT,
               titres: float = 0.0, baisse_titres: float = 0.0) -> float:
    perte_credit = prets * hausse_defauts * lgd
    perte_marche = titres * abs(baisse_titres)
    return (capital - perte_credit - perte_marche) / rwa


def hausse_qui_casse(capital: float, rwa: float, prets: float, lgd: float = LGD_DEFAUT, seuil: float = SEUIL_MINIMUM) -> float:
    """Pire cas à l'envers : la hausse du taux de défaut qui amène le CET1 au seuil."""
    return max(0.0, (capital - seuil * rwa) / (prets * lgd))


# ------------------------------------------------------------------ assemblage par banque
def valider(scenario: str, lgd: float) -> None:
    """ValueError si le scénario est inconnu ou la LGD hors de [25 % ; 75 %]."""
    if scenario not in QUANTILES:
        raise ValueError(f"Scénario inconnu : « {scenario} ». Choix : {', '.join(QUANTILES)}.")
    if not (isinstance(lgd, (int, float)) and math.isfinite(lgd) and LGD_MIN <= lgd <= LGD_MAX):
        raise ValueError(f"La LGD doit être comprise entre {LGD_MIN:.0%} et {LGD_MAX:.0%}.")


def statut(ratio: float) -> str:
    return "sous_minimum" if ratio < SEUIL_MINIMUM else "sous_coussin" if ratio < SEUIL_COUSSIN else "ok"


def simuler_banque(b, quantile: float | None = None, hausse: float = 0.0, lgd: float = LGD_DEFAUT, scenario: str = "",
                   parametres: dict | None = None) -> dict:
    """Moteur général, pour une banque réelle (objet de `donnees_reelles`). Les chocs s'appliquent dans cet ordre, sur une seule PD :

        1. crise générale    PD_crise    = Vasicek(PD de départ, quantile), ou PD de départ sans quantile
        2. défauts en plus   PD stressée = min(1, PD_crise + hausse)
        3. garanties         Perte       = prêts bruts × (PD stressée − PD de départ) × LGD

    Chaque prêt ne fait défaut qu'une fois (une seule PD, plafonnée à 100 %) et ne perd qu'une fois (une seule LGD) :
    pas de double comptage. La perte se ventile EXACTEMENT en trois canaux, à LGD de base 45 % :
        crise    = prêts × (PD_crise − PD de départ) × 45 %
        défauts  = prêts × (PD stressée − PD_crise) × 45 %
        garanties = prêts × (PD stressée − PD de départ) × (LGD − 45 %)
    Montants dans l'unité du CSV (milliers de SAR) ; `*_md` en milliards."""
    prets = b.prets_bruts
    pd0 = b.pd_depart
    pd_crise = pd_stressee(pd0, quantile)
    pd1 = min(1.0, pd_crise + hausse)
    hausse_totale = pd1 - pd0
    perte = prets * hausse_totale * lgd
    apres = cet1_apres(b.cet1_capital, b.actifs_ponderes, prets, hausse_totale, lgd)
    md = 1e-6 if b.unite == "milliers" else 1e-3 if b.unite == "millions" else 1.0
    base = LGD_DEFAUT
    canaux = [
        {"cle": "crise", "libelle": "Crise générale (plus de défauts)", "perte": prets * (pd_crise - pd0) * base},
        {"cle": "defauts", "libelle": "Défauts supplémentaires", "perte": prets * (pd1 - pd_crise) * base},
        {"cle": "garanties", "libelle": "Garanties dévalorisées (LGD plus haute)", "perte": prets * hausse_totale * (lgd - base)},
    ]
    canaux = [c | {"perte_md": c["perte"] * md} for c in canaux if abs(c["perte"]) > 1e-12]
    restant = b.cet1_capital - perte
    besoin_4_5 = max(0.0, SEUIL_MINIMUM * b.actifs_ponderes - restant)
    besoin_7 = max(0.0, SEUIL_COUSSIN * b.actifs_ponderes - restant)
    return {
        "besoin_4_5_md": besoin_4_5 * md, "besoin_7_md": besoin_7 * md,
        "conclusion": conclusion_banque(b.nom, apres, besoin_4_5 * md, besoin_7 * md,
                                        hausse_qui_casse(b.cet1_capital, b.actifs_ponderes, prets, lgd, SEUIL_MINIMUM) - hausse_totale),
        "cle": b.cle, "banque": b.nom, "type": b.type, "scenario": scenario, "lgd": lgd, "quantile": quantile, "hausse_ajoutee": hausse,
        "parametres": parametres,
        "cet1_avant": b.cet1_capital / b.actifs_ponderes, "cet1_publie": b.cet1_ratio, "cet1_apres": apres,
        "variation_points": (apres - b.cet1_capital / b.actifs_ponderes) * 100,
        "pd_avant": pd0, "pd_crise": pd_crise, "pd_stressee": pd1, "hausse_defauts": hausse_totale, "correlation": correlation(pd0),
        "perte": perte, "perte_md": perte * md,
        "capital_avant": b.cet1_capital, "capital_apres": b.cet1_capital - perte,
        "capital_avant_md": b.cet1_capital * md, "capital_apres_md": (b.cet1_capital - perte) * md,
        "actifs_ponderes": b.actifs_ponderes, "actifs_ponderes_md": b.actifs_ponderes * md,
        "prets_bruts": prets, "prets_bruts_md": prets * md, "prets_defaut_md": b.prets_defaut * md,
        "statut": statut(apres),
        "hausse_vers_4_5": hausse_qui_casse(b.cet1_capital, b.actifs_ponderes, prets, lgd, SEUIL_MINIMUM),
        "hausse_vers_7": hausse_qui_casse(b.cet1_capital, b.actifs_ponderes, prets, lgd, SEUIL_COUSSIN),
        "devise": b.devise, "unite": b.unite, "canaux": canaux,
        # explication exacte : capital de départ − pertes par canal = capital restant (la somme tombe juste)
        "barres": [{"libelle": "Capital CET1 de départ", "valeur_md": b.cet1_capital * md}]
                  + [{"libelle": c["libelle"], "valeur_md": -c["perte_md"]} for c in canaux]
                  + [{"libelle": "Capital restant", "valeur_md": (b.cet1_capital - perte) * md}],
    }


def _pc(v: float) -> str:
    return ("−" if v < 0 else "") + f"{abs(v) * 100:.2f}".replace(".", ",") + " %"


def _md(v: float) -> str:
    return f"{v:.2f}".replace(".", ",") + " Md"


def conclusion_banque(nom: str, ratio: float, besoin_4_5_md: float, besoin_7_md: float, marge: float) -> str:
    """La solution, en une phrase : le verdict, puis le capital à reconstituer pour revenir au seuil.
    Capital à reconstituer = max(0, seuil × actifs pondérés − capital restant). Calcul mécanique, pas un conseil."""
    if ratio >= SEUIL_COUSSIN:
        points_marge = f"{max(0.0, marge) * 100:.1f}".replace(".", ",")
        return (f"{nom} résiste : son CET1 reste à {_pc(ratio)}, au-dessus de 7 %. Aucun capital à reconstituer. "
                f"Il faudrait encore {points_marge} points de défauts en plus pour la faire descendre à 4,5 %.")
    if ratio >= SEUIL_MINIMUM:
        return (f"{nom} reste au-dessus du minimum de 4,5 % mais passe sous 7 % ({_pc(ratio)}). "
                f"Solution : reconstituer {_md(besoin_7_md)} de capital CET1 pour revenir à 7 %.")
    absorbe = " Les pertes dépassent tout son capital CET1." if ratio < 0 else ""
    return (f"{nom} passe sous le minimum de 4,5 % ({_pc(ratio)}).{absorbe} Solution : reconstituer {_md(besoin_4_5_md)} de capital CET1 "
            f"pour revenir à 4,5 %, et {_md(besoin_7_md)} pour revenir à 7 %.")


def conclusion_groupe(resultats: list[dict]) -> dict:
    """Bilan de la comparaison : combien résistent, la plus fragile, le capital total à reconstituer pour remettre tout le monde à 7 %."""
    if not resultats:
        return {"texte": "", "besoin_7_md": 0.0, "besoin_4_5_md": 0.0}
    n = len(resultats)
    ok = sum(r["cet1_apres"] >= SEUIL_COUSSIN for r in resultats)
    pire = min(resultats, key=lambda r: r["cet1_apres"])
    total_7 = sum(r["besoin_7_md"] for r in resultats)
    total_4_5 = sum(r["besoin_4_5_md"] for r in resultats)
    texte = f"{ok} banque{'s' if ok > 1 else ''} sur {n} rest{'ent' if ok > 1 else 'e'} au-dessus de 7 %. "
    texte += f"La plus fragile est {pire['banque']}, à {_pc(pire['cet1_apres'])}. "
    if total_7 > 0:
        texte += f"Solution : reconstituer au total {_md(total_7)} de capital CET1 pour remettre toutes ces banques à 7 %"
        texte += f", dont {_md(total_4_5)} juste pour revenir au minimum de 4,5 %." if total_4_5 > 0 else "."
    else:
        texte += "Aucun capital à reconstituer dans ce scénario."
    return {"texte": texte, "besoin_7_md": total_7, "besoin_4_5_md": total_4_5,
            "sous_7": n - ok, "sous_4_5": sum(r["cet1_apres"] < SEUIL_MINIMUM for r in resultats), "pire": pire["cle"]}


def stresser_banque(b, scenario: str = "adverse", lgd: float = LGD_DEFAUT) -> dict:
    """Ancienne entrée (Central, Adverse, Sévère, Extrême) : une récession au quantile du scénario. Gardée pour la matrice et les tests."""
    valider(scenario, lgd)
    return simuler_banque(b, QUANTILES[scenario], 0.0, lgd, scenario)


def simuler_scenario(b, p: dict) -> dict:
    """Applique les paramètres de `scenarios.parametres(type, intensite)` à une banque."""
    return simuler_banque(b, p["quantile"]["valeur"], p["hausse"]["valeur"], p["lgd"]["valeur"], f"{p['type']}:{p['intensite']}", p)


def moyennes_par_groupe(resultats: list[dict]) -> dict:
    """Moyenne SIMPLE (non pondérée) par type de banque."""
    sortie = {}
    for t in ("islamique", "conventionnelle"):
        g = [r for r in resultats if r["type"] == t]
        if not g:
            continue
        avant = sum(r["cet1_avant"] for r in g) / len(g)
        apres = sum(r["cet1_apres"] for r in g) / len(g)
        sortie[t] = {"nb": len(g), "cet1_avant": avant, "cet1_apres": apres, "points_perdus": (avant - apres) * 100,
                     "au_dessus_7": sum(r["cet1_apres"] >= SEUIL_COUSSIN for r in g)}
    return sortie


def phrase_duel(groupes: dict) -> str:
    """Phrase calculée à partir des moyennes, jamais écrite en dur."""
    i, c = groupes.get("islamique"), groupes.get("conventionnelle")
    if not i or not c:
        return ""
    if abs(i["points_perdus"] - c["points_perdus"]) < 0.3:
        return "Les deux groupes perdent presque autant, l'écart final vient surtout du capital de départ."
    moins = "islamiques" if i["points_perdus"] < c["points_perdus"] else "conventionnelles"
    return f"Dans ce scénario, les banques {moins} perdent en moyenne moins de points de CET1."


def _assembler(resultats: list[dict], **entete) -> dict:
    groupes = moyennes_par_groupe(resultats)
    return entete | {"resultats": resultats, "groupes": groupes, "phrase": phrase_duel(groupes), "conclusion": conclusion_groupe(resultats),
                     "seuil_minimum": SEUIL_MINIMUM, "seuil_coussin": SEUIL_COUSSIN}


def comparer(banques: list, scenario: str = "adverse", lgd: float = LGD_DEFAUT) -> dict:
    return _assembler([stresser_banque(b, scenario, lgd) for b in banques], scenario=scenario, lgd=lgd)


def comparer_scenario(banques: list, p: dict) -> dict:
    """Le scénario (type et intensité) appliqué aux banques choisies, avec les paramètres réellement utilisés."""
    return _assembler([simuler_scenario(b, p) for b in banques], scenario=f"{p['type']}:{p['intensite']}", lgd=p["lgd"]["valeur"],
                      parametres=p)


def matrice(banques: list, lgd: float = LGD_DEFAUT) -> dict:
    valider("central", lgd)
    lignes = []
    for b in banques:
        cases = {s["cle"]: stresser_banque(b, s["cle"], lgd) for s in SCENARIOS}
        lignes.append({"cle": b.cle, "banque": b.nom, "type": b.type,
                       "cases": {k: {"cet1_apres": r["cet1_apres"], "statut": r["statut"]} for k, r in cases.items()},
                       "hausse_vers_4_5": cases["central"]["hausse_vers_4_5"], "hausse_vers_7": cases["central"]["hausse_vers_7"]})
    classement = sorted(lignes, key=lambda x: x["hausse_vers_4_5"])
    return {"lgd": lgd, "scenarios": list(SCENARIOS), "lignes": lignes, "classement": [x["cle"] for x in classement],
            "sous_7": {s["cle"]: sum(x["cases"][s["cle"]]["cet1_apres"] < SEUIL_COUSSIN for x in lignes) for s in SCENARIOS}}


def synthese_xai(scenario: str = "extreme", lgd: float = LGD_DEFAUT) -> dict:
    """Pour l'assistant XAI (poste A) : les vraies banques sous un scénario, la plus fragile et ses barres exactes.
    `canaux` suit le contrat de `modele.stresser` : [{libelle, perte}], en milliards de la devise."""
    from . import donnees_reelles
    c = comparer(donnees_reelles.charger(), scenario, lgd)
    res = sorted(c["resultats"], key=lambda r: r["cet1_apres"])
    pire = res[0]
    return {"scenario": scenario, "lgd": lgd, "resultats": res, "groupes": c["groupes"], "phrase": c["phrase"],
            "pire": pire, "canaux": [{"libelle": "Perte de crédit", "perte": pire["perte_md"]}],
            "sous_7": sum(r["cet1_apres"] < SEUIL_COUSSIN for r in res),
            "formule": "CET1 après = (capital CET1 − prêts bruts × (PD stressée − PD de départ) × LGD) ÷ actifs pondérés",
            "limite": "Vraies banques saoudiennes (rapports Pilier 3, 31/12/2025). LGD et corrélation de Bâle : hypothèses. "
                      "Pas un test réglementaire."}
