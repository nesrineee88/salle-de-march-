"""Historique des positions, reconstruit à partir des exécutions (aucune table supplémentaire). Fonction pure.

Une « position » est un cycle : elle s'ouvre au premier achat quand on ne détient rien, et se clôture quand la quantité
détenue revient à zéro. Une position clôturée ne disparaît donc jamais : elle reste dans cet historique.

Définitions (montants dans la devise de l'actif, USD dans ce simulateur) :
- prix d'achat moyen = Σ (quantité achetée × prix) / Σ quantité achetée ;
- prix de vente moyen = Σ (quantité vendue × prix) / Σ quantité vendue ;
- gain ou perte réalisé = Σ pnl des ventes, où pnl = (prix de vente − prix de revient moyen au moment de la vente) × quantité ;
- résultat net = réalisé − tous les frais du cycle (achats et ventes) ;
- rendement net = résultat net / coût total des achats (sans unité).
"""
from __future__ import annotations

EPS_RELATIF = 1e-9


def _nouveau(e: dict) -> dict:
    return {"symbole": e["symbole"], "ouverte_le": e["instant"], "cloturee_le": None, "quantite": 0.0, "quantite_max": 0.0,
            "qte_achetee": 0.0, "cout_achats": 0.0, "qte_vendue": 0.0, "produit_ventes": 0.0, "pnl": 0.0, "frais": 0.0,
            "nb_operations": 0, "motif_cloture": None}


def _motif(ordre_id: int, origines: dict[int, str | None], types_regles: dict[int, str]) -> str:
    """« manuelle » pour un ordre de l'utilisateur ; le type de la règle (stop_loss, take_profit...) sinon."""
    origine = origines.get(ordre_id)
    if not origine or not origine.startswith("regle:"):
        return "manuelle"
    try:
        return types_regles.get(int(origine.split(":", 1)[1]), "regle")
    except ValueError:
        return "regle"


def _en_sortie(c: dict) -> dict:
    return {
        "symbole": c["symbole"], "statut": "cloturee" if c["cloturee_le"] else "ouverte",
        "ouverte_le": c["ouverte_le"], "cloturee_le": c["cloturee_le"],
        "quantite_max": c["quantite_max"], "quantite_restante": 0.0 if c["cloturee_le"] else c["quantite"],
        "prix_achat_moyen": c["cout_achats"] / c["qte_achetee"] if c["qte_achetee"] else None,
        "prix_vente_moyen": c["produit_ventes"] / c["qte_vendue"] if c["qte_vendue"] else None,
        "pnl_realise": c["pnl"], "frais": c["frais"], "resultat_net": c["pnl"] - c["frais"],
        "rendement_net": (c["pnl"] - c["frais"]) / c["cout_achats"] if c["cout_achats"] > 0 else None,
        "motif_cloture": c["motif_cloture"], "nb_operations": c["nb_operations"],
    }


def historique_positions(executions: list[dict], origines: dict[int, str | None], types_regles: dict[int, str]) -> list[dict]:
    """`executions` dans l'ordre où elles ont eu lieu ; `origines` : ordre_id -> origine de l'ordre (« regle:7 » ou None) ;
    `types_regles` : regle_id -> type. Positions ouvertes d'abord (la plus récente en premier), puis les clôturées."""
    ouvertes: dict[str, dict] = {}
    toutes: list[dict] = []
    for e in executions:
        c = ouvertes.get(e["symbole"])
        q = e["quantite"]
        if e["sens"] == "achat":
            if c is None:
                c = ouvertes[e["symbole"]] = _nouveau(e)
                toutes.append(c)
            c["quantite"] += q
            c["qte_achetee"] += q
            c["cout_achats"] += q * e["prix"]
            c["quantite_max"] = max(c["quantite_max"], c["quantite"])
        else:
            if c is None:
                continue                                  # vente sans position : impossible sans vente à découvert, ignorée
            c["quantite"] -= q
            c["qte_vendue"] += q
            c["produit_ventes"] += q * e["prix"]
            c["pnl"] += e.get("pnl") or 0.0
        c["frais"] += e["frais"]
        c["nb_operations"] += 1
        if e["sens"] == "vente" and c["quantite"] <= EPS_RELATIF * max(1.0, c["quantite_max"]):
            c["cloturee_le"] = e["instant"]
            c["motif_cloture"] = _motif(e["ordre_id"], origines, types_regles)
            del ouvertes[e["symbole"]]
    ouvertes_tri = sorted((c for c in toutes if not c["cloturee_le"]), key=lambda c: c["ouverte_le"], reverse=True)
    cloturees_tri = sorted((c for c in toutes if c["cloturee_le"]), key=lambda c: c["cloturee_le"], reverse=True)
    return [_en_sortie(c) for c in ouvertes_tri + cloturees_tri]
