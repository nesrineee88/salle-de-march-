"""Routes des règles automatiques (stop-loss en %, prise de profit, stop suiveur, achat complémentaire)
et de la vérification du risque avant un achat."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .analyse.indicateurs import atr
from .contexte import Contexte, acces_bac, donnees_ou_erreur, obtenir_contexte
from .marche.stockage import DonneeIndisponible
from .risque.avant_ordre import verifier_achat
from .trading.carnet import FRAIS_BPS
from .trading.modeles import STOP_LOSS, STOP_SUIVEUR
from .trading.salle import regle_en_dict
from .utilisateurs.modeles import Utilisateur
from .utilisateurs.routes import exiger

routeur = APIRouter(prefix="/api/v1")


class CorpsRegle(BaseModel):
    symbole: str = Field(max_length=20)
    type: Literal["stop_loss", "take_profit", "stop_suiveur", "achat_complementaire"]
    seuil_pct: float = Field(gt=0, le=1000, description="Toujours positif : 30 signifie « 30 % » ; le sens vient du type.")
    part_pct: float = Field(100.0, gt=0, le=100, description="Part de la position concernée (vente ou achat complémentaire).")


def _niveau(regle: dict, pos: dict | None) -> float | None:
    """Prix auquel la règle se déclenche, si on peut le calculer."""
    if regle["statut"] != "active":
        return None
    if regle["type"] == STOP_SUIVEUR:
        return regle["plus_haut"] * (1 - regle["seuil"]) if regle["plus_haut"] else None
    return pos["prix_moyen"] * (1 + regle["seuil"]) if pos else None


@routeur.get("/regles")
def lister_regles(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    """Toutes les règles de l'utilisateur, les plus récentes d'abord, avec le prix de déclenchement des règles actives."""
    with acces_bac(ctx, u) as (bac, t):
        compte = bac.salle.compte(bac.compte_id)
        positions = {p["symbole"]: p for p in bac.salle.valorisation(bac.compte_id, t)["positions"]}
        sortie = []
        for r in sorted(compte.regles.values(), key=lambda r: -r.id):
            d = regle_en_dict(r)
            d["niveau"] = _niveau(d, positions.get(r.symbole))
            d["prix_moyen"] = positions[r.symbole]["prix_moyen"] if r.symbole in positions else None
            sortie.append(d)
        return sortie


@routeur.put("/regles")
def poser_regle(corps: CorpsRegle, ctx: Contexte = Depends(obtenir_contexte),
                u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    """Pose une règle sur une position, ou remplace la règle active du même type sur cet actif."""
    seuil = corps.seuil_pct / 100.0
    with acces_bac(ctx, u) as (bac, t):
        try:
            regle = bac.salle.poser_regle(bac.compte_id, corps.symbole, corps.type,
                                          -seuil if corps.type == STOP_LOSS else seuil, corps.part_pct / 100.0, t)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return regle_en_dict(regle)


@routeur.delete("/regles/{regle_id}")
def supprimer_regle(regle_id: int, ctx: Contexte = Depends(obtenir_contexte),
                    u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    with acces_bac(ctx, u) as (bac, _t):
        try:
            return regle_en_dict(bac.salle.annuler_regle(bac.compte_id, regle_id))
        except KeyError as exc:
            raise HTTPException(404, str(exc).strip("'\"")) from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None


@routeur.get("/verification-ordre")
def verification_ordre(symbole: str, sens: Literal["achat", "vente"] = "achat", quantite: float = Query(..., gt=0),
                       ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    """Alertes de risque avant un ordre (jamais bloquantes). Pour un achat : concentration, perte possible comparée à la
    tolérance du profil, liquidités restantes, volatilité de l'actif, absence de protection."""
    donnees_ou_erreur(ctx, symbole)
    with acces_bac(ctx, u) as (bac, t):
        try:
            cot = ctx.moteur.cotation(symbole, t)
            lues = ctx.moteur.historique(symbole, t, 60)
        except DonneeIndisponible as exc:
            raise HTTPException(409, str(exc)) from None
        valo = bac.salle.valorisation(bac.compte_id, t)
        compte = bac.salle.compte(bac.compte_id)
        position = next((p for p in valo["positions"] if p["symbole"] == symbole), None)
        regles = [r for r in compte.regles.values() if r.active and r.symbole == symbole]
        equity = valo["equity"] or 1.0

        if sens == "vente":
            alertes = []
            if position and quantite >= position["quantite"] - 1e-9 and regles:
                alertes.append({"code": "regles_annulees", "niveau": "info", "texte": (
                    f"Vendre toute la position annulera les {len(regles)} règle(s) automatique(s) posée(s) sur {symbole}.")})
            return {"alertes": alertes, "apres": None}

        frais = FRAIS_BPS[ctx.univers[symbole].classe] / 1e4
        montant = quantite * cot.prix * (1 + frais)
        valeur_apres = (position["valeur"] if position else 0.0) + quantite * cot.prix
        poids_apres = valeur_apres / equity
        part_cash_apres = (valo["cash"] - montant) / equity
        atr_pct = None
        if len(lues) >= 15 and cot.prix:
            serie = atr([b["high"] for b in lues], [b["low"] for b in lues], [b["close"] for b in lues], 14)
            dernier = serie[-1]
            atr_pct = float(dernier) / abs(cot.prix) if dernier == dernier else None          # NaN : historique trop court
        stop = next((r for r in regles if r.type == STOP_LOSS), None)
        alertes = verifier_achat(
            symbole=symbole, poids_apres=poids_apres, part_cash_apres=part_cash_apres, atr_pct=atr_pct,
            profil=u.profil_risque, baisse_stop=-stop.seuil if stop else None,
            a_une_protection=any(r.type in (STOP_LOSS, STOP_SUIVEUR) for r in regles))
        return {"alertes": alertes, "apres": {"poids": poids_apres, "part_liquidites": part_cash_apres, "montant": montant}}
