from datetime import datetime

import pytest
from sqlalchemy import select

from app.main import Contexte, app, obtenir_contexte
from app.marche.moteur import MoteurMarche
from app.trading import persistance


def aller(client, u, instant):
    r = client.post("/api/v1/horloge/aller-a", json={"instant": instant}, headers=u.h)
    assert r.status_code == 200, r.text


def acheter(client, u, q=10, symbole="TST", sens="achat"):
    return client.post("/api/v1/ordres", json={"symbole": symbole, "sens": sens, "quantite": q, "type": "marche"}, headers=u.h).json()


def test_analyse_sans_position(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-02-10T17:00:00")
    a = client.get("/api/v1/portefeuille/analyse", headers=u.h).json()
    assert a["diversification"] is None and a["concentration"] is None and a["risque"] is None
    assert any("Aucune position" in m for m in a["avertissements"])
    assert a["repartition"]["marche"] == [{"libelle": "Liquidités", "part": pytest.approx(1.0)}]
    assert a["profil"] == {"statut": "profil_absent"}


def test_analyse_avec_position_repartition_et_profil(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-20T17:00:00")
    assert acheter(client, u, 200)["statut"] == "execute"
    client.post("/api/v1/moi/profil-risque", json={"reponses": {f"q{i}": 2 for i in range(1, 7)}}, headers=u.h)
    a = client.get("/api/v1/portefeuille/analyse", headers=u.h).json()

    for cle in ("marche", "secteur", "position"):
        assert sum(x["part"] for x in a["repartition"][cle]) == pytest.approx(1.0)         # liquidités comprises
    assert {x["libelle"] for x in a["repartition"]["position"]} == {"TST", "Liquidités"}
    assert a["concentration"]["hhi"] == pytest.approx(1.0) and a["diversification"] == {"score": 0, "nb_positions": 1, "nb_marches": 1}
    assert a["risque"]["jours"] >= 30 and a["risque"]["cvar"] >= a["risque"]["var"] >= 0
    assert a["risque"]["var_montant"] == pytest.approx(a["risque"]["var"] * client.get("/api/v1/portefeuille", headers=u.h).json()["equity"])
    assert a["profil"]["statut"] in ("ok", "proche", "depasse") and a["profil"]["perte_tolerance"] == pytest.approx(0.10)
    assert a["correlations"] is None                                                         # une seule position


def test_courbe_de_valeur_un_point_par_jour_simule_et_persistee(client, utilisateur, base_test):
    u = utilisateur()
    aller(client, u, "2020-02-03T17:00:00")
    acheter(client, u, 5)
    for jour in ("2020-02-04", "2020-02-05", "2020-02-06"):
        aller(client, u, f"{jour}T17:00:00")
    h = client.get("/api/v1/portefeuille/historique", headers=u.h).json()
    jours = [p["jour"] for p in h["points"]]
    assert jours == sorted(set(jours)) and jours[0] == "2020-01-01" and jours[-1] == "2020-02-06"   # 1er point : le départ
    assert {"2020-02-03", "2020-02-04", "2020-02-05"} <= set(jours)
    assert h["points"][0]["equity"] == pytest.approx(100_000)
    apres_achat = next(p for p in h["points"] if p["jour"] == "2020-02-03")
    assert apres_achat["equity"] == pytest.approx(100_000, abs=50)                          # juste après l'achat : frais et spread seulement
    assert h["benchmark"] == "^GSPC" and h["points"][0]["benchmark"] is None               # pas de S&P 500 dans les données de test
    with base_test.session() as s:
        assert [p["jour"] for p in persistance.lire_historique(s, u.id)] == jours


def test_la_courbe_survit_a_un_redemarrage_et_masque_le_futur_apres_un_retour_arriere(client, utilisateur, base_test, univers_test, magasin_test):
    from fastapi.testclient import TestClient

    u = utilisateur()
    for jour in ("2020-02-03", "2020-02-10", "2020-02-17"):
        aller(client, u, f"{jour}T17:00:00")
    avant = client.get("/api/v1/portefeuille/historique", headers=u.h).json()["points"]
    neuf = Contexte(univers_test, magasin_test, MoteurMarche(magasin_test, univers_test), base=base_test)
    app.dependency_overrides[obtenir_contexte] = lambda: neuf
    c2 = TestClient(app)
    assert c2.get("/api/v1/portefeuille/historique", headers=u.h).json()["points"] == avant
    aller(c2, u, "2020-02-11T17:00:00")                                                      # retour en arrière
    visibles = [p["jour"] for p in c2.get("/api/v1/portefeuille/historique", headers=u.h).json()["points"]]
    assert "2020-02-17" not in visibles and "2020-02-03" in visibles


def test_trades_clotures_avec_gain_realise(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-02-10T17:00:00")
    acheter(client, u, 10)
    assert client.get("/api/v1/portefeuille/trades", headers=u.h).json() == []              # un achat n'est pas un trade clôturé
    acheter(client, u, 4, sens="vente")
    acheter(client, u, 6, sens="vente")
    trades = client.get("/api/v1/portefeuille/trades", headers=u.h).json()
    assert [t["quantite"] for t in trades] == [6, 4]                                         # plus récent d'abord
    for t in trades:
        assert t["pnl"] == pytest.approx((t["prix_vente"] - t["prix_achat_moyen"]) * t["quantite"]) and t["frais"] > 0
    total = client.get("/api/v1/portefeuille", headers=u.h).json()["pnl_realise"]
    assert total == pytest.approx(sum(t["pnl"] for t in trades))


def test_fin_de_simulation_arrete_le_temps(client, utilisateur):
    import time

    u = utilisateur()
    aller(client, u, "2020-12-31T23:59:00")
    client.post("/api/v1/horloge/facteur", json={"facteur": 1_000_000}, headers=u.h)
    client.post("/api/v1/horloge/reprendre", headers=u.h)
    time.sleep(0.3)
    i = client.get("/api/v1/marche/instantane", headers=u.h).json()
    assert i["termine"] is True and i["horloge"]["en_pause"] is True and i["instant"] == "2020-12-31T23:59:59"
    assert client.get("/api/v1/marche/instantane", headers=u.h).json()["instant"] == "2020-12-31T23:59:59"


def test_variation_marche_ferme_compare_a_la_seance_d_avant(client, utilisateur, magasin_test):
    u = utilisateur()
    aller(client, u, "2020-01-18T12:00:00")                                                 # un samedi
    c = {x["symbole"]: x for x in client.get("/api/v1/marche/instantane", headers=u.h).json()["cotations"]}["TST"]
    assert c["statut"] == "ferme"
    serie = magasin_test._series["TST"]
    veille = serie.loc[:"2020-01-17"]["close"]
    assert c["prix"] == pytest.approx(veille.iloc[-1]) and c["reference"] == pytest.approx(veille.iloc[-2])
    assert c["reference"] != c["prix"]                                                      # la variation n'est plus toujours 0 %


def test_export_des_donnees(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-02-10T17:00:00")
    acheter(client, u, 3)
    e = client.get("/api/v1/moi/export", headers=u.h).json()
    assert e["utilisateur"]["email"] == "alice@example.com" and "mot_de_passe_hash" not in str(e)
    assert e["bac_a_sable"]["positions"][0]["quantite"] == 3 and len(e["bac_a_sable"]["executions"]) == 1
    assert e["bac_a_sable"]["instant_simule"].startswith("2020-02-10") and len(e["historique_valeur"]) >= 1
    assert client.get("/api/v1/moi/export").status_code == 401
