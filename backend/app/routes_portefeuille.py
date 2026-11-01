"""Routes du portefeuille : analyse du risque, courbe de valeur, trades clôturés, export des données."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends

from .contexte import Contexte, acces_bac, obtenir_contexte
from .risque.analyse import analyser
from .trading.salle import ordre_en_dict
from .utilisateurs.modeles import Utilisateur
from .utilisateurs.routes import exiger, publique, utilisateur_courant

routeur = APIRouter(prefix="/api/v1")
BENCHMARK = "^GSPC"
FENETRE_RISQUE_JOURS = 260


@routeur.get("/portefeuille/analyse")
def analyse(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    with acces_bac(ctx, u) as (bac, t):
        valo = bac.salle.valorisation(bac.compte_id, t)
        series = {p["symbole"]: ctx.magasin.barres_terminees(p["symbole"], t.date(), n=FENETRE_RISQUE_JOURS)["close"]
                  for p in valo["positions"] if ctx.magasin.a_des_donnees(p["symbole"])}
        catalogue = {a.symbole: (a.classe, a.secteur) for a in ctx.univers}
        return analyser(valo, ctx.historique_visible(bac, t), series, catalogue, u.profil_risque)


@routeur.get("/portefeuille/historique")
def historique_valeur(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    """Courbe de valeur du portefeuille, avec le S&P 500 ramené au même capital de départ pour comparer."""
    with acces_bac(ctx, u) as (bac, t):
        points = ctx.historique_visible(bac, t)
        capital = bac.salle.compte(bac.compte_id).capital_initial
        base = None
        sortie = []
        for p in points:
            jour = date.fromisoformat(p["jour"])
            ref = None
            if ctx.magasin.a_des_donnees(BENCHMARK):
                ref = ctx.magasin.derniere_cloture_avant(BENCHMARK, jour + timedelta(days=1))   # clôture de ce jour ou la dernière connue
            if base is None and ref:
                base = ref
            sortie.append({"jour": p["jour"], "equity": p["equity"], "cash": p["cash"],
                           "benchmark": capital * ref / base if (ref and base) else None})
        return {"points": sortie, "benchmark": BENCHMARK, "capital_initial": capital}


@routeur.get("/portefeuille/trades")
def trades_clotures(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(exiger("trading.passer_ordre"))):
    """Les ventes (trades clôturés), la plus récente en premier, avec le gain ou la perte réalisé."""
    with acces_bac(ctx, u) as (bac, _t):
        ventes = [e for e in bac.salle.compte(bac.compte_id).executions if e.sens == "vente"]
    sortie = []
    for e in reversed(ventes[-200:]):
        pnl = e.pnl or 0.0
        prix_achat = e.prix - pnl / e.quantite if e.quantite else None
        sortie.append({"instant": e.instant.isoformat(timespec="seconds"), "symbole": e.symbole, "quantite": e.quantite,
                       "prix_achat_moyen": prix_achat, "prix_vente": e.prix, "pnl": pnl, "frais": e.frais,
                       "rendement": (e.prix / prix_achat - 1) if prix_achat else None})
    return sortie


@routeur.get("/moi/export")
def exporter_mes_donnees(ctx: Contexte = Depends(obtenir_contexte), u: Utilisateur = Depends(utilisateur_courant)):
    """Toutes les données de l'utilisateur (profil, ordres, exécutions, courbe de valeur), à télécharger."""
    bac = ctx.bac(u.id)
    with bac.verrou:
        etat = bac.salle.exporter(bac.compte_id)
        historique = list(bac.historique)
        instant = bac.horloge.maintenant().isoformat(timespec="seconds")
    return {"utilisateur": publique(u), "bac_a_sable": {**etat, "instant_simule": instant}, "historique_valeur": historique}
