"""Remplaçant statistique (« surrogate ») du modèle structurel : des modèles d'apprentissage automatique apprennent à prédire la variation du CET1
à partir du profil de la banque et des chocs, puis on explique leurs prédictions.

Pourquoi : le modèle structurel est la référence (il est exact par construction) ; le remplaçant sert à comparer des familles de modèles (linéaire,
forêt aléatoire, arbres boostés), à montrer quelles variables comptent le plus, et à illustrer que ces modèles reproduisent un calcul connu.
Les données d'apprentissage sont tirées au hasard (banques et chocs inventés) : ce n'est PAS un modèle appris sur de vrais stress tests."""
from __future__ import annotations

import numpy as np

from .modele import GROUPES, Banque, stresser

NOMS_CARACTERISTIQUES = (
    ["islamique", "cet1", "densite_rwa", "rentabilite", "pd_base", "lgd", "part_trading"]
    + [f"part_{g}" for g in GROUPES]
    + ["part_murabaha", "part_stock_murabaha", "part_salam", "couverture_salam", "part_istisna", "repercussion_istisna", "part_psia", "lissage"]
    + [f"choc_{g}" for g in GROUPES]
)
LIBELLES = {
    "islamique": "Banque islamique", "cet1": "CET1 de départ", "densite_rwa": "Densité des actifs pondérés", "rentabilite": "Rentabilité avant provisions",
    "pd_base": "PD de départ", "lgd": "Perte en cas de défaut", "part_trading": "Position de marché ou exposition directe",
    "part_murabaha": "Part en mourabaha", "part_stock_murabaha": "Part de la mourabaha en stock", "part_salam": "Part en salam", "couverture_salam": "Couverture du salam",
    "part_istisna": "Part en istisna", "repercussion_istisna": "Répercussion de l'istisna", "part_psia": "Part financée par les PSIA", "lissage": "Lissage (DCR)",
    "part_energie": "Crédit : énergie", "part_metaux_precieux": "Crédit : métaux précieux", "part_metaux_industriels": "Crédit : métaux industriels",
    "part_agricole": "Crédit : agricole", "choc_energie": "Choc énergie", "choc_metaux_precieux": "Choc métaux précieux",
    "choc_metaux_industriels": "Choc métaux industriels", "choc_agricole": "Choc agricole",
}


def vecteur(b: Banque, chocs: dict) -> list[float]:
    return ([1.0 if b.type == "islamique" else 0.0, b.cet1, b.densite_rwa, b.rentabilite, b.pd_base, b.lgd, b.part_trading]
            + [b.part_groupes.get(g, 0.0) for g in GROUPES]
            + [b.part_murabaha, b.part_stock_murabaha, b.part_salam, b.couverture_salam, b.part_istisna, b.repercussion_istisna, b.part_psia, b.lissage]
            + [chocs[g] for g in GROUPES])


def tirer_banque(rng: np.random.Generator) -> Banque:
    isl = rng.random() < 0.5
    parts = rng.dirichlet(np.ones(4)) * rng.uniform(0.02, 0.25)
    b = Banque(nom="tirage", type="islamique" if isl else "conventionnelle", actifs=100.0, densite_rwa=rng.uniform(0.4, 0.8), cet1=rng.uniform(0.08, 0.18),
               rentabilite=rng.uniform(0.004, 0.02), pd_base=rng.uniform(0.01, 0.08), lgd=rng.uniform(0.3, 0.7), part_trading=rng.uniform(0, 0.04),
               part_groupes=dict(zip(GROUPES, map(float, parts))))
    if isl:
        b.part_murabaha, b.part_stock_murabaha = rng.uniform(0, 0.25), rng.uniform(0, 0.6)
        b.part_salam, b.couverture_salam = rng.uniform(0, 0.08), rng.uniform(0, 1)
        b.part_istisna, b.repercussion_istisna = rng.uniform(0, 0.12), rng.uniform(0, 1)
        b.part_psia, b.lissage = rng.uniform(0, 0.6), rng.uniform(0, 0.6)
    return b


def jeu_apprentissage(n: int, graine: int = 11) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(graine)
    X, y = [], []
    while len(X) < n:
        b = tirer_banque(rng)
        chocs = {g: float(rng.uniform(-0.6, 0.4)) for g in GROUPES}
        X.append(vecteur(b, chocs))
        y.append(stresser(b, chocs)["variation_points"])
    return np.array(X), np.array(y)


_CACHE: dict = {}


def entrainer(n: int = 3000, graine: int = 11) -> dict:
    """Compare régression ridge, forêt aléatoire et arbres boostés sur un jeu de test mis de côté. Résultat gardé en mémoire."""
    cle = (n, graine)
    if cle in _CACHE:
        return _CACHE[cle]
    try:
        from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
        from sklearn.inspection import permutation_importance
        from sklearn.linear_model import Ridge
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError("scikit-learn n'est pas installé : lancez « pip install -r requirements-ia.txt » dans backend.") from exc
    X, y = jeu_apprentissage(n, graine)
    Xa, Xt, ya, yt = train_test_split(X, y, test_size=0.25, random_state=graine)
    modeles = {
        "ridge": ("Régression linéaire (ridge)", make_pipeline(StandardScaler(), Ridge(alpha=1.0))),
        "foret": ("Forêt aléatoire", RandomForestRegressor(n_estimators=80, max_depth=12, random_state=graine, n_jobs=1)),
        "boost": ("Arbres boostés", GradientBoostingRegressor(n_estimators=150, max_depth=3, random_state=graine)),
    }
    comparaison, ajustes = [], {}
    for cle_m, (nom, m) in modeles.items():
        m.fit(Xa, ya)
        p = m.predict(Xt)
        comparaison.append({"cle": cle_m, "nom": nom, "r2": float(r2_score(yt, p)), "erreur_absolue_moyenne": float(mean_absolute_error(yt, p))})
        ajustes[cle_m] = m
    meilleur = max(comparaison, key=lambda c: c["r2"])["cle"]
    imp = permutation_importance(ajustes[meilleur], Xt, yt, n_repeats=3, random_state=graine, n_jobs=1)
    importance = sorted(({"variable": v, "libelle": LIBELLES[v], "importance": float(i)} for v, i in zip(NOMS_CARACTERISTIQUES, imp.importances_mean)), key=lambda d: -d["importance"])
    resultat = {"comparaison": comparaison, "meilleur": meilleur, "importance": importance[:10], "n": n, "ecart_type_cible": float(np.std(yt)),
                "_modeles": ajustes, "_mediane": np.median(X, axis=0)}
    _CACHE[cle] = resultat
    return resultat


def expliquer(b: Banque, chocs: dict, modele: str, n: int = 3000, graine: int = 11) -> dict:
    """Prédiction du remplaçant et explication locale : écart de prédiction quand chaque variable est remplacée par la médiane du jeu d'apprentissage
    (attribution par perturbation, approximative), à comparer à la ventilation exacte du modèle structurel."""
    r = entrainer(n, graine)
    if modele not in r["_modeles"]:
        raise ValueError("Modèle inconnu : ridge, foret ou boost.")
    m = r["_modeles"][modele]
    x = np.array(vecteur(b, chocs))
    base = float(m.predict(x.reshape(1, -1))[0])
    attributions = []
    for j, nom in enumerate(NOMS_CARACTERISTIQUES):
        x2 = x.copy()
        x2[j] = r["_mediane"][j]
        attributions.append({"variable": nom, "libelle": LIBELLES[nom], "valeur": float(x[j]), "effet": base - float(m.predict(x2.reshape(1, -1))[0])})
    attributions.sort(key=lambda a: -abs(a["effet"]))
    return {"modele": modele, "prediction_points": base, "reference_structurelle_points": stresser(b, chocs)["variation_points"], "attributions": attributions[:10],
            "note": "Effet = prédiction moins prédiction obtenue en remplaçant la variable par la médiane du jeu d'apprentissage. Approximatif : les variables agissent ensemble."}
