"""Tarification auto et Chain Ladder."""
import math

import numpy as np
import pandas as pd
import pytest

from app.actuariat import routes, tarification as tar


# ------------------------------------------------------------------ Chain Ladder à la main
TRI = [[100, 150, 160], [110, 168, None], [120, None, None]]


def test_chain_ladder_a_la_main():
    r = tar.chain_ladder(TRI)
    # f0 = (150+168)/(100+110) = 1,514286 ; f1 = 160/150 = 1,066667
    assert r["facteurs"][0] == pytest.approx(318 / 210) and r["facteurs"][1] == pytest.approx(160 / 150)
    a = {x["annee"]: x for x in r["annees"]}
    assert a[1]["provision"] == 0 and a[1]["ultime"] == 160
    assert a[2]["ultime"] == pytest.approx(168 * 160 / 150) and a[2]["provision"] == pytest.approx(168 * (160 / 150 - 1))
    assert a[3]["ultime"] == pytest.approx(120 * (318 / 210) * (160 / 150))
    assert r["provision_totale"] == pytest.approx(sum(x["provision"] for x in r["annees"])) and "Mack" in r["limites"]


@pytest.mark.parametrize("tri, texte", [
    ([[1, 2], [1, None]], "carré"),
    ([[100, 150, 160], [110, 168, 170], [120, None, None]], "inférieur"),
    ([[100, 150, 160], [110, None, None], [120, None, None]], "complet"),
    ([[100, 90, 160], [110, 168, None], [120, None, None]], "diminuer"),
    ([[0, 0, 0], [0, 0, None], [0, None, None]], "nulle"),
    ([[100, -5, 160], [110, 168, None], [120, None, None]], "positifs"),
])
def test_triangles_refuses(tri, texte):
    with pytest.raises(ValueError, match=texte):
        tar.chain_ladder(tri)


def test_le_triangle_synthetique_retrouve_la_cadence():
    r = tar.chain_ladder(tar.triangle_synthetique())
    assert len(r["facteurs"]) == 7 and r["facteurs"][0] > 1.4 and all(f >= 1.0 for f in r["facteurs"])
    assert r["annees"][0]["provision"] == 0 and r["annees"][-1]["provision"] > r["annees"][1]["provision"]       # la dernière année est la moins développée


# ------------------------------------------------------------------ tarification
@pytest.fixture(scope="module")
def modele():
    pytest.importorskip("sklearn")
    return tar.ModeleTarif.entrainer(tar.echantillon_synthetique(25000), "synthetique")


def test_le_modele_retrouve_les_effets_connus(modele):
    m = modele.metriques
    assert m["deviance_poisson"] < m["deviance_poisson_reference"] and m["deviance_gamma"] < m["deviance_gamma_reference"]
    assert modele.frequence["BonusMalus"] > 0 and modele.frequence["DrivAge"] < 0 and modele.frequence["LogDensity"] > 0 and modele.frequence["VehGas=Regular"] > 0
    assert 0.05 < m["frequence_moyenne"] < 0.30 and m["n_sinistres"] > 1000


def test_prime_a_la_main(modele):
    p = modele.prime({"DrivAge": 30, "BonusMalus": 120}, exposition=0.5, frais=0.2, marge=0.1)
    assert p["prime_pure"] == pytest.approx(p["frequence_annuelle"] * p["cout_moyen"] * 0.5)
    assert p["prime_commerciale"] == pytest.approx(p["prime_pure"] * 1.1 / 0.8)
    assert p["prime_commerciale"] == pytest.approx(p["prime_pure"] + p["marge_securite"] + p["frais"])           # prime = pure + marge + frais
    assert p["probabilite_sinistre"] == pytest.approx(1 - math.exp(-p["frequence_annuelle"] * 0.5)) and 0 < p["probabilite_sinistre"] < 1


def test_les_profils_risques_paient_plus(modele):
    jeune = modele.prime({"DrivAge": 20, "BonusMalus": 150})["prime_pure"]
    sage = modele.prime({"DrivAge": 60, "BonusMalus": 60})["prime_pure"]
    assert jeune > sage
    assert modele.prime({"Area": "F", "Density": 20000})["frequence_annuelle"] > modele.prime({"Area": "A", "Density": 20})["frequence_annuelle"]
    assert modele.prime({}, exposition=1)["probabilite_sinistre"] > modele.prime({}, exposition=0.1)["probabilite_sinistre"]
    f = modele.prime({})["facteurs_frequence"]
    assert abs(math.log(f[0]["facteur"])) >= abs(math.log(f[-1]["facteur"]))


@pytest.mark.parametrize("profil, exposition, frais, marge, texte", [
    ({"DrivAge": 5}, 1, 0.2, 0.05, "compris entre"), ({"Area": "Z"}, 1, 0.2, 0.05, "doit valoir"), ({"x": 1}, 1, 0.2, 0.05, "inconnue"),
    ({}, 0, 0.2, 0.05, "exposition"), ({}, 1, 0.95, 0.05, "frais"), ({"BonusMalus": float("nan")}, 1, 0.2, 0.05, "compris entre"),
])
def test_entrees_refusees(modele, profil, exposition, frais, marge, texte):
    with pytest.raises(ValueError, match=texte):
        modele.prime(profil, exposition, frais, marge)


def test_nettoyage_des_plafonds_et_jointure_des_montants():
    freq = pd.DataFrame({"IDpol": [1, 2], "ClaimNb": [9, 1], "Exposure": [3.0, 0.5], "VehPower": [12, 5], "VehAge": [40, 2], "DrivAge": [99, 30], "BonusMalus": [200, 60],
                         "VehGas": [" diesel", "REGULAR"], "Area": ["a", "F"], "Density": [0, 5000]})
    sev = pd.DataFrame({"IDpol": [2, 2], "ClaimAmount": [100.0, 50.0]})
    d = tar.nettoyer(freq, sev)
    assert d.loc[0, "ClaimNb"] == 4 and d.loc[0, "Exposure"] == 1.0 and d.loc[0, "VehPower"] == 9 and d.loc[0, "VehAge"] == 20 and d.loc[0, "DrivAge"] == 90 and d.loc[0, "BonusMalus"] == 150
    assert d.loc[0, "VehGas"] == "Diesel" and d.loc[1, "VehGas"] == "Regular" and d.loc[0, "Area"] == "A" and d.loc[0, "LogDensity"] == 0
    assert d.loc[0, "ClaimAmount"] == 0 and d.loc[1, "ClaimAmount"] == 150                  # montants additionnés par contrat
    with pytest.raises(ValueError, match="Colonnes absentes"):
        tar.nettoyer(freq.drop(columns=["Area"]))


def test_trop_peu_de_sinistres():
    pytest.importorskip("sklearn")
    d = tar.echantillon_synthetique(500)
    d["ClaimNb"] = 0
    with pytest.raises(ValueError, match="Trop peu"):
        tar.ModeleTarif.entrainer(d, "synthetique")


# ------------------------------------------------------------------ API
def test_api(client, utilisateur, tmp_path, monkeypatch):
    pytest.importorskip("sklearn")
    monkeypatch.setattr(routes.config, "DATA_DIR", tmp_path)
    u = utilisateur()
    d = client.get("/api/v1/actuariat/modele", headers=u.h).json()
    assert d["source"] == "synthetique" and "INVENTÉS" in d["avertissement"] and len(d["variables"]) == 7 and d["relativites_frequence"]
    r = client.post("/api/v1/actuariat/prime", json={"profil": {"DrivAge": 28}, "exposition": 1, "frais": 0.2, "marge": 0.05}, headers=u.h)
    assert r.status_code == 200 and r.json()["prime_commerciale"] > r.json()["prime_pure"] > 0
    assert client.post("/api/v1/actuariat/prime", json={"profil": {"DrivAge": 2}}, headers=u.h).status_code == 422
    assert client.post("/api/v1/actuariat/prime", json={"exposition": 5}, headers=u.h).status_code == 422
    ex = client.get("/api/v1/actuariat/provision/exemple", headers=u.h).json()
    assert ex["fictif"] and len(ex["triangle"]) == 8
    p = client.post("/api/v1/actuariat/provision", json={"triangle": ex["triangle"]}, headers=u.h)
    assert p.status_code == 200 and p.json()["provision_totale"] > 0
    assert client.post("/api/v1/actuariat/provision", json={"triangle": [[1]]}, headers=u.h).status_code == 422
    assert client.post("/api/v1/actuariat/admin/entrainer", headers=u.h).status_code == 403
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    freq = tar.echantillon_synthetique(4000, graine=2).drop(columns=["ClaimAmount", "LogDensity"])
    (tmp_path / "externes").mkdir()
    freq.to_csv(tmp_path / "externes" / "freMTPL2freq.csv", index=False)
    sev = tar.echantillon_synthetique(4000, graine=2)[["IDpol", "ClaimAmount"]]
    sev[sev["ClaimAmount"] > 0].to_csv(tmp_path / "externes" / "freMTPL2sev.csv", index=False)
    r = client.post("/api/v1/actuariat/admin/entrainer", headers=admin.h)
    assert r.status_code == 200 and r.json()["source"] == "kaggle"
    assert "freMTPL2" in client.get("/api/v1/actuariat/modele", headers=u.h).json()["avertissement"]
