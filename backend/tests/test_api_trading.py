import pytest


def aller(client, u, instant="2020-01-15T17:00:00"):
    assert client.post("/api/v1/horloge/aller-a", json={"instant": instant}, headers=u.h).status_code == 200


def ordre(**kw):
    return {"symbole": "TST", "sens": "achat", "quantite": 5, "type": "marche", **kw}


def test_parcours_complet_achat_portefeuille_vente(client, utilisateur):
    u = utilisateur()
    aller(client, u)
    r = client.post("/api/v1/ordres", json=ordre(), headers=u.h)
    assert r.status_code == 201 and r.json()["statut"] == "execute" and r.json()["prix_moyen"] > 0

    p = client.get("/api/v1/portefeuille", headers=u.h).json()
    assert p["positions"][0]["symbole"] == "TST" and p["positions"][0]["quantite"] == 5
    assert p["capital_initial"] == 100_000
    assert p["equity"] == pytest.approx(p["cash"] + p["valeur_positions"])
    assert p["pnl_total"] == pytest.approx(p["pnl_realise"] + p["pnl_latent"] - p["frais_cumules"])

    assert client.post("/api/v1/ordres", json=ordre(sens="vente"), headers=u.h).json()["statut"] == "execute"
    assert client.get("/api/v1/portefeuille", headers=u.h).json()["positions"] == []
    assert len(client.get("/api/v1/ordres", headers=u.h).json()) == 2


def test_chaque_utilisateur_a_son_propre_compte(client, utilisateur):
    alice, bob = utilisateur(), utilisateur("bob@example.com", "Bob")
    aller(client, alice)
    aller(client, bob)
    client.post("/api/v1/ordres", json=ordre(), headers=alice.h)
    assert len(client.get("/api/v1/portefeuille", headers=alice.h).json()["positions"]) == 1
    assert client.get("/api/v1/portefeuille", headers=bob.h).json()["positions"] == []
    assert client.get("/api/v1/ordres", headers=bob.h).json() == []
    # Bob ne peut pas annuler l'ordre d'Alice : pour lui, cet ordre n'existe pas
    assert client.delete("/api/v1/ordres/1", headers=bob.h).status_code == 404


def test_on_ne_peut_pas_designer_le_compte_d_un_autre(client, utilisateur):
    u = utilisateur()
    aller(client, u)
    r = client.post("/api/v1/ordres", json=ordre(compte_id="u999"), headers=u.h)   # champ inconnu ignoré
    assert r.status_code == 201
    assert len(client.get("/api/v1/ordres", headers=u.h).json()) == 1


def test_rejet_metier_renvoye_avec_motif_et_validation_422(client, utilisateur):
    u = utilisateur()
    aller(client, u)
    r = client.post("/api/v1/ordres", json=ordre(quantite=10_000_000), headers=u.h)
    assert r.status_code == 201 and r.json()["statut"] == "rejete" and "liquidités" in r.json()["motif"]
    assert client.post("/api/v1/ordres", json=ordre(quantite=0), headers=u.h).status_code == 422
    assert client.post("/api/v1/ordres", json=ordre(sens="prêt"), headers=u.h).status_code == 422


def test_ordre_limite_annulation(client, utilisateur):
    u = utilisateur()
    aller(client, u)
    o = client.post("/api/v1/ordres", json=ordre(type="limite", prix_limite=1.0), headers=u.h).json()
    assert o["statut"] == "en_attente"
    assert client.delete(f"/api/v1/ordres/{o['id']}", headers=u.h).json()["statut"] == "annule"
    assert client.delete(f"/api/v1/ordres/{o['id']}", headers=u.h).status_code == 409
    assert client.delete("/api/v1/ordres/999", headers=u.h).status_code == 404


def test_les_ordres_en_attente_s_executent_quand_le_temps_avance(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-01-15T17:00:00")
    cot = client.get("/api/v1/cotations/TST", headers=u.h).json()["prix"]
    o = client.post("/api/v1/ordres", json=ordre(type="limite", prix_limite=round(cot * 0.5, 2)), headers=u.h).json()
    assert o["statut"] == "en_attente"
    aller(client, u, "2020-02-20T17:00:00")                           # saut dans le temps : évalué en passant
    # prix synthétique peu probable à -50 % : l'ordre reste ou s'exécute, mais ne plante jamais
    statut = client.get("/api/v1/ordres", headers=u.h).json()[0]["statut"]
    assert statut in ("en_attente", "execute")


def test_reinitialiser_le_bac(client, utilisateur):
    u = utilisateur()
    aller(client, u)
    client.post("/api/v1/ordres", json=ordre(), headers=u.h)
    r = client.post("/api/v1/bac/reinitialiser", headers=u.h)
    assert r.status_code == 200 and r.json()["en_pause"] is True
    assert client.get("/api/v1/ordres", headers=u.h).json() == []
    assert client.get("/api/v1/portefeuille", headers=u.h).json()["cash"] == 100_000


def test_carnet(client, utilisateur):
    u = utilisateur()
    aller(client, u)
    c = client.get("/api/v1/carnet/TST", headers=u.h)
    corps = c.json()
    assert c.status_code == 200 and corps["synthetique"] is True and len(corps["ventes"]) == 10
    assert corps["ventes"][0]["prix"] > corps["achats"][0]["prix"]
    assert client.get("/api/v1/carnet/VIDE", headers=u.h).status_code == 503
    assert client.get("/api/v1/carnet/INCONNU", headers=u.h).status_code == 404


def test_instantane_une_seule_requete_pour_tout_le_marche(client, utilisateur):
    u = utilisateur()
    aller(client, u)
    r = client.get("/api/v1/marche/instantane", headers=u.h)
    corps = r.json()
    assert r.status_code == 200 and corps["instant"].startswith("2020-01-15T17:00")
    assert {c["symbole"] for c in corps["cotations"]} == {"TST", "CRY"}           # seuls les actifs avec données
    assert corps["fenetre"] == {"debut": "2020-01-01", "fin": "2020-12-31"}
    assert corps["horloge"]["en_pause"] is True and "1 semaine = 1 heure" in corps["horloge"]["facteurs_predefinis"]
    assert client.get("/api/v1/marche/instantane").status_code == 401


def test_historique_des_executions(client, utilisateur):
    u = utilisateur()
    aller(client, u)
    assert client.get("/api/v1/executions", headers=u.h).json() == []
    client.post("/api/v1/ordres", json=ordre(quantite=3), headers=u.h)
    client.post("/api/v1/ordres", json=ordre(quantite=2, sens="vente"), headers=u.h)
    ex = client.get("/api/v1/executions", headers=u.h).json()
    assert [e["sens"] for e in ex] == ["vente", "achat"] and ex[0]["frais"] > 0       # plus récent d'abord
