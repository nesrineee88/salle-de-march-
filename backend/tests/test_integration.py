"""Chaîne complète sur données SYNTHÉTIQUES : univers réel -> brut -> propre -> rapport -> moteur."""
import json
import zlib
from datetime import datetime

import pandas as pd

from app import config
from app.marche.catalogue import charger_univers
from app.marche.moteur import MoteurMarche
from app.marche.stockage import Magasin
from pipeline.nettoyer import fenetre_brute, nettoyer_dataframe
from pipeline.qualite import ecrire_rapports
from pipeline.telecharger import normaliser_yfinance, telecharger_univers, verifier_instantane

from .conftest import serie_synthetique


def test_univers_reel_est_valide():
    u = charger_univers(config.UNIVERS_YAML)
    classes = [a.classe for a in u]
    assert classes.count("action") == 22 and classes.count("crypto") == 8
    assert classes.count("matiere") == 11 and classes.count("indice") == 2
    assert len({a.fichier for a in u}) == len(u.actifs)             # pas de collision de noms de fichiers
    assert u["CL=F"].negatif_ok and not u["BZ=F"].negatif_ok
    assert u["CL=F"].fichier == "CL_F.csv" and u["^GSPC"].fichier == "idx_GSPC.csv"
    assert not u["^VIX"].tradable and u["AAPL"].session_utc is not None and u["BTC-USD"].session_utc is None
    assert u.debut.year == 2018 and u.fin.year == 2026


def test_chaine_complete(tmp_path):
    u = charger_univers(config.UNIVERS_YAML)
    brut_dir, propre_dir = tmp_path / "raw", tmp_path / "clean"

    def faux_telechargeur(symbole, debut, fin):
        a = u[symbole]
        df = serie_synthetique(debut.isoformat(), 400, a.calendrier, 100.0, graine=zlib.crc32(symbole.encode()) % 1000)
        brut = df.drop(columns="corrige").rename(columns=str.title)
        return normaliser_yfinance(brut)

    manifest = telecharger_univers(u, brut_dir, faux_telechargeur)
    assert len(manifest["fichiers"]) == len(u.actifs) and verifier_instantane(brut_dir) == []

    debut = fenetre_brute(u.debut, u.historique_prealable_jours)
    rapports = []
    propre_dir.mkdir()
    for a in u:
        brut = pd.read_csv(brut_dir / a.fichier, index_col="date")
        propre, rap = nettoyer_dataframe(brut, a, debut, u.fin)
        propre.to_csv(propre_dir / a.fichier, index_label="date")
        rapports.append(rap)
    chemin_json, chemin_md = ecrire_rapports(rapports, propre_dir)
    assert len(json.loads(chemin_json.read_text())["actifs"]) == len(u.actifs)
    assert "| AAPL |" in chemin_md.read_text(encoding="utf-8")

    magasin = Magasin.charger(propre_dir, u)
    assert magasin.disponibles() == set(u.actifs)
    moteur = MoteurMarche(magasin, u)
    premiere = magasin.periode("AAPL")[0]
    c = moteur.cotation("AAPL", datetime(premiere.year, premiere.month, premiere.day, 17, 0))
    assert c.symbole == "AAPL"
