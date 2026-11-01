from datetime import datetime

import pytest


def aller(client, u, instant):
    r = client.post("/api/v1/horloge/aller-a", json={"instant": instant}, headers=u.h)
    assert r.status_code == 200, r.text
    return r.json()


def test_les_routes_de_marche_exigent_une_connexion(client):
    for chemin in ("/api/v1/actifs", "/api/v1/horloge", "/api/v1/cotations/TST", "/api/v1/carnet/TST",
                   "/api/v1/historique/TST", "/api/v1/portefeuille", "/api/v1/ordres"):
        r = client.get(chemin)
        assert r.status_code == 401, chemin
        assert r.headers["www-authenticate"] == "Bearer"
    assert client.get("/api/v1/sante").status_code == 200           # seule la santé est publique


def test_sante_signale_les_actifs_sans_donnees(client):
    r = client.get("/api/v1/sante").json()
    assert r["statut"] == "donnees_incompletes" and set(r["actifs_manquants"]) == {"WTI", "VIDE"}


def test_catalogue(client, utilisateur):
    u = utilisateur()
    actifs = {a["symbole"]: a for a in client.get("/api/v1/actifs", headers=u.h).json()}
    assert actifs["TST"]["disponible"] and "premiere_cotation" in actifs["TST"]
    assert not actifs["VIDE"]["disponible"] and "premiere_cotation" not in actifs["VIDE"]


def test_horloge_personnelle_pause_facteur_et_aller_a(client, utilisateur):
    u = utilisateur()
    assert client.get("/api/v1/horloge", headers=u.h).json()["en_pause"] is True      # démarre en pause
    assert aller(client, u, "2020-02-03T17:00:00")["maintenant"].startswith("2020-02-03T17:00")
    assert client.post("/api/v1/horloge/facteur", json={"facteur": 24}, headers=u.h).json()["facteur"] == 24
    assert client.post("/api/v1/horloge/facteur", json={"facteur": 0}, headers=u.h).status_code == 422
    for hors in ("2030-01-01T00:00:00", "2010-01-01T00:00:00"):
        assert client.post("/api/v1/horloge/aller-a", json={"instant": hors}, headers=u.h).status_code == 422
    assert client.post("/api/v1/horloge/reprendre", headers=u.h).json()["en_pause"] is False
    assert client.post("/api/v1/horloge/pause", headers=u.h).json()["en_pause"] is True


def test_chaque_utilisateur_a_son_propre_temps(client, utilisateur):
    alice, bob = utilisateur(), utilisateur("bob@example.com", "Bob")
    aller(client, alice, "2020-02-03T17:00:00")
    aller(client, bob, "2020-01-15T17:00:00")
    assert client.get("/api/v1/horloge", headers=alice.h).json()["maintenant"].startswith("2020-02-03")
    assert client.get("/api/v1/horloge", headers=bob.h).json()["maintenant"].startswith("2020-01-15")
    ca = client.get("/api/v1/cotations/TST", headers=alice.h).json()
    cb = client.get("/api/v1/cotations/TST", headers=bob.h).json()
    assert ca["horodatage"].startswith("2020-02-03") and cb["horodatage"].startswith("2020-01-15")


def test_cotation_et_historique(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-01-15T17:00:00")
    c = client.get("/api/v1/cotations/TST", headers=u.h)
    corps = c.json()
    assert c.status_code == 200 and corps["statut"] == "ouvert" and corps["origine"] == "tick_simule"
    assert corps["barre_en_formation"]["low"] <= corps["prix"] <= corps["barre_en_formation"]["high"]
    h = client.get("/api/v1/historique/TST?barres=10", headers=u.h).json()
    assert 1 <= len(h) <= 10 and h[-1]["en_formation"]


def test_toute_premiere_seance_sans_cloture_precedente(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-01-01T08:00:00")
    corps = client.get("/api/v1/cotations/TST", headers=u.h).json()
    assert corps["statut"] == "ferme" and corps["origine"] == "ouverture" and corps["barre_en_formation"] is None


def test_erreurs_404_503_422(client, utilisateur):
    u = utilisateur()
    assert client.get("/api/v1/cotations/INCONNU", headers=u.h).status_code == 404
    assert client.get("/api/v1/cotations/VIDE", headers=u.h).status_code == 503
    assert client.get("/api/v1/historique/TST?barres=0", headers=u.h).status_code == 422
