"""Statistiques globales et performances pour l'administrateur."""
import pytest


def test_reserve_a_l_administrateur(client, utilisateur):
    u = utilisateur()
    assert client.get("/api/v1/admin/statistiques", headers=u.h).status_code == 403
    assert client.get("/api/v1/admin/performances", headers=u.h).status_code == 403
    assert client.get("/api/v1/admin/statistiques").status_code == 401


def test_statistiques(client, utilisateur, tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    client.post("/api/v1/horloge/aller-a", json={"instant": "2020-02-03T17:00:00"}, headers=bob.h)
    client.post("/api/v1/ordres", json={"symbole": "TST", "sens": "achat", "quantite": 10, "type": "marche"}, headers=bob.h)
    client.post("/api/v1/formation/lecons/ordres/repondre", json={"reponses": [0, 0, 0]}, headers=bob.h)
    client.post("/api/v1/admin/scenarios", json={"nom": "Test", "date_debut": "2020-02-10", "portee_type": "tous", "choc_pct": -10}, headers=admin.h)
    s = client.get("/api/v1/admin/statistiques", headers=admin.h).json()
    assert s["utilisateurs"]["total"] == 2 and s["utilisateurs"]["par_role"] == {"admin": 1, "apprenant": 1} and s["utilisateurs"]["nouveaux_7_jours"] == 2
    assert s["trading"]["executions"] == 1 and s["trading"]["ordres_par_statut"] == {"execute": 1} and s["trading"]["frais_totaux"] > 0
    assert s["trading"]["actifs_les_plus_echanges"] == [{"symbole": "TST", "executions": 1}] and s["trading"]["comptes_avec_historique"] == 1
    assert len(s["formation"]) == 8 and next(f for f in s["formation"] if f["id"] == "ordres")["reussites"] in (0, 1)
    assert s["crises"]["scenarios"] == 1 and s["crises"]["scenarios_actifs"] == 1
    assert s["donnees"]["actifs_charges"] == 2 and s["donnees"]["actifs_total"] == 4
    assert [m["present"] for m in s["modeles"]] == [False, False]
    assert s["parametres"]["frais_points_de_base"]["action"] == 5.0 and "Lecture seule" in s["parametres"]["note"]


def test_modeles_enregistres_apparaissent_apres_entrainement(client, utilisateur, tmp_path, monkeypatch):
    pytest.importorskip("sklearn")
    from app import config
    from app.credit import routes as credit
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    client.get("/api/v1/credit/pd/modele", headers=admin.h)
    m = client.get("/api/v1/admin/statistiques", headers=admin.h).json()["modeles"][0]
    assert m["present"] and m["source"] == "synthetique" and 0.5 < m["valeur"] < 1 and m["route_entrainement"].endswith("/entrainer")


def test_performances(client, utilisateur):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    for jour in ("2020-01-20", "2020-01-21", "2020-01-22", "2020-01-23", "2020-01-24", "2020-01-27"):
        client.post("/api/v1/horloge/aller-a", json={"instant": f"{jour}T17:00:00"}, headers=bob.h)
    p = client.get("/api/v1/admin/performances", headers=admin.h).json()
    par_nom = {x["nom"]: x for x in p}
    assert par_nom["Bob"]["portefeuille"]["points"] >= 5 and par_nom["Chef"]["portefeuille"] is None and par_nom["Bob"]["email"] == "bob@example.com"
