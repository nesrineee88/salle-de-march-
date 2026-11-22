"""Prix d'une protection du portefeuille contre une baisse, de deux façons. Fonctions pures.

Le contrat : si le panier assuré perd plus que la franchise sur la durée, il est payé, dans la limite du plafond.
    indemnité (part du capital) = min(plafond, max(0, perte − franchise))

1. Méthode des assureurs, sur les vrais cours passés : on rejoue le contrat sur toutes les périodes passées de même durée,
   avec le panier actuel et ses poids actuels.
    fréquence = périodes où la perte dépasse la franchise / périodes observées
    coût moyen = indemnité moyenne de ces périodes
    prime pure = fréquence × coût moyen ;  prime payée = prime pure × (1 + marge) / (1 − frais)
   Aucun sinistre observé : le contrat n'est PAS tarifé. Inventer une fréquence donnerait n'importe quel prix ; on renvoie
   seulement le prix en bourse et la pire perte observée.
2. La même protection en bourse : l'indemnité est exactement celle d'un « put spread » (acheter une option de vente au prix
   1 − franchise, en vendre une au prix 1 − franchise − plafond). Prix de Black-Scholes, taux nul, volatilité historique du panier.

Les périodes se chevauchent : elles ne sont pas indépendantes. Le passé ne contient pas le prochain krach.
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

MARGE = 0.20
FRAIS = 0.15
PAS_SEANCES = 5                   # un départ de période toutes les 5 séances
MIN_PERIODES = 20
SEANCES_VOLATILITE = 250
NORMALE = NormalDist()


def indemnite(perte: float, franchise: float, plafond: float) -> float:
    return min(plafond, max(0.0, perte - franchise))


def put_black_scholes(prix_exercice: float, volatilite: float, annees: float) -> float:
    """Option de vente sur un panier valant 1, taux nul."""
    if prix_exercice <= 0:
        return 0.0
    s = volatilite * math.sqrt(annees)
    if s <= 0:
        return max(0.0, prix_exercice - 1.0)
    d1 = (math.log(1.0 / prix_exercice) + s * s / 2) / s
    return prix_exercice * NORMALE.cdf(-(d1 - s)) - NORMALE.cdf(-d1)


def _panier(cours: dict[str, pd.Series]) -> pd.DataFrame:
    df = pd.DataFrame(cours).sort_index().ffill().dropna()
    df.index = pd.to_datetime(df.index)
    return df


def tarifer(cours: dict[str, pd.Series], valeurs: dict[str, float], franchise: float, plafond: float, jours: int) -> dict:
    """`cours` : clôtures passées par actif ; `valeurs` : valeur détenue aujourd'hui par actif."""
    capital = float(sum(valeurs.values()))
    poids = pd.Series({s: v / capital for s, v in valeurs.items()})
    df = _panier(cours)[list(poids.index)]
    if df.empty:
        raise ValueError("Aucun cours commun à toutes les positions du panier.")
    fin = df.index[-1]
    departs = [d for d in df.index[::PAS_SEANCES] if d + pd.Timedelta(days=jours) <= fin]
    if len(departs) < MIN_PERIODES:
        raise ValueError(f"Pas assez d'historique commun : {len(departs)} périodes de {jours} jours, il en faut {MIN_PERIODES}.")

    periodes = []
    for d in departs:
        arrivee = df.loc[: d + pd.Timedelta(days=jours)].iloc[-1]
        rendement = float((poids * (arrivee / df.loc[d] - 1)).sum())
        periodes.append((d, -rendement))
    pertes = np.array([p for _, p in periodes])
    payees = np.array([indemnite(p, franchise, plafond) for p in pertes])
    sinistres = int((pertes > franchise).sum())
    sans_chevauchement = max(1, int((fin - df.index[0]).days // jours))
    tarifable = sinistres > 0
    frequence = sinistres / len(pertes)
    cout_moyen = float(payees[pertes > franchise].mean()) if tarifable else 0.0
    pure = frequence * cout_moyen
    payee = pure * (1 + MARGE) / (1 - FRAIS)

    # volatilité du panier, poids actuels, dernières séances
    recentes = df.iloc[-(SEANCES_VOLATILITE + 1):]
    valeur_panier = (recentes / recentes.iloc[0] * poids).sum(axis=1)
    par_an = len(df.loc[fin - pd.Timedelta(days=365):]) or 252
    volatilite = float(np.log(valeur_panier).diff().dropna().std() * math.sqrt(par_an))
    annees = jours / 365
    put_haut = put_black_scholes(1 - franchise, volatilite, annees)
    put_bas = put_black_scholes(1 - franchise - plafond, volatilite, annees)

    # la pire période réelle, rejouée
    i = int(pertes.argmax())
    debut_pire = periodes[i][0]
    chemin = df.loc[debut_pire: debut_pire + pd.Timedelta(days=jours)]
    trajet = (poids * (chemin / chemin.iloc[0] - 1)).sum(axis=1)
    sous = trajet[trajet <= -franchise]
    perte_pire = float(pertes[i])
    stop = float(-sous.iloc[0]) if len(sous) else perte_pire
    en_baisse = int(((chemin.iloc[-1] / chemin.iloc[0] - 1) < 0).sum())

    return {
        "capital": capital, "franchise": franchise, "plafond": plafond, "jours": jours,
        "periodes": len(pertes), "periodes_sans_chevauchement": sans_chevauchement,
        "premiere_date": df.index[0].date().isoformat(), "derniere_date": fin.date().isoformat(),
        "sinistres": sinistres, "tarifable": tarifable, "frequence": frequence,
        "cout_moyen": cout_moyen * capital if tarifable else None, "prime_pure": pure * capital if tarifable else None,
        "marge": pure * MARGE * capital if tarifable else None,
        "frais": (payee - pure * (1 + MARGE)) * capital if tarifable else None, "prime": payee * capital if tarifable else None,
        "volatilite": volatilite, "prix_bourse": (put_haut - put_bas) * capital,
        "pire": {
            "debut": debut_pire.date().isoformat(), "fin": chemin.index[-1].date().isoformat(), "perte": perte_pire * capital,
            "sans_protection": -perte_pire * capital,
            "avec_stop": (-stop * capital) if len(sous) else -perte_pire * capital, "stop_declenche": bool(len(sous)),
            "avec_assurance": ((-perte_pire + indemnite(perte_pire, franchise, plafond) - payee) * capital) if tarifable else None,
            "indemnite": indemnite(perte_pire, franchise, plafond) * capital,
            "positions": len(poids), "positions_en_baisse": en_baisse,
        },
    }
