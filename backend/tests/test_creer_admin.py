from sqlalchemy import select

from app.utilisateurs import creer_admin
from app.utilisateurs.modeles import Utilisateur
from app.utilisateurs.service import inscrire

from .conftest import MDP


def test_creation_et_promotion(base_test):
    with base_test.session() as s:
        u = creer_admin.creer_admin(s, "Chef@Example.com", "Chef", MDP)
        assert u.role == "admin" and u.email == "chef@example.com"
        simple = inscrire(s, "bob@example.com", "Bob", MDP)
        simple.actif = False
        s.commit()
        promu = creer_admin.creer_admin(s, "bob@example.com", "Bob", "ignore")     # promotion d'un compte existant
        assert promu.role == "admin" and promu.actif
        assert len(s.scalars(select(Utilisateur)).all()) == 2


def test_cli_mots_de_passe_differents(monkeypatch, base_test):
    reponses = iter(["Motdepasse-2026x", "autre-chose-12"])
    monkeypatch.setattr(creer_admin.getpass, "getpass", lambda _msg: next(reponses))
    assert creer_admin.main(["a@example.com", "Admin"]) == 1


def test_cli_usage():
    assert creer_admin.main([]) == 2
