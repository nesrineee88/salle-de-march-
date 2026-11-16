"""Supports, résistances, cassures, lignes de tendance et retracements de Fibonacci. Fonctions pures sur des bougies.

Aucun regard sur le futur : un sommet (ou un creux) à l'indice i n'est CONFIRMÉ qu'après k bougies de plus, puisqu'il faut
voir les k bougies suivantes pour savoir qu'il était le plus haut (ou le plus bas) de sa fenêtre. Les k dernières bougies
ne peuvent donc pas encore porter de sommet confirmé.
Tous ces niveaux sont des repères descriptifs : une cassure est un signal POSSIBLE, jamais une certitude ni un conseil.
"""
from __future__ import annotations

K_PIVOT = 3
MAX_NIVEAUX = 6
RATIOS_FIBONACCI = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)


def pivots(bougies: list[dict], k: int = K_PIVOT) -> tuple[list[int], list[int]]:
    """Indices des sommets (plus haut de la fenêtre [i−k, i+k]) et des creux (plus bas), confirmés seulement."""
    hauts = [b["high"] for b in bougies]
    bas = [b["low"] for b in bougies]
    sommets, creux = [], []
    for i in range(k, len(bougies) - k):
        if hauts[i] >= max(hauts[i - k:i + k + 1]) and hauts[i] > max(hauts[i - k:i]):
            sommets.append(i)
        if bas[i] <= min(bas[i - k:i + k + 1]) and bas[i] < min(bas[i - k:i]):
            creux.append(i)
    return sommets, creux


def _regrouper(points: list[tuple[float, int]], tolerance: float) -> list[list[tuple[float, int]]]:
    """Regroupe des (prix, indice) triés par prix quand ils sont à moins de `tolerance` de la moyenne du groupe."""
    groupes: list[list[tuple[float, int]]] = []
    for p in sorted(points):
        if groupes and abs(p[0] - sum(x[0] for x in groupes[-1]) / len(groupes[-1])) <= tolerance:
            groupes[-1].append(p)
        else:
            groupes.append([p])
    return groupes


def supports_resistances(bougies: list[dict], k: int = K_PIVOT, min_touches: int = 2) -> list[dict]:
    """Zones où le prix s'est retourné au moins `min_touches` fois. niveau = moyenne des sommets et creux regroupés ;
    tolérance de regroupement = la moitié de l'amplitude moyenne d'une bougie (plus haut − plus bas).
    Type : « support » si le niveau est sous la dernière clôture, « résistance » sinon."""
    if len(bougies) < 2 * k + 2:
        return []
    sommets, creux = pivots(bougies, k)
    points = [(bougies[i]["high"], i) for i in sommets] + [(bougies[i]["low"], i) for i in creux]
    amplitude = sum(b["high"] - b["low"] for b in bougies) / len(bougies)
    tolerance = max(amplitude * 0.5, 1e-12)
    dernier = bougies[-1]["close"]
    niveaux = []
    for g in _regrouper(points, tolerance):
        if len(g) < min_touches:
            continue
        niveau = sum(x[0] for x in g) / len(g)
        indices = sorted(x[1] for x in g)
        niveaux.append({"niveau": niveau, "type": "support" if niveau < dernier else "resistance", "touches": len(g),
                        "premier_t": bougies[indices[0]]["t"], "dernier_t": bougies[indices[-1]]["t"], "dernier_indice": indices[-1]})
    niveaux.sort(key=lambda n: (-n["touches"], -n["dernier_indice"]))
    return niveaux[:MAX_NIVEAUX]


def cassures(bougies: list[dict], niveaux: list[dict], k: int = K_PIVOT) -> list[dict]:
    """Dernière clôture qui traverse chaque niveau APRÈS sa confirmation (dernier contact + k bougies).
    variation_depuis = (dernière clôture − clôture de cassure) / |clôture de cassure| : ce que le cours a fait ensuite."""
    sortie = []
    clotures = [b["close"] for b in bougies]
    for n in niveaux:
        debut = n["dernier_indice"] + k + 1
        for j in range(len(bougies) - 1, max(debut, 1) - 1, -1):
            avant, apres = clotures[j - 1], clotures[j]
            sens = "haussiere" if avant <= n["niveau"] < apres else "baissiere" if avant >= n["niveau"] > apres else None
            if sens:
                sortie.append({"niveau": n["niveau"], "sens": sens, "t": bougies[j]["t"], "prix": apres,
                               "bougies_depuis": len(bougies) - 1 - j,
                               "variation_depuis": (clotures[-1] - apres) / abs(apres) if apres else None})
                break
    return sorted(sortie, key=lambda c: -c["t"])


def lignes_tendance(bougies: list[dict], k: int = K_PIVOT) -> list[dict]:
    """Tendance haussière : droite par les deux derniers creux confirmés s'ils montent ;
    tendance baissière : droite par les deux derniers sommets confirmés s'ils descendent. Prolongée jusqu'à la dernière bougie."""
    sommets, creux = pivots(bougies, k)
    sortie = []
    for indices, cle, sens, condition in ((creux, "low", "haussiere", lambda a, b: b > a), (sommets, "high", "baissiere", lambda a, b: b < a)):
        if len(indices) < 2:
            continue
        i, j = indices[-2], indices[-1]
        a, b = bougies[i][cle], bougies[j][cle]
        if not condition(a, b):
            continue
        pente = (b - a) / (j - i)                                    # par bougie
        fin = len(bougies) - 1
        sortie.append({"sens": sens, "t1": bougies[i]["t"], "p1": a, "t2": bougies[fin]["t"], "p2": a + pente * (fin - i)})
    return sortie


def fibonacci(bougies: list[dict]) -> dict | None:
    """Retracements entre le plus haut et le plus bas de la période affichée.
    Si le plus bas précède le plus haut (mouvement haussier) : niveau(r) = haut − r × (haut − bas) ;
    sinon (mouvement baissier) : niveau(r) = bas + r × (haut − bas). r ∈ {0 ; 23,6 % ; 38,2 % ; 50 % ; 61,8 % ; 78,6 % ; 100 %}."""
    if len(bougies) < 2:
        return None
    i_haut = max(range(len(bougies)), key=lambda i: bougies[i]["high"])
    i_bas = min(range(len(bougies)), key=lambda i: bougies[i]["low"])
    haut, bas = bougies[i_haut]["high"], bougies[i_bas]["low"]
    if haut <= bas:
        return None
    hausse = i_bas < i_haut
    niveaux = [{"ratio": r, "prix": haut - r * (haut - bas) if hausse else bas + r * (haut - bas)} for r in RATIOS_FIBONACCI]
    return {"sens": "haussier" if hausse else "baissier", "haut": haut, "bas": bas,
            "t_haut": bougies[i_haut]["t"], "t_bas": bougies[i_bas]["t"], "niveaux": niveaux}
