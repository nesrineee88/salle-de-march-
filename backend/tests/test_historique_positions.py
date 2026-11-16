"""Historique des positions (ouverture → clôture), reconstruit à partir des exécutions : une position clôturée reste visible."""
import pytest

from app.trading.historique import historique_positions

from .test_portefeuille_api import acheter, aller


def _e(ordre, sens, q, prix, frais, instant, pnl=None, symbole="AAPL"):
    return {"ordre_id": ordre, "symbole": symbole, "sens": sens, "quantite": q, "prix": prix, "frais": frais,
            "instant": instant, "pnl": pnl}


EXECUTIONS = [
    _e(1, "achat", 10, 100.0, 0.5, "2021-01-04T15:00:00"),
    _e(2, "achat", 10, 110.0, 0.55, "2021-01-05T15:00:00"),                 # prix de revient moyen : 105
    _e(3, "vente", 5, 120.0, 0.3, "2021-01-06T15:00:00", pnl=75.0),         # (120 − 105) × 5
    _e(9, "achat", 2, 300.0, 0.3, "2021-01-06T16:00:00", symbole="MSFT"),
    _e(4, "vente", 15, 90.0, 0.675, "2021-01-07T15:00:00", pnl=-225.0),     # (90 − 105) × 15, par la règle 7 → clôture
    _e(5, "achat", 3, 95.0, 0.1425, "2021-01-08T15:00:00"),                 # nouvelle position AAPL
]


def test_cycle_cloture_calcule_a_la_main():
    h = historique_positions(EXECUTIONS, {3: None, 4: "regle:7"}, {7: "stop_loss"})
    cloture = next(c for c in h if c["statut"] == "cloturee")
    assert cloture["symbole"] == "AAPL"
    assert cloture["ouverte_le"] == "2021-01-04T15:00:00" and cloture["cloturee_le"] == "2021-01-07T15:00:00"
    assert cloture["quantite_max"] == pytest.approx(20)
    assert cloture["prix_achat_moyen"] == pytest.approx(105.0)                # (1000 + 1100) / 20
    assert cloture["prix_vente_moyen"] == pytest.approx(97.5)                 # (600 + 1350) / 20
    assert cloture["pnl_realise"] == pytest.approx(-150.0)                    # 75 − 225
    assert cloture["frais"] == pytest.approx(2.025)                           # 0,5 + 0,55 + 0,3 + 0,675
    assert cloture["resultat_net"] == pytest.approx(-152.025)
    assert cloture["rendement_net"] == pytest.approx(-152.025 / 2100)        # −7,24 %
    assert cloture["motif_cloture"] == "stop_loss" and cloture["nb_operations"] == 4


def test_positions_ouvertes_et_tri():
    h = historique_positions(EXECUTIONS, {}, {})
    assert [(c["symbole"], c["statut"]) for c in h] == [("AAPL", "ouverte"), ("MSFT", "ouverte"), ("AAPL", "cloturee")]
    nouvelle = h[0]
    assert nouvelle["quantite_restante"] == pytest.approx(3) and nouvelle["cloturee_le"] is None
    assert nouvelle["prix_vente_moyen"] is None and nouvelle["pnl_realise"] == 0.0
    assert h[2]["motif_cloture"] == "manuelle"                                # origine inconnue : vente de l'utilisateur


def test_regle_inconnue_et_historique_vide():
    assert historique_positions([], {}, {}) == []
    h = historique_positions(EXECUTIONS[:5], {4: "regle:99"}, {})
    assert next(c for c in h if c["statut"] == "cloturee")["motif_cloture"] == "regle"


def test_vente_sans_achat_ignoree():
    # Ne devrait pas arriver (pas de vente à découvert) : la ligne est ignorée plutôt que de fausser les calculs.
    assert historique_positions([_e(1, "vente", 1, 10.0, 0.0, "2021-01-04T15:00:00", pnl=0.0)], {}, {}) == []


def test_api_position_cloturee_reste_dans_l_historique(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-20T17:00:00")
    assert acheter(client, u, 10)["statut"] == "execute"
    assert acheter(client, u, 10, sens="vente")["statut"] == "execute"
    assert client.get("/api/v1/portefeuille", headers=u.h).json()["positions"] == []
    h = client.get("/api/v1/portefeuille/positions/historique", headers=u.h)
    assert h.status_code == 200
    (c,) = h.json()
    assert c["symbole"] == "TST" and c["statut"] == "cloturee" and c["motif_cloture"] == "manuelle"
    assert c["frais"] > 0 and c["resultat_net"] == pytest.approx(c["pnl_realise"] - c["frais"])
