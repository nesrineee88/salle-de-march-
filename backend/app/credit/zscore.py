"""Score Z d'Altman : un signal d'alerte de faillite à partir de cinq ratios comptables.

Deux versions classiques :
 - Z (1968), sociétés industrielles cotées : 1,2·X1 + 1,4·X2 + 3,3·X3 + 0,6·X4 + 1,0·X5 ; sain au-dessus de 2,99, zone grise de 1,81 à 2,99, détresse en dessous de 1,81.
 - Z'' (1995), sociétés non industrielles ou émergentes : 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4 ; sain au-dessus de 2,6, zone grise de 1,1 à 2,6, détresse en dessous de 1,1.
Ratios : X1 fonds de roulement / total actif ; X2 bénéfices non distribués / total actif ; X3 résultat d'exploitation (EBIT) / total actif ;
X4 valeur de marché des capitaux propres / total des dettes (Z) ou valeur comptable des capitaux propres / total des dettes (Z'') ;
X5 chiffre d'affaires / total actif. Ce sont des repères statistiques anciens, pas une probabilité de défaut."""
from __future__ import annotations

from dataclasses import dataclass

MODELES = {
    "z": {"nom": "Z (1968) : industrielles cotées", "coef": {"X1": 1.2, "X2": 1.4, "X3": 3.3, "X4": 0.6, "X5": 1.0}, "sain": 2.99, "detresse": 1.81},
    "z2": {"nom": "Z'' (1995) : non industrielles et émergentes", "coef": {"X1": 6.56, "X2": 3.26, "X3": 6.72, "X4": 1.05}, "sain": 2.6, "detresse": 1.1},
}
LIBELLES = {
    "X1": "Fonds de roulement / total actif", "X2": "Bénéfices non distribués / total actif", "X3": "EBIT / total actif",
    "X4": "Capitaux propres / total des dettes", "X5": "Chiffre d'affaires / total actif",
}


@dataclass(frozen=True)
class Comptes:
    actif_courant: float
    passif_courant: float
    total_actif: float
    benefices_non_distribues: float
    ebit: float
    capitaux_propres: float          # valeur de marché pour Z, valeur comptable pour Z''
    total_dettes: float
    chiffre_affaires: float


def ratios(c: Comptes) -> dict[str, float]:
    if c.total_actif <= 0:
        raise ValueError("Le total de l'actif doit être strictement positif.")
    if c.total_dettes <= 0:
        raise ValueError("Le total des dettes doit être strictement positif.")
    return {
        "X1": (c.actif_courant - c.passif_courant) / c.total_actif,
        "X2": c.benefices_non_distribues / c.total_actif,
        "X3": c.ebit / c.total_actif,
        "X4": c.capitaux_propres / c.total_dettes,
        "X5": c.chiffre_affaires / c.total_actif,
    }


def calculer(c: Comptes, modele: str = "z") -> dict:
    if modele not in MODELES:
        raise ValueError("Modèle inconnu : choisissez « z » ou « z2 ».")
    m = MODELES[modele]
    r = ratios(c)
    contributions = [{"ratio": k, "libelle": LIBELLES[k], "valeur": r[k], "coefficient": coef, "contribution": coef * r[k]} for k, coef in m["coef"].items()]
    z = sum(x["contribution"] for x in contributions)
    zone = "sain" if z > m["sain"] else "detresse" if z < m["detresse"] else "grise"
    return {"modele": modele, "nom_modele": m["nom"], "z": z, "zone": zone, "seuil_sain": m["sain"], "seuil_detresse": m["detresse"],
            "contributions": contributions}


# Entreprises FICTIVES (jamais de vrais bilans), choisies pour illustrer les trois zones.
EXEMPLES = [
    {"nom": "Atelier Sidi SA (fictive, saine)", "comptes": Comptes(520, 300, 1000, 380, 150, 900, 450, 1300)},
    {"nom": "Textile Carthage (fictive, zone grise)", "comptes": Comptes(300, 250, 1000, 120, 80, 500, 600, 1100)},
    {"nom": "Chantier du Sud (fictive, en détresse)", "comptes": Comptes(180, 320, 1000, -150, -20, 100, 850, 600)},
]
