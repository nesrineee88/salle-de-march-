"""Routes du test de résistance des banques (conventionnelles et islamiques) aux chocs sur les matières premières."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..contexte import Contexte, obtenir_contexte
from ..utilisateurs.modeles import Utilisateur
from ..utilisateurs.routes import exiger
from . import credit, donnees_reelles, historique, ia, modele, scenarios

routeur = APIRouter(prefix="/api/v1/stress")


# ------------------------------------------------------------------ banques RÉELLES (rapports Pilier 3), stress de crédit
LIMITES = [
    "En Arabie saoudite, les banques conventionnelles sont mixtes : elles ont aussi des guichets islamiques. À la fin de 2025, 83 % des "
    "financements de SNB et 62 % de ceux de Riyad Bank étaient conformes à la charia (S&P, repris par Arab News).",
    "Le taux de prêts en défaut est un stock. Il sert d'approximation de la probabilité de défaut (PD) à un an.",
    "La LGD (45 % de base, jusqu'à 75 % selon le scénario) et la corrélation « entreprises » de Bâle sont appliquées à tous les prêts "
    "de toutes les banques.",
    "Les intensités modérée et sévère, les hausses de défauts et les paliers de LGD sont des hypothèses de l'équipe. Seul le quantile "
    "99,9 % vient de Bâle.",
    "Seules les nouvelles pertes sont comptées : les prêts déjà en défaut sont supposés couverts par les provisions existantes.",
    "Même formule pour les deux types de banque : les mécanismes propres à la finance islamique ne sont pas appliqués aux vraies banques.",
    "Actifs pondérés constants, horizon d'un an, pas d'effet de second tour. Ni les provisions existantes ni les bénéfices futurs ne compensent la perte.",
    "Le périmètre de la ligne « Loans » du tableau CR1 peut varier d'une banque à l'autre.",
    "Le repère de 7 % n'inclut pas les coussins propres à chaque banque. Ce n'est pas un test réglementaire, ni une prédiction de faillite.",
    "4 banques islamiques contre 5 conventionnelles : aucune conclusion du type « un modèle bancaire est meilleur ».",
    "Chaque chiffre reste « À relire » tant qu'une personne de l'équipe ne l'a pas comparé au PDF.",
]
SOURCES_LIMITES = {"mixtes": "https://www.arabnews.pk/node/2651723/business-economy", "bale": "https://www.bis.org/bcbs/irbriskweight.pdf"}


def _banques_reelles() -> list:
    try:
        return donnees_reelles.charger()
    except FileNotFoundError:
        raise HTTPException(503, "Le fichier des banques réelles est absent : data/externes/banques_reelles.csv.") from None
    except donnees_reelles.ErreurDonneesBanques as exc:
        raise HTTPException(503, str(exc)) from None


CHAMPS_PUBLICS = ("cle", "nom", "type", "pays", "date_arrete", "devise", "source_url", "page_km1", "page_cr1", "date_collecte", "statut")


@routeur.get("/reelles/banques")
def reelles_banques(_u: Utilisateur = Depends(exiger("marche.lire"))):
    """Ce qu'il faut pour CHOISIR : nom, type et source de chaque banque. Les chiffres bruts restent côté serveur."""
    bs = _banques_reelles()
    return {"banques": [{c: getattr(b, c) for c in CHAMPS_PUBLICS} for b in bs], "resume": donnees_reelles.resume(bs),
            "scenarios": list(credit.SCENARIOS), "catalogue": scenarios.catalogue(), "lgd_defaut": credit.LGD_DEFAUT, "lgd_min": credit.LGD_MIN, "lgd_max": credit.LGD_MAX,
            "seuil_minimum": credit.SEUIL_MINIMUM, "seuil_coussin": credit.SEUIL_COUSSIN,
            "limites": LIMITES, "sources_limites": SOURCES_LIMITES, "commande_collecte": "python -m pipeline.banques"}


class CorpsReel(BaseModel):
    type: str | None = None                     # nouveau : type de crise (recession, defauts, actifs, combine)…
    intensite: str = "severe"                   # … et intensité (moderee, severe, extreme)
    scenario: str | None = None                 # ancien : central, adverse, severe, extreme (récession seule)
    lgd: float | None = None                    # LGD imposée (réglage avancé) ; absente = celle du scénario
    banques: list[str] | None = None            # clés choisies ; absent = toutes


@routeur.post("/reelles/comparer")
def reelles_comparer(corps: CorpsReel, _u: Utilisateur = Depends(exiger("marche.lire"))):
    """Simulation : le scénario appliqué aux banques choisies (une seule, ou plusieurs pour comparer)."""
    try:
        if corps.type is not None:
            p = scenarios.parametres(corps.type, corps.intensite, corps.lgd)
        else:
            ancien, lgd = corps.scenario or "adverse", credit.LGD_DEFAUT if corps.lgd is None else corps.lgd
            credit.valider(ancien, lgd)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    bs = _banques_reelles()
    if corps.banques is not None:
        connues = {b.cle for b in bs}
        inconnues = sorted(set(corps.banques) - connues)
        if inconnues:
            raise HTTPException(422, f"Banque inconnue : {', '.join(inconnues)}.")
        if not corps.banques:
            raise HTTPException(422, "Choisissez au moins une banque.")
        bs = [b for b in bs if b.cle in set(corps.banques)]
    return credit.comparer_scenario(bs, p) if corps.type is not None else credit.comparer(bs, ancien, lgd)


@routeur.get("/reelles/matrice")
def reelles_matrice(lgd: float = credit.LGD_DEFAUT, _u: Utilisateur = Depends(exiger("marche.lire"))):
    try:
        credit.valider("central", lgd)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return credit.matrice(_banques_reelles(), lgd)


@routeur.get("/banques")
def banques(_u: Utilisateur = Depends(exiger("marche.lire"))):
    return {"banques": [b.en_dict() for b in modele.panel_synthetique()], "groupes": [{"cle": g, "libelle": modele.LIBELLE_GROUPES[g]} for g in modele.GROUPES],
            "seuil_minimum": modele.SEUIL_MINIMUM, "seuil_coussin": modele.SEUIL_COUSSIN,
            "avertissement": "Banques INVENTÉES (synthétiques), aux profils plausibles : ce ne sont pas de vraies banques. Paramètres pédagogiques à valider avec l'encadrant."}


@routeur.get("/chocs-historiques")
def chocs_hist(ctx: Contexte = Depends(obtenir_contexte), _u: Utilisateur = Depends(exiger("marche.lire"))):
    return {"fenetres": historique.chocs_historiques(ctx.magasin), "symboles": historique.SYMBOLES,
            "note": "Chocs mesurés sur les prix d'origine du simulateur (hors crises injectées)."}


class CorpsStress(BaseModel):
    banque: dict = Field(default_factory=dict)
    chocs: dict = Field(default_factory=dict)


def _preparer(corps: CorpsStress):
    try:
        return modele.valider_banque(corps.banque), modele.valider_chocs(corps.chocs)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from None


@routeur.post("/simuler")
def simuler(corps: CorpsStress, _u: Utilisateur = Depends(exiger("marche.lire"))):
    b, chocs = _preparer(corps)
    return modele.stresser(b, chocs)


@routeur.post("/comparer")
def comparer(corps: CorpsStress, _u: Utilisateur = Depends(exiger("marche.lire"))):
    """Même choc appliqué à toutes les banques du panel synthétique, classées de la plus touchée à la moins touchée."""
    _b, chocs = _preparer(CorpsStress(banque={}, chocs=corps.chocs))
    lignes = []
    for b in modele.panel_synthetique():
        r = modele.stresser(b, chocs)
        lignes.append({k: r[k] for k in ("banque", "type", "ratio_avant", "ratio_apres", "variation_points", "statut")})
    lignes.sort(key=lambda x: x["variation_points"])
    par_type = {}
    for t in ("conventionnelle", "islamique"):
        v = [x["variation_points"] for x in lignes if x["type"] == t]
        par_type[t] = {"nb": len(v), "variation_moyenne": sum(v) / len(v), "pire": min(v)}
    return {"banques": lignes, "par_type": par_type, "chocs": chocs}


@routeur.post("/inverse")
def inverse(corps: CorpsStress, _u: Utilisateur = Depends(exiger("marche.lire"))):
    b, _ = _preparer(CorpsStress(banque=corps.banque, chocs={}))
    return {"minimum": modele.choc_inverse(b, modele.SEUIL_MINIMUM), "coussin": modele.choc_inverse(b, modele.SEUIL_COUSSIN)}


@routeur.post("/ia/comparaison")
def ia_comparaison(_u: Utilisateur = Depends(exiger("ia.utiliser"))):
    try:
        r = ia.entrainer()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None
    return {k: v for k, v in r.items() if not k.startswith("_")} | {
        "avertissement": "Les modèles apprennent à reproduire le modèle structurel sur des banques et des chocs tirés au hasard (données inventées) : ils ne remplacent pas le modèle structurel, qui reste la référence."}


class CorpsExplication(CorpsStress):
    modele: str = "boost"


@routeur.post("/ia/explication")
def ia_explication(corps: CorpsExplication, _u: Utilisateur = Depends(exiger("ia.utiliser"))):
    b, chocs = _preparer(corps)
    try:
        return ia.expliquer(b, chocs, corps.modele)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
