from datetime import date

import pandas as pd
import pytest

from app.marche.catalogue import Actif
from pipeline.nettoyer import nettoyer_dataframe

ACTION = Actif("AAA", "Action", "action", "Test", "semaine")
PETROLE = Actif("CL=F", "WTI", "matiere", "Énergie", "semaine", negatif_ok=True)
CRYPTO = Actif("CRY", "Crypto", "crypto", "Test", "continu")


def brut(lignes):
    df = pd.DataFrame(lignes, columns=["date", "Open", "High", "Low", "Close", "Volume"])
    return df.set_index("date")


def test_cas_normal_et_colonnes_en_casse_libre():
    b = brut([("2020-01-02", 10, 11, 9, 10.5, 100), ("2020-01-03", 10.5, 12, 10, 11, 120)])
    propre, rap = nettoyer_dataframe(b, ACTION, date(2020, 1, 1), date(2020, 12, 31))
    assert list(propre.columns) == ["open", "high", "low", "close", "volume", "corrige"]
    assert rap.lignes_propres == 2 and rap.barres_corrigees == 0 and not rap.avertissements


def test_doublons_vides_incompletes_et_hors_fenetre():
    b = brut([
        ("2019-12-31", 1, 2, 1, 1.5, 10),                        # hors fenêtre
        ("2020-01-02", 10, 11, 9, 10.5, 100),
        ("2020-01-02", 10, 11.5, 9, 10.8, 100),                  # doublon : on garde le dernier
        ("2020-01-03", None, None, None, None, None),            # vide
        ("2020-01-06", 10, 11, 9, None, 100),                    # incomplète
        ("2020-01-07", 10, 11, 9, 10, 100),
    ])
    propre, rap = nettoyer_dataframe(b, ACTION, date(2020, 1, 1), date(2020, 12, 31))
    assert rap.doublons_supprimes == 1
    assert rap.lignes_hors_fenetre == 1
    assert rap.lignes_vides_supprimees == 1
    assert rap.lignes_incompletes_supprimees == 1
    assert len(propre) == 2
    assert propre.loc["2020-01-02", "high"] == 11.5


def test_barre_incoherente_corrigee_et_comptee():
    b = brut([("2020-01-02", 10, 9.0, 9.5, 12, 100)])            # high < low et < close
    propre, rap = nettoyer_dataframe(b, ACTION, date(2020, 1, 1), date(2020, 12, 31))
    ligne = propre.iloc[0]
    assert ligne["high"] == 12 and ligne["low"] == 9.0 and bool(ligne["corrige"])
    assert rap.barres_corrigees == 1
    assert rap.correction_max_pct == pytest.approx(25.0)           # plus haut relevé de 9 à 12 : (12 - 9) / 12


def test_prix_negatif_supprime_sauf_pour_les_actifs_autorises():
    lignes = [("2020-04-17", 18.5, 19.0, 17.0, 18.27, 100), ("2020-04-20", 17.7, 18.0, -40.3, -37.63, 500)]
    propre_wti, rap_wti = nettoyer_dataframe(brut(lignes), PETROLE, date(2020, 1, 1), date(2020, 12, 31))
    assert len(propre_wti) == 2 and propre_wti["close"].min() == -37.63
    assert rap_wti.prix_negatifs_conserves == 1 and rap_wti.avertissements

    propre_act, rap_act = nettoyer_dataframe(brut(lignes), ACTION, date(2020, 1, 1), date(2020, 12, 31))
    assert len(propre_act) == 1
    assert rap_act.prix_non_positifs_supprimes == 1


def test_volume_manquant_mis_a_zero_et_compte():
    b = brut([("2020-01-02", 10, 11, 9, 10.5, None)])
    propre, rap = nettoyer_dataframe(b, ACTION, date(2020, 1, 1), date(2020, 12, 31))
    assert propre["volume"].iloc[0] == 0 and rap.volumes_manquants == 1


def test_trous_longs_et_mouvements_suspects_signales_mais_conserves():
    b = brut([
        ("2020-01-02", 10, 11, 9, 10, 1),
        ("2020-01-03", 10, 17, 10, 16, 1),                       # +60 %
        ("2020-02-10", 16, 17, 15, 16, 1),                       # trou de 38 jours
    ])
    propre, rap = nettoyer_dataframe(b, ACTION, date(2020, 1, 1), date(2020, 12, 31))
    assert len(propre) == 3                                      # rien n'est supprimé ni inventé
    assert rap.trous_longs == [{"de": "2020-01-03", "a": "2020-02-10", "jours": 38}]
    assert rap.mouvements_suspects[0]["date"] == "2020-01-03"
    assert rap.mouvements_suspects[0]["variation"] == pytest.approx(0.6)


def test_seuil_de_trou_depend_du_calendrier():
    b = brut([("2020-01-01", 1, 2, 1, 1, 1), ("2020-01-04", 1, 2, 1, 1, 1)])   # 3 jours d'écart
    _, action = nettoyer_dataframe(b, ACTION, date(2019, 1, 1), date(2020, 12, 31))
    _, crypto = nettoyer_dataframe(b, CRYPTO, date(2019, 1, 1), date(2020, 12, 31))
    assert action.trous_longs == [] and len(crypto.trous_longs) == 1


def test_index_avec_fuseau_horaire():
    idx = pd.DatetimeIndex(["2020-01-02 05:00:00+00:00"], name="date")
    df = pd.DataFrame({"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5], "volume": [1.0]}, index=idx)
    propre, _ = nettoyer_dataframe(df, ACTION, date(2020, 1, 1), date(2020, 12, 31))
    assert propre.index[0] == pd.Timestamp("2020-01-02")


def test_resultat_vide_avertit():
    propre, rap = nettoyer_dataframe(brut([("2021-05-05", 1, 2, 1, 1, 1)]), ACTION, date(2020, 1, 1), date(2020, 12, 31))
    assert len(propre) == 0 and rap.avertissements


def test_rapport_detaille_les_corrections_et_les_gros_mouvements(tmp_path):
    from pipeline.qualite import ecrire_rapports

    b = brut([("2020-01-02", 10, 9.0, 9.5, 12, 100), ("2020-01-03", 12, 31, 11, 30, 100)])      # +150 % la 2e séance
    _, rap = nettoyer_dataframe(b, ACTION, date(2020, 1, 1), date(2020, 12, 31))
    _, chemin_md = ecrire_rapports([rap], tmp_path)
    texte = chemin_md.read_text(encoding="utf-8")
    assert "## Bougies corrigées" in texte and "| AAA | 1 | 50.0 % | 25.00 % |" in texte
    assert "## Mouvements de plus de 50 % en une séance" in texte and "| AAA | 2020-01-03 | +150.0 % |" in texte


def test_commande_comparer_montre_brut_et_propre(tmp_path, monkeypatch, capsys):
    from app import config
    from pipeline import cli

    raw, clean = tmp_path / "raw", tmp_path / "clean"
    raw.mkdir(); clean.mkdir()
    (raw / "AAPL.csv").write_text("date,Open,High,Low,Close,Volume\n2020-01-02,10,9.0,9.5,12,100\n", encoding="utf-8")
    (clean / "AAPL.csv").write_text("date,open,high,low,close,volume,corrige\n2020-01-02,10,12,9,12,100,True\n", encoding="utf-8")
    monkeypatch.setattr(config, "RAW_DIR", raw); monkeypatch.setattr(config, "CLEAN_DIR", clean)
    assert cli.main(["comparer", "AAPL"]) == 0
    sortie = capsys.readouterr().out
    assert "1 bougie(s) corrigée(s)" in sortie and "brut" in sortie and "propre" in sortie
    assert cli.main(["comparer", "NOPE"]) == 1
