"""Ligne de commande du pipeline de données.

Depuis le dossier backend/ :
    python -m pipeline telecharger [--force] [--symboles AAPL BTC-USD]
    python -m pipeline verifier
    python -m pipeline nettoyer
    python -m pipeline comparer KC=F   (affiche, pour un actif, les bougies corrigées : brut contre propre)
    python -m pipeline demo       (données au hasard, pour voir l'interface sans réseau)
    python -m pipeline tout
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from app import config
from app.marche.catalogue import charger_univers

from .demo import generer_demo
from .nettoyer import fenetre_brute, nettoyer_dataframe
from .qualite import ecrire_rapports
from .telecharger import telecharger_univers, verifier_instantane


def cmd_telecharger(args) -> int:
    univers = charger_univers(config.UNIVERS_YAML)
    manifest = telecharger_univers(
        univers, config.RAW_DIR, force=args.force, symboles=args.symboles
    )
    print(f"{len(manifest['fichiers'])} fichiers dans l'instantané ({config.RAW_DIR}).")
    for symbole, erreur in manifest["erreurs"].items():
        print(f"  ERREUR {symbole} : {erreur}")
    return 1 if manifest["erreurs"] else 0


def cmd_verifier(_args) -> int:
    problemes = verifier_instantane(config.RAW_DIR)
    for p in problemes:
        print("  PROBLÈME :", p)
    print("Instantané identique au manifest." if not problemes else f"{len(problemes)} problème(s).")
    return 1 if problemes else 0


def cmd_nettoyer(_args) -> int:
    univers = charger_univers(config.UNIVERS_YAML)
    debut = fenetre_brute(univers.debut, univers.historique_prealable_jours)
    config.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    config.MARQUEUR_SYNTHETIQUE.unlink(missing_ok=True)      # les vraies données remplacent la démonstration
    rapports = []
    for actif in univers:
        source = config.RAW_DIR / actif.fichier
        if not source.exists():
            print(f"  absent : {actif.symbole} (lancer « telecharger »)")
            continue
        brut = pd.read_csv(source, index_col="date")
        propre, rapport = nettoyer_dataframe(brut, actif, debut, univers.fin)
        propre.to_csv(config.CLEAN_DIR / actif.fichier, index_label="date", float_format="%.10g")
        rapports.append(rapport)
    chemin_json, chemin_md = ecrire_rapports(rapports, config.CLEAN_DIR)
    print(f"{len(rapports)} actifs nettoyés. Rapport : {chemin_md}")
    return 0


def cmd_comparer(args) -> int:
    """Montre les premières bougies corrigées d'un actif : valeurs d'origine contre valeurs propres."""
    univers = charger_univers(config.UNIVERS_YAML)
    if args.symbole not in univers:
        print(f"Actif inconnu : {args.symbole}")
        return 1
    actif = univers.actifs[args.symbole]
    brut_chemin, propre_chemin = config.RAW_DIR / actif.fichier, config.CLEAN_DIR / actif.fichier
    if not brut_chemin.exists() or not propre_chemin.exists():
        print("Fichiers absents : lancer d'abord « python -m pipeline tout ».")
        return 1
    brut = pd.read_csv(brut_chemin, index_col="date")
    brut.columns = [c.strip().lower() for c in brut.columns]
    propre = pd.read_csv(propre_chemin, index_col="date")
    if "corrige" not in propre.columns or not propre["corrige"].astype(bool).any():
        print(f"{args.symbole} : aucune bougie corrigée.")
        return 0
    corrigees = propre[propre["corrige"].astype(bool)]
    print(f"{args.symbole} : {len(corrigees)} bougie(s) corrigée(s) sur {len(propre)}. Les {min(args.nombre, len(corrigees))} premières :")
    print(f"{'date':<12}{'':<8}{'open':>12}{'high':>12}{'low':>12}{'close':>12}")
    for date_, ligne in corrigees.head(args.nombre).iterrows():
        d = brut.loc[date_] if date_ in brut.index else None
        if d is not None:
            print(f"{date_:<12}{'brut':<8}{d['open']:>12.4f}{d['high']:>12.4f}{d['low']:>12.4f}{d['close']:>12.4f}")
        print(f"{'':<12}{'propre':<8}{ligne['open']:>12.4f}{ligne['high']:>12.4f}{ligne['low']:>12.4f}{ligne['close']:>12.4f}")
    return 0


def cmd_demo(_args) -> int:
    univers = charger_univers(config.UNIVERS_YAML)
    n = generer_demo(univers, config.CLEAN_DIR, config.MARQUEUR_SYNTHETIQUE)
    print(f"{n} séries de DÉMONSTRATION écrites dans {config.CLEAN_DIR} (ce ne sont pas des prix réels).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    sous = parser.add_subparsers(dest="commande", required=True)
    p = sous.add_parser("telecharger", help="télécharge et fige l'instantané")
    p.add_argument("--force", action="store_true", help="écrase les fichiers bruts existants")
    p.add_argument("--symboles", nargs="*", help="limiter à ces symboles")
    p.set_defaults(fonction=cmd_telecharger)
    sous.add_parser("verifier", help="compare l'instantané au manifest").set_defaults(fonction=cmd_verifier)
    sous.add_parser("nettoyer", help="brut -> propre + rapport").set_defaults(fonction=cmd_nettoyer)
    c = sous.add_parser("comparer", help="bougies corrigées d'un actif : brut contre propre")
    c.add_argument("symbole")
    c.add_argument("--nombre", type=int, default=8)
    c.set_defaults(fonction=cmd_comparer)
    sous.add_parser("demo", help="données générées au hasard pour voir l'interface sans réseau").set_defaults(fonction=cmd_demo)
    sous.add_parser("tout", help="télécharger, vérifier, nettoyer").set_defaults(fonction=None)
    args = parser.parse_args(argv)

    if args.commande == "tout":
        args.force, args.symboles = False, None
        for fonction in (cmd_telecharger, cmd_verifier, cmd_nettoyer):
            code = fonction(args)
            if code:
                return code
        return 0
    return args.fonction(args)


if __name__ == "__main__":
    sys.exit(main())
