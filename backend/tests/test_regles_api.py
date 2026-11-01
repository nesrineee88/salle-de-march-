"""API des règles automatiques et vérification du risque avant ordre."""
import pytest
from sqlalchemy import func, select

from app.main import Contexte, app, obtenir_contexte
from app.marche.moteur import MoteurMarche
from app.trading.persistance import OrdreDb, RegleDb


def aller(client, u, instant):
    assert client.post("/api/v1/horloge/aller-a", json={"instant": instant}, headers=u.h).status_code == 200


def ordre(client, u, quantite=10, sens="achat", symbole="TST"):
    r = client.post("/api/v1/ordres", json={"symbole": symbole, "sens": sens, "quantite": quantite, "type": "marche"}, headers=u.h)
    assert r.status_code == 201 and r.json()["statut"] == "execute", r.text
    return r.json()


def regle(client, u, type="stop_loss", seuil_pct=30, part_pct=100, symbole="TST"):
    return client.put("/api/v1/regles", json={"symbole": symbole, "type": type, "seuil_pct": seuil_pct, "part_pct": part_pct}, headers=u.h)


def test_pose_liste_et_suppression(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-20T17:00:00")
    assert regle(client, u).status_code == 422 and "aucune position" in regle(client, u).json()["detail"]
    ordre(client, u)
    r = regle(client, u, "stop_loss", 30)
    assert r.status_code == 200
    corps = r.json()
    assert corps["type"] == "stop_loss" and corps["seuil"] == pytest.approx(-0.30) and corps["part"] == 1.0 and corps["statut"] == "active"

    regle(client, u, "take_profit", 50, 50)
    liste = client.get("/api/v1/regles", headers=u.h).json()
    assert [x["type"] for x in liste] == ["take_profit", "stop_loss"]                    # la plus récente d'abord
    sl = next(x for x in liste if x["type"] == "stop_loss")
    pos = client.get("/api/v1/portefeuille", headers=u.h).json()["positions"][0]
    assert sl["niveau"] == pytest.approx(pos["prix_moyen"] * 0.70) and sl["prix_moyen"] == pytest.approx(pos["prix_moyen"])

    assert client.delete(f"/api/v1/regles/{sl['id']}", headers=u.h).json()["statut"] == "annulee"
    assert client.delete(f"/api/v1/regles/{sl['id']}", headers=u.h).status_code == 409
    assert client.delete("/api/v1/regles/999", headers=u.h).status_code == 404


def test_pose_exige_connexion_et_valide_le_corps(client, utilisateur):
    assert client.put("/api/v1/regles", json={"symbole": "TST", "type": "stop_loss", "seuil_pct": 30}).status_code == 401
    assert client.get("/api/v1/regles").status_code == 401
    u = utilisateur()
    for corps in [{"symbole": "TST", "type": "inconnu", "seuil_pct": 30}, {"symbole": "TST", "type": "stop_loss", "seuil_pct": 0},
                  {"symbole": "TST", "type": "stop_loss", "seuil_pct": -5}, {"symbole": "TST", "type": "take_profit", "seuil_pct": 20, "part_pct": 150}]:
        assert client.put("/api/v1/regles", json=corps, headers=u.h).status_code == 422


def test_une_regle_se_declenche_avec_l_horloge_et_laisse_une_trace_d_origine(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-20T17:00:00")
    ordre(client, u, 20)
    r = regle(client, u, "stop_suiveur", 0.5).json()                      # recul de 0,5 % : se déclenche vite sur ces prix
    aller(client, u, "2020-03-31T17:00:00")
    apres = next(x for x in client.get("/api/v1/regles", headers=u.h).json() if x["id"] == r["id"])
    assert apres["statut"] == "declenchee" and apres["declenchee_le"] and "vendu" in apres["motif"]
    ordres = client.get("/api/v1/ordres", headers=u.h).json()
    auto = [o for o in ordres if o["origine"]]
    assert [o["origine"] for o in auto] == [f"regle:{r['id']}"] and auto[0]["sens"] == "vente" and auto[0]["statut"] == "execute"
    assert client.get("/api/v1/portefeuille", headers=u.h).json()["positions"] == []
    assert any(e["ordre_id"] == auto[0]["id"] and e["sens"] == "vente" for e in client.get("/api/v1/executions", headers=u.h).json())


def test_les_regles_survivent_a_un_redemarrage_et_a_la_remise_a_zero(client, utilisateur, base_test, univers_test, magasin_test):
    from fastapi.testclient import TestClient

    u = utilisateur()
    aller(client, u, "2020-03-20T17:00:00")
    ordre(client, u)
    regle(client, u, "stop_loss", 30)
    regle(client, u, "take_profit", 50, 50)
    avant = client.get("/api/v1/regles", headers=u.h).json()
    with base_test.session() as s:
        assert s.scalar(select(func.count()).select_from(RegleDb).where(RegleDb.utilisateur_id == u.id)) == 2

    neuf = Contexte(univers_test, magasin_test, MoteurMarche(magasin_test, univers_test), base=base_test)
    app.dependency_overrides[obtenir_contexte] = lambda: neuf
    c2 = TestClient(app)
    assert c2.get("/api/v1/regles", headers=u.h).json() == avant
    suivante = c2.put("/api/v1/regles", json={"symbole": "TST", "type": "stop_suiveur", "seuil_pct": 10}, headers=u.h).json()
    assert suivante["id"] == max(x["id"] for x in avant) + 1                                   # la numérotation continue

    assert c2.post("/api/v1/bac/reinitialiser", headers=u.h).status_code in (200, 204)
    assert c2.get("/api/v1/regles", headers=u.h).json() == []
    with base_test.session() as s:
        assert s.scalar(select(func.count()).select_from(RegleDb).where(RegleDb.utilisateur_id == u.id)) == 0
        assert s.scalar(select(func.count()).select_from(OrdreDb).where(OrdreDb.utilisateur_id == u.id)) == 0


def test_verification_avant_achat(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-20T17:00:00")
    prix = client.get("/api/v1/cotations/TST", headers=u.h).json()["prix"]
    petit = client.get("/api/v1/verification-ordre?symbole=TST&quantite=5", headers=u.h).json()
    codes = {a["code"] for a in petit["alertes"]}
    assert "profil_absent" in codes and "protection" in codes and "concentration" not in codes
    assert petit["apres"]["poids"] == pytest.approx(5 * prix / 100_000, rel=1e-3)

    gros = client.get(f"/api/v1/verification-ordre?symbole=TST&quantite={int(60_000 / prix)}", headers=u.h).json()
    assert gros["alertes"][0]["niveau"] == "attention" and gros["alertes"][0]["code"] == "concentration"
    assert gros["apres"]["poids"] > 0.5

    client.post("/api/v1/moi/profil-risque", json={"reponses": {f"q{i}": 1 for i in range(1, 7)}}, headers=u.h)   # profil prudent
    prudent = client.get(f"/api/v1/verification-ordre?symbole=TST&quantite={int(20_000 / prix)}", headers=u.h).json()
    codes = {a["code"] for a in prudent["alertes"]}
    assert {"concentration", "tolerance"} <= codes and "profil_absent" not in codes


def test_verification_prend_en_compte_le_stop_loss_pose_et_la_vente_totale(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-20T17:00:00")
    ordre(client, u, 10)
    regle(client, u, "stop_loss", 10)
    v = client.get("/api/v1/verification-ordre?symbole=TST&quantite=5", headers=u.h).json()
    assert "protection" not in {a["code"] for a in v["alertes"]}
    assert any("−10 %" in a["texte"] for a in v["alertes"] if a["code"] in ("profil_absent", "tolerance"))
    vente = client.get("/api/v1/verification-ordre?symbole=TST&sens=vente&quantite=10", headers=u.h).json()
    assert [a["code"] for a in vente["alertes"]] == ["regles_annulees"]
    assert client.get("/api/v1/verification-ordre?symbole=TST&sens=vente&quantite=3", headers=u.h).json()["alertes"] == []


def test_verification_erreurs(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-20T17:00:00")
    assert client.get("/api/v1/verification-ordre?symbole=TST&quantite=5").status_code == 401
    assert client.get("/api/v1/verification-ordre?symbole=NOPE&quantite=5", headers=u.h).status_code == 404
    assert client.get("/api/v1/verification-ordre?symbole=VIDE&quantite=5", headers=u.h).status_code == 503
    assert client.get("/api/v1/verification-ordre?symbole=TST&quantite=0", headers=u.h).status_code == 422
