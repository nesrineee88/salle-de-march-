import json
from datetime import timedelta

from sqlalchemy import select

from app.utilisateurs import securite
from app.utilisateurs.modeles import JetonRafraichissement, JournalAudit, Utilisateur, maintenant

from .conftest import MDP


def corps(email="alice@example.com", nom="Alice", mdp=MDP, **extra):
    return {"email": email, "nom": nom, "mot_de_passe": mdp, **extra}


# ------------------------------------------------------------------ inscription
def test_inscription_ok_et_mot_de_passe_jamais_stocke_en_clair(client, base_test):
    r = client.post("/api/v1/auth/inscription", json=corps("Alice@Example.com"))
    assert r.status_code == 201
    assert r.json()["email"] == "alice@example.com" and r.json()["role"] == "apprenant"
    assert "mot_de_passe" not in r.text and "hash" not in r.text
    with base_test.session() as s:
        u = s.scalar(select(Utilisateur))
        assert u.mot_de_passe_hash.startswith("$argon2id$") and MDP not in u.mot_de_passe_hash


def test_on_ne_peut_pas_s_attribuer_un_role_a_l_inscription(client):
    r = client.post("/api/v1/auth/inscription", json=corps(role="admin", actif=True))
    assert r.status_code == 201 and r.json()["role"] == "apprenant"


def test_inscription_refus(client):
    client.post("/api/v1/auth/inscription", json=corps())
    assert client.post("/api/v1/auth/inscription", json=corps("ALICE@example.com", "Autre")).status_code == 409
    assert client.post("/api/v1/auth/inscription", json=corps("autre@example.com", "ALICE")).status_code == 409
    for mauvais, code in ((corps("pas-un-email"), "email_invalide"), (corps(nom="A"), "nom_invalide"),
                          (corps("b@example.com", "Bob", "court1"), "mot_de_passe_faible")):
        r = client.post("/api/v1/auth/inscription", json=mauvais)
        assert r.status_code == 422 and r.json()["code"] == code


# ------------------------------------------------------------------ connexion
def test_connexion_message_identique_pour_compte_inconnu_et_mauvais_mot_de_passe(client):
    client.post("/api/v1/auth/inscription", json=corps())
    a = client.post("/api/v1/auth/connexion", json={"email": "alice@example.com", "mot_de_passe": "mauvais-mdp-12"})
    b = client.post("/api/v1/auth/connexion", json={"email": "inconnu@example.com", "mot_de_passe": "mauvais-mdp-12"})
    assert a.status_code == b.status_code == 401 and a.json()["detail"] == b.json()["detail"]


def test_verrouillage_apres_cinq_echecs_meme_avec_le_bon_mot_de_passe_puis_deblocage(client, base_test):
    client.post("/api/v1/auth/inscription", json=corps())
    mauvais = {"email": "alice@example.com", "mot_de_passe": "mauvais-mdp-12"}
    for _ in range(5):
        assert client.post("/api/v1/auth/connexion", json=mauvais).status_code == 401
    bon = {"email": "alice@example.com", "mot_de_passe": MDP}
    assert client.post("/api/v1/auth/connexion", json=bon).status_code == 423          # verrouillé
    with base_test.session() as s:
        s.scalar(select(Utilisateur)).verrouille_jusqua = maintenant() - timedelta(seconds=1)
        s.commit()
    assert client.post("/api/v1/auth/connexion", json=bon).status_code == 200          # délai écoulé


def test_succes_remet_le_compteur_d_echecs_a_zero(client, base_test):
    client.post("/api/v1/auth/inscription", json=corps())
    mauvais = {"email": "alice@example.com", "mot_de_passe": "mauvais-mdp-12"}
    for _ in range(4):
        client.post("/api/v1/auth/connexion", json=mauvais)
    client.post("/api/v1/auth/connexion", json={"email": "alice@example.com", "mot_de_passe": MDP})
    for _ in range(4):
        assert client.post("/api/v1/auth/connexion", json=mauvais).status_code == 401  # pas de verrou : 4 < 5


# ------------------------------------------------------------------ jetons d'accès
def test_acces_protege(client, utilisateur):
    u = utilisateur()
    assert client.get("/api/v1/moi", headers=u.h).json()["email"] == "alice@example.com"
    assert client.get("/api/v1/moi").status_code == 401
    assert client.get("/api/v1/moi", headers={"Authorization": "Bearer n-importe-quoi"}).status_code == 401
    expire = securite.creer_jeton_acces(u.id, "apprenant", duree_min=-1)
    assert client.get("/api/v1/moi", headers={"Authorization": f"Bearer {expire}"}).status_code == 401


def test_le_role_du_jeton_est_ignore_le_role_en_base_fait_foi(client, utilisateur):
    u = utilisateur()
    faux_admin = securite.creer_jeton_acces(u.id, "admin")          # jeton signé mais revendiquant « admin »
    r = client.get("/api/v1/admin/utilisateurs", headers={"Authorization": f"Bearer {faux_admin}"})
    assert r.status_code == 403


def test_compte_desactive_perd_l_acces_immediatement_et_ses_sessions(client, utilisateur):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    assert client.patch(f"/api/v1/admin/utilisateurs/{bob.id}", json={"actif": False}, headers=admin.h).status_code == 200
    assert client.get("/api/v1/moi", headers=bob.h).status_code == 401
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": bob.refresh}).status_code == 401
    r = client.post("/api/v1/auth/connexion", json={"email": "bob@example.com", "mot_de_passe": MDP})
    assert r.status_code == 403 and r.json()["code"] == "desactive"


# ------------------------------------------------------------------ rafraîchissement
def test_rotation_du_jeton_de_rafraichissement(client, utilisateur):
    u = utilisateur()
    r = client.post("/api/v1/auth/rafraichir", json={"refresh_token": u.refresh})
    assert r.status_code == 200 and r.json()["refresh_token"] != u.refresh
    nouveau = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/v1/moi", headers=nouveau).status_code == 200


def test_reutilisation_d_un_ancien_jeton_revoque_toute_la_session(client, utilisateur, base_test):
    u = utilisateur()
    r1 = client.post("/api/v1/auth/rafraichir", json={"refresh_token": u.refresh}).json()
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": u.refresh}).status_code == 401   # rejeu
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": r1["refresh_token"]}).status_code == 401
    with base_test.session() as s:
        assert any(a.action == "jeton_reutilise" for a in s.scalars(select(JournalAudit)))


def test_jeton_de_rafraichissement_expire_ou_inconnu(client, utilisateur, base_test):
    u = utilisateur()
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": "x" * 40}).status_code == 401
    with base_test.session() as s:
        s.scalar(select(JetonRafraichissement)).expire_le = maintenant() - timedelta(seconds=1)
        s.commit()
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": u.refresh}).status_code == 401


def test_deconnexion_idempotente(client, utilisateur):
    u = utilisateur()
    assert client.post("/api/v1/auth/deconnexion", json={"refresh_token": u.refresh}).status_code == 204
    assert client.post("/api/v1/auth/deconnexion", json={"refresh_token": u.refresh}).status_code == 204
    assert client.post("/api/v1/auth/rafraichir", json={"refresh_token": u.refresh}).status_code == 401


def test_les_jetons_ne_sont_jamais_stockes_en_clair(client, utilisateur, base_test):
    u = utilisateur()
    with base_test.session() as s:
        assert s.scalar(select(JetonRafraichissement)).empreinte != u.refresh


# ------------------------------------------------------------------ rôles et administration
def test_controle_d_acces_par_role(client, utilisateur):
    apprenant = utilisateur()
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    for chemin in ("/api/v1/admin/utilisateurs", "/api/v1/admin/audit"):
        assert client.get(chemin, headers=apprenant.h).status_code == 403
        assert client.get(chemin, headers=admin.h).status_code == 200
        assert client.get(chemin).status_code == 401


def test_administration_des_utilisateurs(client, utilisateur):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    r = client.patch(f"/api/v1/admin/utilisateurs/{bob.id}", json={"role": "formateur"}, headers=admin.h)
    assert r.status_code == 200 and r.json()["role"] == "formateur"
    assert client.patch(f"/api/v1/admin/utilisateurs/{bob.id}", json={"role": "roi"}, headers=admin.h).status_code == 422
    assert client.patch("/api/v1/admin/utilisateurs/9999", json={"actif": False}, headers=admin.h).status_code == 404
    r = client.patch(f"/api/v1/admin/utilisateurs/{admin.id}", json={"actif": False}, headers=admin.h)
    assert r.status_code == 409                                      # un admin ne peut pas se verrouiller dehors
    assert {u["email"] for u in client.get("/api/v1/admin/utilisateurs", headers=admin.h).json()} == {
        "admin@example.com", "bob@example.com"}


def test_la_retrogradation_est_immediate(client, utilisateur):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    autre = utilisateur("autre@example.com", "Autre", role="admin")
    assert client.get("/api/v1/admin/audit", headers=autre.h).status_code == 200
    client.patch(f"/api/v1/admin/utilisateurs/{autre.id}", json={"role": "apprenant"}, headers=admin.h)
    assert client.get("/api/v1/admin/audit", headers=autre.h).status_code == 403   # même jeton, rôle relu en base


# ------------------------------------------------------------------ audit
def test_journal_d_audit_complet_sans_donnees_sensibles(client, utilisateur):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    client.post("/api/v1/auth/connexion", json={"email": "bob@example.com", "mot_de_passe": "mauvais-mdp-12"})
    client.post("/api/v1/auth/rafraichir", json={"refresh_token": bob.refresh})
    client.patch(f"/api/v1/admin/utilisateurs/{bob.id}", json={"role": "trader"}, headers=admin.h)
    journal = client.get("/api/v1/admin/audit?limite=200", headers=admin.h).json()
    actions = {a["action"] for a in journal}
    assert {"inscription", "connexion", "connexion_echec", "modification_utilisateur"} <= actions
    texte = json.dumps(journal)
    assert MDP not in texte and bob.refresh not in texte and "mauvais-mdp-12" not in texte and "argon2" not in texte


# ------------------------------------------------------------------ profil de risque
def test_profil_de_risque(client, utilisateur):
    u = utilisateur()
    q = client.get("/api/v1/profil-risque/questionnaire").json()
    assert len(q["questions"]) == 6 and "conseil" in q["avertissement"]
    assert client.post("/api/v1/moi/profil-risque", json={"reponses": {"q1": 1}}, headers=u.h).status_code == 422
    reponses = {f"q{i}": 3 for i in range(1, 7)}
    r = client.post("/api/v1/moi/profil-risque", json={"reponses": reponses}, headers=u.h)
    assert r.status_code == 200 and r.json()["categorie"] == "dynamique" and r.json()["perte_max_toleree_pct"] == 20.0
    assert client.get("/api/v1/moi", headers=u.h).json()["profil_risque"]["score"] == 18
    assert client.post("/api/v1/moi/profil-risque", json={"reponses": reponses}).status_code == 401


# ------------------------------------------------------------------ limitation de débit
def test_limitation_de_debit_par_ip(client):
    from app.main import app
    from app.utilisateurs.limiteur import LimiteurFenetre
    from app.utilisateurs.routes import obtenir_limiteur

    limiteur = LimiteurFenetre(3, 300)                  # une seule instance, comme en production (lru_cache)
    app.dependency_overrides[obtenir_limiteur] = lambda: limiteur
    essais = [client.post("/api/v1/auth/connexion", json={"email": "x@example.com", "mot_de_passe": "mauvais-mdp-12"})
              for _ in range(5)]
    assert [r.status_code for r in essais] == [401, 401, 401, 429, 429]
