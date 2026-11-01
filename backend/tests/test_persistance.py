"""Le bac à sable survit à un redémarrage du serveur."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.main import Contexte, app, obtenir_contexte
from app.marche.moteur import MoteurMarche
from app.trading import persistance
from app.trading.persistance import BacEtat, ExecutionDb, OrdreDb, PositionDb


def aller(client, u, instant="2020-01-15T17:00:00"):
    assert client.post("/api/v1/horloge/aller-a", json={"instant": instant}, headers=u.h).status_code == 200


def ordre(**kw):
    return {"symbole": "TST", "sens": "achat", "quantite": 5, "type": "marche", **kw}


def comptes(base, modele, uid):
    with base.session() as s:
        return s.scalar(select(func.count()).select_from(modele).where(modele.utilisateur_id == uid))


def test_redemarrage_restaure_ordres_positions_executions_et_horloge(client, utilisateur, base_test, univers_test, magasin_test):
    from fastapi.testclient import TestClient

    u = utilisateur()
    aller(client, u)
    client.post("/api/v1/ordres", json=ordre(quantite=7), headers=u.h)
    attente = client.post("/api/v1/ordres", json=ordre(type="limite", prix_limite=1.0), headers=u.h).json()
    avant = client.get("/api/v1/portefeuille", headers=u.h).json()
    ordres_avant = client.get("/api/v1/ordres", headers=u.h).json()
    execs_avant = client.get("/api/v1/executions", headers=u.h).json()
    instant_avant = client.get("/api/v1/horloge", headers=u.h).json()["maintenant"]

    # « Redémarrage » : un contexte neuf, mêmes données, même base.
    neuf = Contexte(univers_test, magasin_test, MoteurMarche(magasin_test, univers_test), base=base_test)
    app.dependency_overrides[obtenir_contexte] = lambda: neuf
    c2 = TestClient(app)

    apres = c2.get("/api/v1/portefeuille", headers=u.h).json()
    assert apres["positions"] == avant["positions"] and apres["cash"] == pytest.approx(avant["cash"])
    assert apres["frais_cumules"] == pytest.approx(avant["frais_cumules"])
    assert c2.get("/api/v1/ordres", headers=u.h).json() == ordres_avant
    assert c2.get("/api/v1/executions", headers=u.h).json() == execs_avant
    h = c2.get("/api/v1/horloge", headers=u.h).json()
    assert h["maintenant"] == instant_avant and h["en_pause"] is True            # reprend à l'instant enregistré, en pause

    # La numérotation continue et l'ordre en attente reste annulable.
    suivant = c2.post("/api/v1/ordres", json=ordre(quantite=1), headers=u.h).json()
    assert suivant["id"] == attente["id"] + 1
    assert c2.delete(f"/api/v1/ordres/{attente['id']}", headers=u.h).json()["statut"] == "annule"


def test_sauvegarde_seulement_quand_l_etat_change(client, utilisateur, monkeypatch):
    u = utilisateur()
    aller(client, u)
    appels = []
    reel = persistance.sauvegarder
    monkeypatch.setattr(persistance, "sauvegarder", lambda *a, **k: appels.append(1) or reel(*a, **k))
    for _ in range(10):
        client.get("/api/v1/portefeuille", headers=u.h)
        client.get("/api/v1/marche/instantane", headers=u.h)
    assert appels == []                                       # lectures : aucune écriture en base
    client.post("/api/v1/ordres", json=ordre(), headers=u.h)
    assert len(appels) == 1


def test_les_executions_ne_sont_ajoutees_qu_une_fois(client, utilisateur, base_test):
    u = utilisateur()
    aller(client, u)
    for _ in range(3):
        client.post("/api/v1/ordres", json=ordre(quantite=1), headers=u.h)
    assert comptes(base_test, ExecutionDb, u.id) == 3
    assert comptes(base_test, OrdreDb, u.id) == 3 and comptes(base_test, PositionDb, u.id) == 1


def test_reinitialiser_efface_aussi_la_base(client, utilisateur, base_test):
    u = utilisateur()
    aller(client, u)
    client.post("/api/v1/ordres", json=ordre(), headers=u.h)
    assert comptes(base_test, BacEtat, u.id) == 1
    client.post("/api/v1/bac/reinitialiser", headers=u.h)
    assert all(comptes(base_test, m, u.id) == 0 for m in (BacEtat, OrdreDb, PositionDb, ExecutionDb))
    assert client.get("/api/v1/portefeuille", headers=u.h).json()["positions"] == []


@pytest.mark.erreur_attendue
def test_une_panne_de_base_ne_bloque_pas_le_trading(client, utilisateur, monkeypatch):
    u = utilisateur()
    aller(client, u)

    def panne(*a, **k):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(persistance, "sauvegarder", panne)
    r = client.post("/api/v1/ordres", json=ordre(), headers=u.h)
    assert r.status_code == 201 and r.json()["statut"] == "execute"            # le trade a bien eu lieu


def test_les_bacs_de_deux_utilisateurs_sont_enregistres_separement(client, utilisateur, base_test):
    a, b = utilisateur(), utilisateur("bob@example.com", "Bob")
    for u in (a, b):
        aller(client, u)
    client.post("/api/v1/ordres", json=ordre(quantite=2), headers=a.h)
    client.post("/api/v1/ordres", json=ordre(quantite=9), headers=b.h)
    with base_test.session() as s:
        etat_a, etat_b = persistance.charger(s, a.id), persistance.charger(s, b.id)
    assert etat_a["positions"][0]["quantite"] == 2 and etat_b["positions"][0]["quantite"] == 9


def test_requetes_simultanees_n_executent_pas_un_ordre_deux_fois(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-01-15T17:00:00")
    cot = client.get("/api/v1/cotations/TST", headers=u.h).json()["prix"]
    o = client.post("/api/v1/ordres", json=ordre(quantite=3, type="limite", prix_limite=round(cot * 0.9, 2)), headers=u.h).json()
    assert o["statut"] == "en_attente"

    def interroger(i):
        chemin = ["/api/v1/portefeuille", "/api/v1/marche/instantane", "/api/v1/ordres", "/api/v1/executions"][i % 4]
        return client.get(chemin, headers=u.h).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert set(pool.map(interroger, range(40))) == {200}
    aller(client, u, "2020-01-16T17:00:00")                                   # le temps avance : l'ordre peut se déclencher
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(interroger, range(40)))
    ex = client.get("/api/v1/executions", headers=u.h).json()
    assert sum(e["quantite"] for e in ex) <= 3 + 1e-9                          # jamais plus que la quantité de l'ordre


def test_base_de_developpement_ancienne_est_refusee_avec_un_message_clair(tmp_path):
    """Une table existante à laquelle il manque une colonne ne doit pas échouer en silence plus tard."""
    import sqlite3
    import pytest
    from app.utilisateurs.db import BaseUtilisateurs

    fichier = tmp_path / "ancienne.db"
    c = sqlite3.connect(fichier)
    c.execute("CREATE TABLE bacs_executions (id INTEGER PRIMARY KEY, utilisateur_id INTEGER)")   # sans la colonne « pnl »
    c.commit(); c.close()
    with pytest.raises(RuntimeError, match="data/utilisateurs.db"):
        BaseUtilisateurs(f"sqlite:///{fichier}")
