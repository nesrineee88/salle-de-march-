from sqlalchemy import select

from app.utilisateurs.modeles import JournalAudit
from .conftest import MDP


def connexion(client, email="alice@example.com", mdp=MDP, agent="Navigateur-A"):
    r = client.post("/api/v1/auth/connexion", json={"email": email, "mot_de_passe": mdp}, headers={"user-agent": agent})
    assert r.status_code == 200, r.text
    c = r.json()
    return {"h": {"Authorization": f"Bearer {c['access_token']}"}, "refresh": c["refresh_token"]}


def test_liste_des_appareils_connectes_et_session_courante(client, utilisateur):
    u = utilisateur()                                              # 1re session (celle du fixture)
    deuxieme = connexion(client, agent="Telephone")
    r = client.post("/api/v1/moi/sessions", json={"refresh_token": deuxieme["refresh"]}, headers=u.h)
    sessions = r.json()
    assert r.status_code == 200 and len(sessions) == 2
    courante = [s for s in sessions if s["courante"]]
    assert len(courante) == 1 and courante[0]["agent"] == "Telephone"
    assert all({"famille", "debut", "derniere_activite", "ip"} <= s.keys() for s in sessions)
    assert "empreinte" not in str(sessions) and u.refresh not in str(sessions)               # aucun secret exposé


def test_fermer_une_session_la_rend_inutilisable(client, utilisateur):
    u = utilisateur()
    autre = connexion(client, agent="Autre")
    sessions = client.post("/api/v1/moi/sessions", json={"refresh_token": u.refresh}, headers=u.h).json()
    cible = next(s for s in sessions if s["agent"] == "Autre")
    assert client.delete(f"/api/v1/moi/sessions/{cible['famille']}", headers=u.h).status_code == 204
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": autre["refresh"]}).status_code == 401
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": u.refresh}).status_code == 200   # la mienne reste valable
    assert client.delete("/api/v1/moi/sessions/inexistante", headers=u.h).status_code == 404


def test_on_ne_peut_pas_fermer_la_session_d_un_autre(client, utilisateur):
    alice, bob = utilisateur(), utilisateur("bob@example.com", "Bob")
    sessions_bob = client.post("/api/v1/moi/sessions", json={}, headers=bob.h).json()
    assert client.delete(f"/api/v1/moi/sessions/{sessions_bob[0]['famille']}", headers=alice.h).status_code == 404
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": bob.refresh}).status_code == 200


def test_deconnexion_partout(client, utilisateur):
    u = utilisateur()
    autre = connexion(client)
    assert client.post("/api/v1/moi/deconnexion-partout", headers=u.h).status_code == 204
    for refresh in (u.refresh, autre["refresh"]):
        assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": refresh}).status_code == 401


def test_changer_le_mot_de_passe(client, utilisateur):
    u = utilisateur()
    autre = connexion(client)
    nouveau = "Nouveau-Secret-2027"
    assert client.post("/api/v1/moi/mot-de-passe", json={"ancien": "faux-mot-de-passe1", "nouveau": nouveau}, headers=u.h).status_code == 403
    assert client.post("/api/v1/moi/mot-de-passe", json={"ancien": MDP, "nouveau": MDP}, headers=u.h).status_code == 422
    faible = client.post("/api/v1/moi/mot-de-passe", json={"ancien": MDP, "nouveau": "court1"}, headers=u.h)
    assert faible.status_code == 422 and faible.json()["code"] == "mot_de_passe_faible"
    r = client.post("/api/v1/moi/mot-de-passe", json={"ancien": MDP, "nouveau": nouveau, "refresh_token": u.refresh}, headers=u.h)
    assert r.status_code == 204
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": autre["refresh"]}).status_code == 401    # autres appareils déconnectés
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": u.refresh}).status_code == 200          # celui-ci reste connecté
    assert client.post("/api/v1/auth/connexion", json={"email": "alice@example.com", "mot_de_passe": MDP}).status_code == 401
    assert client.post("/api/v1/auth/connexion", json={"email": "alice@example.com", "mot_de_passe": nouveau}).status_code == 200


def test_changement_de_mot_de_passe_sans_garder_de_session(client, utilisateur):
    u = utilisateur()
    client.post("/api/v1/moi/mot-de-passe", json={"ancien": MDP, "nouveau": "Nouveau-Secret-2027"}, headers=u.h)
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": u.refresh}).status_code == 401


def test_audit_des_actions_de_compte_sans_secret(client, utilisateur, base_test):
    u = utilisateur()
    client.post("/api/v1/moi/mot-de-passe", json={"ancien": "faux-mot-de-passe1", "nouveau": "Nouveau-Secret-2027"}, headers=u.h)
    client.post("/api/v1/moi/mot-de-passe", json={"ancien": MDP, "nouveau": "Nouveau-Secret-2027"}, headers=u.h)
    client.post("/api/v1/moi/deconnexion-partout", headers=u.h)
    with base_test.session() as s:
        actions = {a.action for a in s.scalars(select(JournalAudit))}
        texte = str([(a.action, a.details) for a in s.scalars(select(JournalAudit))])
    assert {"mot_de_passe_echec", "mot_de_passe_change", "deconnexion_partout"} <= actions
    assert "Nouveau-Secret-2027" not in texte and MDP not in texte
