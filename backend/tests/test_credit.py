"""Score Z d'Altman et probabilité de défaut (PD)."""
import math

import numpy as np
import pandas as pd
import pytest

from app.credit import pd_modele, routes, zscore
from app.credit.zscore import Comptes

SAINE = Comptes(520, 300, 1000, 380, 150, 900, 450, 1300)


# ------------------------------------------------------------------ Z d'Altman
def test_z_calcul_a_la_main():
    # X1=0,22 X2=0,38 X3=0,15 X4=2 X5=1,3  ->  1,2*0,22 + 1,4*0,38 + 3,3*0,15 + 0,6*2 + 1,0*1,3 = 3,791
    r = zscore.calculer(SAINE, "z")
    assert r["z"] == pytest.approx(3.791) and r["zone"] == "sain"
    assert [round(c["valeur"], 3) for c in r["contributions"]] == [0.22, 0.38, 0.15, 2.0, 1.3]
    assert sum(c["contribution"] for c in r["contributions"]) == pytest.approx(r["z"])


def test_z_seconde_version_sans_ventes():
    # Z'' = 6,56*0,22 + 3,26*0,38 + 6,72*0,15 + 1,05*2 = 1,4432 + 1,2388 + 1,008 + 2,1 = 5,79
    r = zscore.calculer(SAINE, "z2")
    assert r["z"] == pytest.approx(5.79) and len(r["contributions"]) == 4 and r["zone"] == "sain"


@pytest.mark.parametrize("z, zone", [(3.0, "sain"), (2.99, "grise"), (1.82, "grise"), (1.81, "grise"), (1.80, "detresse")])
def test_frontieres_des_zones(z, zone):
    m = zscore.MODELES["z"]
    assert ("sain" if z > m["sain"] else "detresse" if z < m["detresse"] else "grise") == zone


def test_les_trois_exemples_fictifs_couvrent_les_trois_zones():
    zones = [zscore.calculer(e["comptes"])["zone"] for e in zscore.EXEMPLES]
    assert zones == ["sain", "grise", "detresse"]


def test_z_refuse_les_bilans_impossibles():
    with pytest.raises(ValueError, match="actif"):
        zscore.calculer(Comptes(1, 1, 0, 0, 0, 1, 1, 1))
    with pytest.raises(ValueError, match="dettes"):
        zscore.calculer(Comptes(1, 1, 10, 0, 0, 1, 0, 1))
    with pytest.raises(ValueError, match="inconnu"):
        zscore.calculer(SAINE, "x")


# ------------------------------------------------------------------ PD
@pytest.fixture(scope="module")
def modele():
    pytest.importorskip("sklearn")
    return pd_modele.entrainer(pd_modele.echantillon_synthetique(8000), "synthetique")


def test_le_modele_apprend_la_loi_connue(modele):
    assert modele.metriques["auc_logistique"] > 0.70
    assert modele.metriques["brier"] < modele.metriques["brier_reference"]               # fait mieux que « tout le monde a le taux moyen »
    c = modele.coefs
    assert c["NumberOfTimes90DaysLate"] > 0 and c["age"] < 0 and c["RevolvingUtilizationOfUnsecuredLines"] > 0 and c["MonthlyIncome"] < 0
    calib = modele.metriques["calibration"]
    assert len(calib) == 10 and calib[-1]["pd_moyenne"] > calib[0]["pd_moyenne"] and calib[-1]["taux_observe"] > calib[0]["taux_observe"]


def test_contributions_exactes(modele):
    p = modele.predire({"age": 30, "NumberOfTimes90DaysLate": 2, "RevolvingUtilizationOfUnsecuredLines": 0.9})
    total = p["intercept"] + sum(c["contribution"] for c in p["contributions"])
    assert total == pytest.approx(p["logit"]) and p["pd"] == pytest.approx(1 / (1 + math.exp(-p["logit"])))
    assert abs(p["contributions"][0]["contribution"]) >= abs(p["contributions"][-1]["contribution"])        # triées par poids
    sage = modele.predire({"age": 70})["pd"]
    assert modele.predire({"age": 25})["pd"] > sage                                                         # plus jeune : plus risqué (loi connue)
    assert modele.predire({"NumberOfTimes90DaysLate": 4})["pd"] > modele.predire({"NumberOfTimes90DaysLate": 0})["pd"]


def test_valeurs_refusees(modele):
    with pytest.raises(ValueError, match="Variable inconnue"):
        modele.predire({"salaire": 1})
    with pytest.raises(ValueError, match="compris entre"):
        modele.predire({"age": 5})
    with pytest.raises(ValueError, match="compris entre"):
        modele.predire({"age": float("nan")})


def test_nettoyage_des_codes_speciaux_et_manquants():
    df = pd_modele.echantillon_synthetique(500)
    df.loc[0, "NumberOfTimes90DaysLate"] = 98
    df.loc[1, "MonthlyIncome"] = np.nan
    df.loc[2, "age"] = 400
    df.insert(0, "Unnamed: 0", range(len(df)))
    n = pd_modele.nettoyer(df)
    assert "Unnamed: 0" not in n.columns and n.loc[0, "NumberOfTimes90DaysLate"] == 20 and n["MonthlyIncome"].notna().all() and n.loc[2, "age"] == 100
    with pytest.raises(ValueError, match="Colonnes absentes"):
        pd_modele.nettoyer(df.drop(columns=["age"]))


def test_trop_peu_de_defauts():
    pytest.importorskip("sklearn")
    df = pd_modele.echantillon_synthetique(2000)
    df[pd_modele.CIBLE] = 0
    with pytest.raises(ValueError, match="Trop peu"):
        pd_modele.entrainer(df, "synthetique")


# ------------------------------------------------------------------ API
@pytest.fixture
def dossiers(tmp_path, monkeypatch):
    monkeypatch.setattr(routes.config, "DATA_DIR", tmp_path)
    return tmp_path


def test_api_zscore(client, utilisateur):
    u = utilisateur()
    ex = client.get("/api/v1/credit/zscore/exemples", headers=u.h).json()
    assert len(ex) == 3 and all(e["fictive"] for e in ex)
    r = client.post("/api/v1/credit/zscore", json={"modele": "z", **ex[0]["comptes"]}, headers=u.h)
    assert r.status_code == 200 and r.json()["zone"] == "sain"
    assert client.post("/api/v1/credit/zscore", json={"modele": "z", **{**ex[0]["comptes"], "total_actif": 0}}, headers=u.h).status_code == 422
    assert client.post("/api/v1/credit/zscore", json={"modele": "zz", **ex[0]["comptes"]}, headers=u.h).status_code == 422
    assert client.get("/api/v1/credit/zscore/exemples").status_code == 401


def test_api_pd_synthetique_signale_puis_kaggle(client, utilisateur, dossiers):
    pytest.importorskip("sklearn")
    u = utilisateur()
    d = client.get("/api/v1/credit/pd/modele", headers=u.h).json()
    assert d["source"] == "synthetique" and "INVENTÉS" in d["avertissement"] and len(d["variables"]) == 10 and (dossiers / "modeles" / "pd_credit.json").exists()
    r = client.post("/api/v1/credit/pd", json={"valeurs": {"age": 33, "NumberOfTimes90DaysLate": 1}}, headers=u.h)
    assert r.status_code == 200 and 0 < r.json()["pd"] < 1 and r.json()["source"] == "synthetique"
    assert client.post("/api/v1/credit/pd", json={"valeurs": {"age": 3}}, headers=u.h).status_code == 422

    # un fichier cs-training.csv présent : l'administrateur ré-entraîne dessus
    (dossiers / "externes").mkdir()
    brut = pd_modele.echantillon_synthetique(3000, graine=3)
    brut.insert(0, "Unnamed: 0", range(len(brut)))
    brut.to_csv(dossiers / "externes" / "cs-training.csv", index=False)
    assert client.post("/api/v1/admin/credit/pd/entrainer", headers=u.h).status_code == 403
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    r = client.post("/api/v1/admin/credit/pd/entrainer", headers=admin.h)
    assert r.status_code == 200 and r.json()["source"] == "kaggle"
    assert "Crédit aux particuliers" in client.get("/api/v1/credit/pd/modele", headers=u.h).json()["avertissement"]
