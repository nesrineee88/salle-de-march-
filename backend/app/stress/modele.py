"""Test de résistance d'une banque aux chocs sur les matières premières : banque conventionnelle contre banque islamique.

Modèle STRUCTUREL et transparent (chaque perte vient d'un canal nommé), volontairement simple. Tous les paramètres sont pédagogiques :
à valider avec l'encadrant avant toute présentation (décisions D9 et D11).

Chocs : variation de prix (−0,30 = −30 %) pour quatre groupes de matières premières (énergie, métaux précieux, métaux industriels, agricole).
Mécanismes communs :
 - Crédit aux producteurs : la probabilité de défaut (PD) de départ est multipliée par exp(4 × baisse du prix du groupe), bornée entre 0,7 et 8 et plafonnée à 60 % ;
   la perte en cas de défaut (LGD) augmente de moitié de la baisse (plafond 90 %). Perte = encours × (LGD stressée × PD stressée − LGD × PD de départ).
 - Position de marché sur matières premières (supposée acheteuse) : perte = montant × choc (gain si le prix monte).
Banque conventionnelle : prêts aux secteurs des matières premières + position de marché.
Banque islamique :
 - Mourabaha (vente à coût majoré) : la part détenue en stock subit la baisse de prix ; le reste est une créance soumise au risque de crédit.
 - Salam (achat à terme payé d'avance, supposé sur des produits agricoles) : perte de prix sur la part non couverte par un salam parallèle + risque de non-livraison du producteur.
 - Istisna (financement de fabrication) : le risque est la défaillance du fabricant, qui augmente quand ses matières premières (énergie, métaux industriels) renchérissent
   et que le coût n'est pas répercuté.
 - Exposition directe (stock d'or ou de métaux, par exemple) : valorisée au prix.
 - Risque commercial déplacé (DCR) : les déposants en comptes d'investissement (PSIA) supportent contractuellement une partie des pertes, mais la banque en absorbe la part `lissage`
   pour éviter les retraits : perte supportée par la banque = pertes × [(1 − p) + p × lissage], p étant la part du portefeuille financée par les PSIA.
Ratio après choc = (fonds propres de départ − pertes supportées) / actifs pondérés, SANS compter les bénéfices à venir : c'est la lecture prudente de « l'impact immédiat ».
Un second ratio ajoute le résultat avant provisions d'une année (`ratio_avec_resultat`) : il peut dépasser le ratio de départ si les pertes sont modestes.
Les actifs pondérés des risques sont supposés constants (limite).
Seuils : CET1 minimal de Bâle III 4,5 %, coussin de conservation inclus 7 %."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, fields

GROUPES = ("energie", "metaux_precieux", "metaux_industriels", "agricole")
LIBELLE_GROUPES = {"energie": "Énergie", "metaux_precieux": "Métaux précieux", "metaux_industriels": "Métaux industriels", "agricole": "Agricole"}
SEUIL_MINIMUM = 0.045
SEUIL_COUSSIN = 0.07
BETA_PD = 4.0
PLAFOND_PD = 0.60


@dataclass
class Banque:
    nom: str = "Banque"
    type: str = "conventionnelle"                     # conventionnelle | islamique
    synthetique: bool = True
    actifs: float = 100.0                             # milliards
    densite_rwa: float = 0.60                         # actifs pondérés / actifs
    cet1: float = 0.12                                # ratio CET1 de départ
    rentabilite: float = 0.012                        # résultat avant provisions / actifs, par an
    horizon: float = 1.0                              # années
    pd_base: float = 0.03
    lgd: float = 0.45
    # parts des actifs exposées à chaque groupe de matières premières (prêts ou financements aux producteurs)
    part_groupes: dict = field(default_factory=lambda: {"energie": 0.06, "metaux_precieux": 0.01, "metaux_industriels": 0.03, "agricole": 0.03})
    part_trading: float = 0.01                        # position de marché ou exposition directe (part des actifs)
    # banque islamique
    part_murabaha: float = 0.0
    part_stock_murabaha: float = 0.3
    part_salam: float = 0.0
    couverture_salam: float = 0.5
    part_istisna: float = 0.0
    repercussion_istisna: float = 0.5
    part_psia: float = 0.0                            # part du portefeuille financée par les comptes d'investissement
    lissage: float = 0.3                              # part des pertes des PSIA que la banque absorbe (DCR)

    def en_dict(self) -> dict:
        return asdict(self)


CHAMPS_BANQUE = {f.name for f in fields(Banque)}


def valider_banque(d: dict) -> Banque:
    inconnus = set(d) - CHAMPS_BANQUE
    if inconnus:
        raise ValueError(f"Paramètre inconnu : {', '.join(sorted(inconnus))}")
    b = Banque(**{**Banque().en_dict(), **d})
    if b.type not in ("conventionnelle", "islamique"):
        raise ValueError("Le type doit être « conventionnelle » ou « islamique ».")

    def borne(nom, v, lo, hi):
        if not (isinstance(v, (int, float)) and math.isfinite(v) and lo <= v <= hi):
            raise ValueError(f"« {nom} » doit être compris entre {lo} et {hi}.")
    borne("actifs", b.actifs, 0.1, 100_000); borne("densité des actifs pondérés", b.densite_rwa, 0.1, 1.5)
    borne("CET1 de départ", b.cet1, 0.01, 0.40); borne("rentabilité", b.rentabilite, -0.05, 0.10); borne("horizon", b.horizon, 0.25, 5)
    borne("PD de départ", b.pd_base, 0.0001, 0.5); borne("LGD", b.lgd, 0.05, 1.0)
    for g in GROUPES:
        borne(f"part {LIBELLE_GROUPES[g]}", b.part_groupes.get(g, 0.0), 0.0, 1.0)
    for nom in ("part_trading", "part_murabaha", "part_stock_murabaha", "part_salam", "couverture_salam", "part_istisna", "repercussion_istisna", "part_psia", "lissage"):
        borne(nom, getattr(b, nom), 0.0, 1.0)
    if sum(b.part_groupes.get(g, 0.0) for g in GROUPES) + b.part_trading + b.part_murabaha + b.part_salam + b.part_istisna > 1.0 + 1e-9:
        raise ValueError("La somme des expositions aux matières premières dépasse 100 % des actifs.")
    if b.type == "conventionnelle" and (b.part_murabaha or b.part_salam or b.part_istisna or b.part_psia):
        raise ValueError("Une banque conventionnelle n'a ni mourabaha, ni salam, ni istisna, ni comptes d'investissement.")
    return b


def valider_chocs(chocs: dict) -> dict:
    inconnus = set(chocs) - set(GROUPES)
    if inconnus:
        raise ValueError(f"Groupe inconnu : {', '.join(sorted(inconnus))}")
    sortie = {}
    for g in GROUPES:
        v = chocs.get(g, 0.0)
        if not (isinstance(v, (int, float)) and math.isfinite(v) and -0.95 <= v <= 3.0):
            raise ValueError(f"Le choc « {LIBELLE_GROUPES[g]} » doit être compris entre −95 % et +300 %.")
        sortie[g] = float(v)
    return sortie


def _pd_stressee(pd_base: float, choc: float) -> float:
    m = min(8.0, max(0.7, math.exp(BETA_PD * -choc)))
    return min(PLAFOND_PD, pd_base * m)


def _lgd_stressee(lgd: float, choc: float) -> float:
    return min(0.9, lgd * (1 + 0.5 * max(0.0, -choc)))


def perte_credit(encours: float, b: Banque, choc: float) -> float:
    return encours * (_lgd_stressee(b.lgd, choc) * _pd_stressee(b.pd_base, choc) - b.lgd * b.pd_base)


def stresser(b: Banque, chocs: dict) -> dict:
    """Ventile la perte par canal et calcule le CET1 après choc."""
    A = b.actifs
    moyen = sum(chocs[g] * b.part_groupes.get(g, 0.0) for g in GROUPES) / max(1e-12, sum(b.part_groupes.get(g, 0.0) for g in GROUPES) or 1)
    canaux: list[dict] = []

    def ajouter(cle, libelle, perte, explication):
        canaux.append({"cle": cle, "libelle": libelle, "perte": perte, "explication": explication})

    # crédit aux producteurs (les deux types de banque ; pour la banque islamique ce sont des financements par participation ou autres)
    for g in GROUPES:
        e = A * b.part_groupes.get(g, 0.0)
        if e > 0:
            ajouter(f"credit_{g}", f"Crédit : {LIBELLE_GROUPES[g]}", perte_credit(e, b, chocs[g]),
                    f"Encours {e:.2f} Md, PD {b.pd_base:.1%} → {_pd_stressee(b.pd_base, chocs[g]):.1%}")
    if b.part_trading > 0:
        # position directe : pondérée par les expositions de crédit aux groupes (à défaut, moyenne simple des quatre chocs)
        poids = [b.part_groupes.get(g, 0.0) for g in GROUPES]
        choc_pos = sum(c * p for c, p in zip((chocs[g] for g in GROUPES), poids)) / sum(poids) if sum(poids) > 0 else sum(chocs[g] for g in GROUPES) / 4
        ajouter("position", "Position de marché sur matières premières" if b.type == "conventionnelle" else "Exposition directe (stocks)",
                -A * b.part_trading * choc_pos, f"Montant {A * b.part_trading:.2f} Md, choc moyen pondéré {choc_pos:+.1%}")

    if b.type == "islamique":
        choc_moy = sum(chocs.values()) / 4
        m = A * b.part_murabaha
        if m > 0:
            stock = m * b.part_stock_murabaha * max(0.0, -choc_moy)
            creance = perte_credit(m * (1 - b.part_stock_murabaha), b, min(0.0, choc_moy))
            ajouter("murabaha_stock", "Mourabaha : baisse de valeur du stock détenu", stock, f"{b.part_stock_murabaha:.0%} de {m:.2f} Md encore en stock, choc {choc_moy:+.1%}")
            ajouter("murabaha_creance", "Mourabaha : défaut du client acheteur", creance, f"Créance {m * (1 - b.part_stock_murabaha):.2f} Md")
        s = A * b.part_salam
        if s > 0:
            prix = s * (1 - b.couverture_salam) * max(0.0, -chocs["agricole"])
            livraison = perte_credit(s, b, chocs["agricole"])
            ajouter("salam_prix", "Salam : baisse du prix de la marchandise non couverte", prix, f"{1 - b.couverture_salam:.0%} non couvert par un salam parallèle de {s:.2f} Md")
            ajouter("salam_livraison", "Salam : non-livraison du producteur", livraison, "Le producteur, payé d'avance, ne livre pas")
        i = A * b.part_istisna
        if i > 0:
            entree = max(0.0, chocs["energie"], chocs["metaux_industriels"])
            pd_f = min(PLAFOND_PD, b.pd_base * min(8.0, math.exp(2.0 * (1 - b.repercussion_istisna) * entree)))
            ajouter("istisna", "Istisna : défaillance du fabricant (coût des matières en hausse)", i * b.lgd * (pd_f - b.pd_base),
                    f"Encours {i:.2f} Md, hausse des intrants {entree:+.1%}, répercussion {b.repercussion_istisna:.0%}")

    brut = sum(c["perte"] for c in canaux)
    p = b.part_psia if b.type == "islamique" else 0.0
    supportee = brut * ((1 - p) + p * b.lissage) if brut > 0 else brut          # les gains ne sont pas partagés dans ce modèle prudent
    if b.type == "islamique" and p > 0 and brut > 0:
        ajouter("partage_psia", "Pertes supportées par les déposants en comptes d'investissement", supportee - brut,
                f"{p:.0%} du portefeuille est financé par des PSIA ; la banque en absorbe {b.lissage:.0%} (risque commercial déplacé)")

    rwa = A * b.densite_rwa
    k0 = b.cet1 * rwa
    resultat = A * b.rentabilite * b.horizon
    k1 = k0 - supportee
    ratio1 = k1 / rwa
    ratio_resultat = (k1 + resultat) / rwa
    statut = "sous_minimum" if ratio1 < SEUIL_MINIMUM else "sous_coussin" if ratio1 < SEUIL_COUSSIN else "ok"
    return {"banque": b.nom, "type": b.type, "ratio_avant": b.cet1, "ratio_apres": ratio1, "ratio_avec_resultat": ratio_resultat, "variation_points": (ratio1 - b.cet1) * 100,
            "perte_brute": brut, "perte_supportee": supportee, "resultat_periode": resultat, "fonds_propres_avant": k0, "fonds_propres_apres": k1,
            "rwa": rwa, "statut": statut, "seuil_minimum": SEUIL_MINIMUM, "seuil_coussin": SEUIL_COUSSIN, "canaux": canaux, "choc_credit_moyen": moyen}


def choc_inverse(b: Banque, seuil: float = SEUIL_MINIMUM) -> dict:
    """Test de résistance inversé : le choc uniforme sur les quatre groupes (par pas de 1 %) qui fait passer le CET1 sous `seuil`."""
    def ratio(c):
        return stresser(b, {g: c for g in GROUPES})["ratio_apres"]
    if ratio(0.0) < seuil:
        return {"choc": 0.0, "message": "La banque est déjà sous le seuil sans aucun choc.", "seuil": seuil}
    lo, hi = -0.95, 0.0
    if ratio(lo) >= seuil:
        return {"choc": None, "message": "La banque reste au-dessus du seuil même avec une baisse de 95 % de toutes les matières premières.", "seuil": seuil}
    for _ in range(60):
        mid = (lo + hi) / 2
        if ratio(mid) < seuil:
            lo = mid
        else:
            hi = mid
    return {"choc": round(hi, 4), "message": f"Une baisse uniforme de {abs(hi):.1%} des quatre groupes fait passer le CET1 sous {seuil:.1%}.", "seuil": seuil}


def panel_synthetique() -> list[Banque]:
    """Douze banques INVENTÉES (6 conventionnelles, 6 islamiques) aux profils plausibles et variés. Ce ne sont pas de vraies banques."""
    conv = [("A", 0.14, 0.04, 0.15, 0.55, 0.020), ("B", 0.12, 0.02, 0.08, 0.60, 0.015), ("C", 0.11, 0.01, 0.05, 0.65, 0.010),
            ("D", 0.13, 0.08, 0.20, 0.50, 0.018), ("E", 0.10, 0.03, 0.10, 0.70, 0.008), ("F", 0.15, 0.00, 0.03, 0.45, 0.012)]
    isl = [("A", 0.13, 0.04, 0.30, 0.20, 0.10, 0.40), ("B", 0.11, 0.02, 0.35, 0.30, 0.05, 0.50), ("C", 0.12, 0.05, 0.25, 0.10, 0.20, 0.30),
           ("D", 0.10, 0.03, 0.40, 0.25, 0.15, 0.55), ("E", 0.15, 0.01, 0.20, 0.35, 0.00, 0.25), ("F", 0.115, 0.06, 0.28, 0.15, 0.12, 0.45)]
    sortie: list[Banque] = []
    for i, (n, cet1, trading, e, dens, renta) in enumerate(conv):
        sortie.append(Banque(nom=f"Banque conventionnelle {n} (synthétique)", type="conventionnelle", actifs=50 + 25 * i, densite_rwa=dens, cet1=cet1, rentabilite=renta,
                             part_trading=trading,
                             part_groupes={"energie": e * 0.5, "metaux_precieux": e * 0.1, "metaux_industriels": e * 0.2, "agricole": e * 0.2}))
    for i, (n, cet1, direct, murabaha, dens, salam, psia) in enumerate(isl):
        sortie.append(Banque(nom=f"Banque islamique {n} (synthétique)", type="islamique", actifs=30 + 20 * i, densite_rwa=0.55 + 0.03 * i, cet1=cet1, rentabilite=0.014,
                             part_trading=direct * 0.5, part_murabaha=murabaha * 0.5, part_stock_murabaha=0.2 + 0.05 * i, part_salam=salam * 0.2, couverture_salam=0.3 + 0.1 * (i % 4),
                             part_istisna=0.05 + 0.01 * i, repercussion_istisna=0.3 + 0.1 * (i % 5), part_psia=psia, lissage=0.2 + 0.05 * i,
                             part_groupes={"energie": 0.03, "metaux_precieux": 0.01, "metaux_industriels": 0.02, "agricole": 0.02 + 0.01 * (i % 3)}))
    return sortie
