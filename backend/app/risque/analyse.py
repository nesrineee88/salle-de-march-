"""Analyse complète d'un portefeuille à un instant simulé : assemble les indicateurs purs."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from . import indicateurs as ind

LIBELLE_MARCHE = {"action": "Actions", "crypto": "Cryptomonnaies", "matiere": "Matières premières", "indice": "Indices"}
LIQUIDITES = "Liquidités"
SEUIL_HHI_DIVERSIFIE = 0.15
SEUIL_HHI_MODERE = 0.25
SEUIL_POSITION_ALERTE = 0.25
SEUIL_SECTEUR_ALERTE = 0.40
SEUIL_SECTEUR_DANGER = 0.60
PART_SOUS_REPRESENTEE = 0.10


def _repartition(valo: dict, catalogue: dict[str, tuple[str, str]], cle: str) -> list[dict]:
    """Parts de la valeur totale : par marché, par secteur ou par position, liquidités comprises."""
    equity = valo["equity"]
    if not equity:
        return []
    parts: dict[str, float] = {}
    for p in valo["positions"]:
        classe, secteur = catalogue.get(p["symbole"], ("?", "?"))
        nom = {"marche": LIBELLE_MARCHE.get(classe, classe), "secteur": secteur, "position": p["symbole"]}[cle]
        parts[nom] = parts.get(nom, 0.0) + p["valeur"] / equity
    parts[LIQUIDITES] = valo["cash"] / equity
    return sorted(({"libelle": k, "part": v} for k, v in parts.items() if abs(v) > 1e-9), key=lambda x: -x["part"])


def _repartition_detail(valo: dict, catalogue: dict[str, tuple[str, str]], cle: str) -> list[dict]:
    equity = valo["equity"]
    if not equity:
        return []
    groupes: dict[str, dict[str, float]] = {}
    for p in valo["positions"]:
        classe, secteur = catalogue.get(p["symbole"], ("?", "?"))
        libelle = {"marche": LIBELLE_MARCHE.get(classe, classe), "secteur": secteur, "position": p["symbole"]}[cle]
        groupe = groupes.setdefault(libelle, {"valeur": 0.0, "pnl_latent": 0.0, "base": 0.0})
        groupe["valeur"] += p["valeur"]
        groupe["pnl_latent"] += p["pnl_latent"]
        groupe["base"] += abs(p["quantite"] * p["prix_moyen"])
    groupes[LIQUIDITES] = {"valeur": valo["cash"], "pnl_latent": 0.0, "base": 0.0}
    return sorted(
        (
            {
                "libelle": libelle,
                "valeur": groupe["valeur"],
                "part": groupe["valeur"] / equity,
                "pnl_latent": groupe["pnl_latent"],
                "pnl_latent_pct": groupe["pnl_latent"] / groupe["base"] if groupe["base"] else None,
            }
            for libelle, groupe in groupes.items()
            if abs(groupe["valeur"]) > 1e-9
        ),
        key=lambda x: -abs(x["part"]),
    )


def _niveau_hhi(hhi: float) -> str:
    if hhi < SEUIL_HHI_DIVERSIFIE:
        return "diversifie"
    if hhi <= SEUIL_HHI_MODERE:
        return "modere"
    return "concentre"


def concentration_portefeuille(positions: list[dict], catalogue: dict[str, tuple[str, str]]) -> dict | None:
    """Concentration par position et par secteur, normalisée sur l'exposition investie."""
    total = sum(abs(p["valeur"]) for p in positions)
    if total <= 0:
        return None

    poids_positions = {p["symbole"]: abs(p["valeur"]) / total for p in positions}
    secteurs: dict[str, float] = {}
    for p in positions:
        secteur = catalogue.get(p["symbole"], ("?", "?"))[1] or "Non classé"
        secteurs[secteur] = secteurs.get(secteur, 0.0) + abs(p["valeur"]) / total

    hhi = sum(p * p for p in poids_positions.values())
    hhi_secteurs = sum(p * p for p in secteurs.values())
    symbole_max = max(poids_positions, key=poids_positions.get)
    secteur_max = max(secteurs, key=secteurs.get)
    plus_grosse_position = {"symbole": symbole_max, "part": poids_positions[symbole_max]}
    plus_gros_secteur = {"secteur": secteur_max, "part": secteurs[secteur_max]}
    alertes = []
    if plus_grosse_position["part"] > SEUIL_POSITION_ALERTE:
        alertes.append({
            "niveau": "attention",
            "texte": f"{symbole_max} représente {plus_grosse_position['part']:.0%} de la partie investie (seuil pédagogique : 25 %).",
        })
    if plus_gros_secteur["part"] > SEUIL_SECTEUR_DANGER:
        alertes.append({
            "niveau": "danger",
            "texte": f"Le secteur {secteur_max} représente {plus_gros_secteur['part']:.0%} de la partie investie : concentration très élevée (plus de 60 %).",
        })
    elif plus_gros_secteur["part"] > SEUIL_SECTEUR_ALERTE:
        alertes.append({
            "niveau": "attention",
            "texte": f"Le secteur {secteur_max} représente {plus_gros_secteur['part']:.0%} de la partie investie (seuil pédagogique : 40 %).",
        })
    return {
        "positions": [{"symbole": s, "part": p} for s, p in poids_positions.items()],
        "secteurs": [{"secteur": s, "part": p} for s, p in sorted(secteurs.items(), key=lambda x: -x[1])],
        "hhi": hhi,
        "nb_effectif": 1.0 / hhi,
        "niveau": _niveau_hhi(hhi),
        "hhi_secteurs": hhi_secteurs,
        "nb_effectif_secteurs": 1.0 / hhi_secteurs,
        "niveau_secteurs": _niveau_hhi(hhi_secteurs),
        "plus_grosse_position": plus_grosse_position,
        "plus_gros_secteur": plus_gros_secteur,
        "alertes": alertes,
    }


def pistes_diversification(positions: list[dict], catalogue: dict[str, tuple[str, str]]) -> list[str]:
    """Pistes pédagogiques fondées sur les classes et secteurs absents ou sous-représentés."""
    total = sum(abs(p["valeur"]) for p in positions)
    if total <= 0:
        return ["Aucune position investie : les pistes de diversification apparaîtront après un premier achat."]

    classes: dict[str, float] = {}
    secteurs: dict[str, float] = {}
    for p in positions:
        classe, secteur = catalogue.get(p["symbole"], ("?", "?"))
        poids = abs(p["valeur"]) / total
        classes[classe] = classes.get(classe, 0.0) + poids
        secteurs[secteur] = secteurs.get(secteur, 0.0) + poids

    pistes = []
    for classe in ("action", "crypto", "matiere"):
        part = classes.get(classe, 0.0)
        nom = LIBELLE_MARCHE[classe]
        if part == 0:
            pistes.append(f"Piste : la classe {nom} est absente du portefeuille.")
        elif part < PART_SOUS_REPRESENTEE:
            pistes.append(f"Piste : la classe {nom} pèse moins de 10 % de la partie investie.")
    if len(pistes) < 5:
        secteurs_catalogue = sorted({secteur for _, secteur in catalogue.values() if secteur and secteur != "?"})
        for secteur in secteurs_catalogue:
            part = secteurs.get(secteur, 0.0)
            if part == 0:
                pistes.append(f"Piste : le secteur {secteur} est absent du portefeuille.")
            elif part < PART_SOUS_REPRESENTEE:
                pistes.append(f"Piste : le secteur {secteur} pèse moins de 10 % de la partie investie.")
            if len(pistes) == 5:
                break
    return pistes or ["Piste : comparez les poids des positions et des secteurs pour repérer les expositions dominantes."]


def simuler_choc_sectoriel(valo: dict, catalogue: dict[str, tuple[str, str]], secteur: str, choc_pct: float) -> dict:
    """Simule une variation sectorielle sans modifier les données ni le portefeuille."""
    valeur_secteur = sum(p["valeur"] for p in valo["positions"]
                        if catalogue.get(p["symbole"], ("?", "?"))[1] == secteur)
    variation = valeur_secteur * choc_pct / 100.0
    equity = valo["equity"]
    return {
        "secteur": secteur,
        "choc_pct": choc_pct,
        "valeur_secteur": valeur_secteur,
        "perte_montant": max(-variation, 0.0),
        "variation_portefeuille_pct": variation / equity * 100.0 if equity else 0.0,
        "valeur_avant": equity,
        "valeur_apres": equity + variation,
    }


def _beta_portefeuille(serie: pd.Series, benchmark: pd.Series | None, nom_indice: str) -> dict | None:
    """Bêta du portefeuille actuel contre l'indice, sur les dates communes, avec les points du nuage (r_indice, r_portefeuille)."""
    if benchmark is None or serie.empty:
        return None
    r_m = ind.rendements_actifs({"m": benchmark})["m"]
    commun = pd.concat([serie.rename("p"), r_m], axis=1, join="inner").dropna()
    b = ind.beta(commun["p"], commun["m"])
    if b is None:
        return None
    return {**b, "indice": nom_indice, "points": [[float(x), float(y)] for x, y in zip(commun["m"], commun["p"])]}


def analyser(valo: dict, historique: list[dict], series_prix: dict[str, pd.Series],
             catalogue: dict[str, tuple[str, str]], profil: dict | None,
             benchmark: pd.Series | None = None, nom_indice: str = "S&P 500") -> dict:
    """`valo` : sortie de SalleDeMarche.valorisation ; `historique` : points de valeur jusqu'à maintenant ;
    `series_prix` : clôtures passées de chaque actif détenu (jamais le futur) ; `catalogue` : symbole -> (classe, secteur) ;
    `benchmark` : clôtures passées de l'indice de référence (pour le bêta), None si indisponible."""
    avertissements: list[str] = []
    equity = valo["equity"]
    positions = valo["positions"]

    # Courbe de valeur : drawdown et statistiques
    points = [(datetime.fromisoformat(p["instant"]), p["equity"]) for p in historique]
    valeurs = [v for _, v in points] or [equity]
    dd = ind.drawdown(valeurs)
    stats = ind.statistiques_courbe(points)
    if stats is None:
        avertissements.append(
            f"Volatilité, Sharpe et Sortino demandent au moins {ind.MIN_POINTS_COURBE} points de valeur : "
            "avancez dans le temps en gardant des positions.")

    # Risque du portefeuille actuel sur le passé des actifs détenus
    poids = {p["symbole"]: p["valeur"] / equity for p in positions} if equity else {}
    risque = None
    correlations = None
    covariances = None
    beta = None
    jours_risque_disponibles = 0
    if poids:
        retours = ind.rendements_actifs({s: series_prix[s] for s in poids if s in series_prix}, ind.SEANCES_RISQUE)
        serie = ind.rendements_portefeuille(poids, retours)
        jours_risque_disponibles = int(serie.notna().sum())
        risque = ind.var_cvar(serie)
        if risque is None:
            avertissements.append(f"VaR et CVaR demandent au moins {ind.MIN_JOURS_VAR} jours d'historique commun aux actifs détenus.")
        else:
            risque["var_montant"] = risque["var"] * equity
            risque["cvar_montant"] = risque["cvar"] * equity
            et = ind.ecart_type(serie)
            risque["ecart_type_jour"] = et
            par_an = ind.seances_par_an(serie.index)
            risque["seances_an"] = par_an
            risque["volatilite_annuelle_seances"] = et * par_an ** 0.5 if et is not None else None
            risque["drawdown_poids"] = ind.drawdown_rendements(serie)
            risque["distribution"] = ind.histogramme(serie)
        beta = _beta_portefeuille(serie, benchmark, nom_indice)
        if len(retours.columns) >= 2 and len(retours) >= ind.MIN_JOURS_VAR:
            c = retours.corr()
            correlations = {"symboles": list(c.columns), "matrice": [[float(x) for x in ligne] for ligne in c.to_numpy()]}
            v = retours.cov()                     # covariance d'échantillon des rendements de séance (unité : rendement²)
            covariances = {"symboles": list(v.columns), "matrice": [[float(x) for x in ligne] for ligne in v.to_numpy()]}
    else:
        avertissements.append("Aucune position : les indicateurs de risque apparaîtront après un premier achat.")

    # Concentration et diversification (positions investies, liquidités exclues)
    conc = ind.concentration({p["symbole"]: p["valeur"] for p in positions})
    conc_detail = concentration_portefeuille(positions, catalogue)
    marches = {catalogue.get(p["symbole"], ("?", "?"))[0] for p in positions}
    diversification = None
    if conc is not None:
        diversification = {"score": ind.score_diversification(conc["hhi"], len(marches)),
                           "nb_positions": len(positions), "nb_marches": len(marches)}

    return {
        "instant": valo["instant"],
        "performance": {
            "rendement_total": equity / valo["capital_initial"] - 1 if valo["capital_initial"] else None,
            "drawdown_max": dd["max"], "drawdown_courant": dd["courant"], "points_courbe": len(points),
            **(stats or {"volatilite_annuelle": None, "rendement_annuel": None, "sharpe": None, "sortino": None}),
        },
        "risque": risque,
        "jours_risque_disponibles": jours_risque_disponibles,
        "jours_risque_minimum": ind.MIN_JOURS_VAR,
        "concentration": conc,
        "concentration_detail": conc_detail,
        "diversification": diversification,
        "repartition": {cle: _repartition(valo, catalogue, cle) for cle in ("marche", "secteur", "position")},
        "repartition_detail": {cle: _repartition_detail(valo, catalogue, cle) for cle in ("marche", "secteur", "position")},
        "pistes_diversification": pistes_diversification(positions, catalogue),
        "correlations": correlations,
        "covariances": covariances,
        "beta": beta,
        "profil": ind.comparer_profil(profil, dd["courant"], risque["var"] if risque else None),
        "avertissements": avertissements,
    }
