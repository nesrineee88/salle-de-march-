"""Vérification du risque AVANT un ordre d'achat : des alertes lisibles, jamais bloquantes (décision D25).

Les seuils sont pédagogiques, pas réglementaires : ils servent à faire réfléchir avant d'acheter, pas à interdire.
"""
from __future__ import annotations

LIMITE_POIDS_PAR_CATEGORIE = {"prudent": 0.15, "équilibré": 0.25, "dynamique": 0.35, "audacieux": 0.50}
LIMITE_POIDS_DEFAUT = 0.30          # sans profil de risque
BAISSE_DE_REFERENCE = 0.30          # scénario : l'actif perd 30 % (une hypothèse de réflexion, pas une prévision)
SEUIL_LIQUIDITES = 0.05             # moins de 5 % du portefeuille en liquidités après l'achat
SEUIL_VOLATILITE = 0.05             # amplitude moyenne d'une journée supérieure à 5 % du prix


def _pct(x: float, decimales: int = 0) -> str:
    return f"{x * 100:.{decimales}f}".replace(".", ",") + " %"


def verifier_achat(*, symbole: str, poids_apres: float, part_cash_apres: float, atr_pct: float | None,
                   profil: dict | None, baisse_stop: float | None, a_une_protection: bool) -> list[dict]:
    """`poids_apres` : part de l'actif dans le portefeuille après l'achat ; `part_cash_apres` : part des liquidités ;
    `atr_pct` : amplitude moyenne d'une journée en fraction du prix ; `baisse_stop` : baisse déclenchant le stop-loss
    déjà posé (fraction positive) ou None."""
    alertes: list[dict] = []
    categorie = profil.get("categorie") if profil else None
    limite = LIMITE_POIDS_PAR_CATEGORIE.get(categorie, LIMITE_POIDS_DEFAUT)
    if poids_apres > limite:
        alertes.append({"code": "concentration", "niveau": "attention", "texte": (
            f"{symbole} représenterait {_pct(poids_apres)} de votre portefeuille après cet achat"
            f"{f' (profil {categorie} : repère de {_pct(limite)})' if categorie else f' (repère : {_pct(limite)})'}. "
            "Une seule position pèse lourd : pensez à répartir.")})

    baisse = baisse_stop if baisse_stop else BAISSE_DE_REFERENCE
    perte = poids_apres * baisse
    hypothese = f"avec votre stop-loss à −{_pct(baisse)}" if baisse_stop else f"si {symbole} perdait {_pct(BAISSE_DE_REFERENCE)} (hypothèse de réflexion)"
    if profil:
        tolerance = profil["perte_max_toleree_pct"] / 100.0
        if perte > tolerance:
            alertes.append({"code": "tolerance", "niveau": "attention", "texte": (
                f"{hypothese[0].upper()}{hypothese[1:]}, le portefeuille perdrait environ {_pct(perte, 1)}, "
                f"au-delà de la perte maximale que vous acceptez ({_pct(tolerance)}).")})
    else:
        alertes.append({"code": "profil_absent", "niveau": "info", "texte": (
            f"{hypothese[0].upper()}{hypothese[1:]}, le portefeuille perdrait environ {_pct(perte, 1)}. "
            "Répondez au questionnaire de risque (page Compte) pour comparer à votre tolérance.")})

    if part_cash_apres < SEUIL_LIQUIDITES:
        alertes.append({"code": "liquidites", "niveau": "info", "texte": (
            f"Il ne vous resterait que {_pct(max(part_cash_apres, 0.0), 1)} en liquidités : peu de marge pour saisir une occasion ou absorber une baisse.")})
    if atr_pct is not None and atr_pct > SEUIL_VOLATILITE:
        alertes.append({"code": "volatilite", "niveau": "info", "texte": (
            f"Actif très agité : sa journée moyenne bouge d'environ {_pct(atr_pct, 1)} (ATR 14). Un stop trop proche risque d'être déclenché par le simple bruit.")})
    if not a_une_protection:
        alertes.append({"code": "protection", "niveau": "info", "texte": (
            "Aucune règle de protection sur cet actif. Après l'achat, vous pouvez poser un stop-loss automatique (par exemple −30 %).")})
    ordre = {"attention": 0, "info": 1}
    return sorted(alertes, key=lambda a: ordre[a["niveau"]])
