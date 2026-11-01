"""Fixtures de TEST : données synthétiques générées au hasard. Elles ne servent qu'aux tests et ne
sont jamais écrites dans data/."""
import sys
from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.marche.catalogue import Actif, Univers  # noqa: E402
from app.marche.stockage import Magasin  # noqa: E402


def serie_synthetique(debut: str, n_jours: int, calendrier: str, prix0: float = 100.0, graine: int = 1):
    rng = np.random.default_rng(graine)
    dates = pd.bdate_range(debut, periods=n_jours) if calendrier == "semaine" else pd.date_range(debut, periods=n_jours)
    close = prix0 + np.cumsum(rng.normal(0, 1.0, len(dates)))
    close = np.maximum(close, 5.0)
    ouv = np.concatenate([[prix0], close[:-1]]) + rng.normal(0, 0.3, len(dates))
    haut = np.maximum(ouv, close) + np.abs(rng.normal(0.5, 0.3, len(dates)))
    bas = np.minimum(ouv, close) - np.abs(rng.normal(0.5, 0.3, len(dates)))
    df = pd.DataFrame(
        {"open": ouv, "high": haut, "low": bas, "close": close,
         "volume": rng.integers(1_000, 9_000, len(dates)).astype(float), "corrige": False},
        index=pd.DatetimeIndex(dates, name="date"),
    )
    return df


@pytest.fixture
def univers_test():
    actifs = {
        "TST": Actif("TST", "Action test", "action", "Test", "semaine", session_utc=(time(14, 30), time(21, 0))),
        "CRY": Actif("CRY", "Crypto test", "crypto", "Test", "continu"),
        "WTI": Actif("WTI", "Pétrole test", "matiere", "Test", "semaine", negatif_ok=True),
        "VIDE": Actif("VIDE", "Sans données", "action", "Test", "semaine"),
    }
    return Univers(date(2020, 1, 1), date(2020, 12, 31), 0, actifs)


@pytest.fixture
def magasin_test():
    return Magasin(
        {
            "TST": serie_synthetique("2020-01-01", 60, "semaine", 100, 1),
            "CRY": serie_synthetique("2020-01-01", 90, "continu", 50, 2),
        }
    )


# ------------------------------------------------------------------ API + utilisateurs
from types import SimpleNamespace  # noqa: E402

from sqlalchemy import select  # noqa: E402


@pytest.fixture
def base_test(tmp_path):
    """Base SQLite dans un fichier temporaire (comme en développement) : sûre avec plusieurs fils d'exécution.
    Avec SDM_TEST_POSTGRES=<url>, les mêmes tests tournent sur un vrai serveur PostgreSQL."""
    import os

    from app.utilisateurs.db import Base, BaseUtilisateurs

    url = os.environ.get("SDM_TEST_POSTGRES")
    if url:
        base = BaseUtilisateurs(url)
        Base.metadata.drop_all(base.moteur)
        Base.metadata.create_all(base.moteur)
        yield base
        base.moteur.dispose()
    else:
        base = BaseUtilisateurs(f"sqlite:///{tmp_path / 'test.db'}")
        yield base
        base.moteur.dispose()


@pytest.fixture
def ctx_test(univers_test, magasin_test, base_test):
    from app.main import Contexte
    from app.marche.moteur import MoteurMarche

    return Contexte(univers_test, magasin_test, MoteurMarche(magasin_test, univers_test), base=base_test)


@pytest.fixture
def client(ctx_test, base_test):
    from fastapi.testclient import TestClient

    from app.main import app, obtenir_contexte
    from app.utilisateurs.db import obtenir_session
    from app.utilisateurs.limiteur import LimiteurFenetre
    from app.utilisateurs.routes import obtenir_limiteur

    ctx = ctx_test

    def session_test():
        s = base_test.session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[obtenir_contexte] = lambda: ctx
    app.dependency_overrides[obtenir_session] = session_test
    app.dependency_overrides[obtenir_limiteur] = lambda: LimiteurFenetre(10_000, 300)
    yield TestClient(app)
    app.dependency_overrides.clear()


MDP = "Motdepasse-2026x"


@pytest.fixture
def utilisateur(client, base_test):
    """Fabrique : crée un compte via l'API, lui donne éventuellement un autre rôle, le connecte."""
    from app.utilisateurs.modeles import Utilisateur

    def _creer(email="alice@example.com", nom="Alice", role="apprenant", mdp=MDP):
        r = client.post("/api/v1/auth/inscription", json={"email": email, "nom": nom, "mot_de_passe": mdp})
        assert r.status_code == 201, r.text
        if role != "apprenant":
            with base_test.session() as s:
                s.scalar(select(Utilisateur).where(Utilisateur.email == email)).role = role
                s.commit()
        r = client.post("/api/v1/auth/connexion", json={"email": email, "mot_de_passe": mdp})
        assert r.status_code == 200, r.text
        corps = r.json()
        return SimpleNamespace(id=corps["utilisateur"]["id"], email=email, mdp=mdp, refresh=corps["refresh_token"],
                               access=corps["access_token"],
                               h={"Authorization": f"Bearer {corps['access_token']}"})

    return _creer


# Une sauvegarde qui échoue est volontairement non bloquante pour l'utilisateur (elle est journalisée) :
# les tests doivent donc vérifier eux-mêmes qu'aucune erreur n'a été journalisée.
@pytest.fixture(autouse=True)
def aucune_erreur_de_sauvegarde(request, caplog):
    yield
    if request.node.get_closest_marker("erreur_attendue"):
        return
    erreurs = [r.getMessage() for r in caplog.records if r.name == "salle_de_marche" and r.levelname == "ERROR"]
    assert not erreurs, f"erreurs journalisées pendant le test : {erreurs}"
