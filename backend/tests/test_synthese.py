"""Synthèse du tableau de bord : niveau de risque global et alertes des règles stop-loss / take-profit."""
import pytest

from app.risque.synthese import alertes_regles, niveau_risque

from .test_portefeuille_api import acheter, aller


def _analyse(var=None, secteurs=None, positions=None, profil=None, dd=0.0):
    """Analyse minimale au format de risque.analyse.analyser (parts exprimées sur la valeur totale)."""
    secteurs = secteurs or []
    positions = positions or []
    return {
        "risque": {"var": var} if var is not None else None,
        "repartition": {
            "secteur": [{"libelle": s, "part": p} for s, p in secteurs] + [{"libelle": "Liquidités", "part": 1 - sum(p for _, p in secteurs)}],
            "position": [{"libelle": s, "part": p} for s, p in positions],
        },
        "profil": profil or {"statut": "profil_absent"},
        "performance": {"drawdown_courant": dd},
    }


def test_portefeuille_sans_position_niveau_aucun():
    r = niveau_risque(_analyse())
    assert r["niveau"] == "aucun" and r["criteres"] == [] and r["part_investie"] == 0.0


def test_portefeuille_faible_risque():
    # 30 % investis, répartis : VaR 0,4 % (< 1 %), position max 10 %, secteur max 20 %, aucune baisse.
    r = niveau_risque(_analyse(var=0.004, secteurs=[("Santé", 0.2), ("Énergie", 0.1)], positions=[("JNJ", 0.1), ("PFE", 0.1), ("XOM", 0.1)]))
    assert r["niveau"] == "faible"
    assert r["part_investie"] == pytest.approx(0.3)
    assert all(c["rang"] == 0 for c in r["criteres"])


def test_concentration_sectorielle_elevee_l_emporte():
    # Exemple du cahier des charges : 90 % en technologie. 0,90 > 0,60 → rang 2 (élevé), même si la VaR est modérée (1,5 %).
    r = niveau_risque(_analyse(var=0.015, secteurs=[("Technologie", 0.9)], positions=[("AAPL", 0.45), ("MSFT", 0.45)]))
    assert r["niveau"] == "eleve"
    premier = r["criteres"][0]
    assert premier == {"critere": "concentration_secteur", "rang": 2, "valeur": pytest.approx(0.9), "libelle": "Technologie"}
    var = next(c for c in r["criteres"] if c["critere"] == "var")
    assert var["rang"] == 1                                    # 1 % < 1,5 % ≤ 2,5 %


def test_seuils_var_aux_bornes():
    # Bornes incluses dans le niveau inférieur : 1 % pile reste faible, 2,5 % pile reste modéré.
    assert next(c for c in niveau_risque(_analyse(var=0.01, secteurs=[("A", 0.1)], positions=[("X", 0.1)]))["criteres"] if c["critere"] == "var")["rang"] == 0
    assert next(c for c in niveau_risque(_analyse(var=0.025, secteurs=[("A", 0.1)], positions=[("X", 0.1)]))["criteres"] if c["critere"] == "var")["rang"] == 1
    assert next(c for c in niveau_risque(_analyse(var=0.0251, secteurs=[("A", 0.1)], positions=[("X", 0.1)]))["criteres"] if c["critere"] == "var")["rang"] == 2


def test_profil_depasse_et_baisse():
    r = niveau_risque(_analyse(var=0.002, secteurs=[("A", 0.1)], positions=[("X", 0.1)],
                               profil={"statut": "depasse", "perte_actuelle": 0.12, "perte_tolerance": 0.10}, dd=0.12))
    assert r["niveau"] == "eleve"
    assert {c["critere"]: c["rang"] for c in r["criteres"]}["profil"] == 2
    assert {c["critere"]: c["rang"] for c in r["criteres"]}["baisse"] == 1      # 12 % : entre 10 % et 20 %


def test_var_absente_ignoree():
    # Historique trop court : pas de VaR, le critère est simplement absent (jamais inventé).
    r = niveau_risque(_analyse(var=None, secteurs=[("A", 0.1)], positions=[("X", 0.1)]))
    assert "var" not in {c["critere"] for c in r["criteres"]}


def test_alertes_regles_distance_et_tri():
    regles = [
        {"id": 1, "symbole": "AAPL", "type": "stop_loss", "statut": "active", "niveau": 90.0},
        {"id": 2, "symbole": "AAPL", "type": "take_profit", "statut": "active", "niveau": 120.0},
        {"id": 3, "symbole": "MSFT", "type": "stop_loss", "statut": "active", "niveau": 196.0},
        {"id": 4, "symbole": "KO", "type": "take_profit", "statut": "declenchee", "niveau": None,
         "declenchee_le": "2021-04-20T15:48:00", "motif": "vendu 10"},
        {"id": 5, "symbole": "BA", "type": "stop_loss", "statut": "active", "niveau": 50.0},       # pas de prix : ignorée
        {"id": 6, "symbole": "PG", "type": "achat_complementaire", "statut": "active", "niveau": 160.0},
    ]
    r = alertes_regles(regles, {"AAPL": 100.0, "MSFT": 200.0, "PG": 150.0})
    # MSFT : |196 − 200| / 200 = 2 % → proche ; AAPL SL : 10 % ; AAPL TP : 20 %.
    assert [a["id"] for a in r["surveillance"]] == [3, 1, 2]
    assert r["surveillance"][0]["distance"] == pytest.approx(0.02) and r["surveillance"][0]["proche"] is True
    assert r["surveillance"][1]["distance"] == pytest.approx(0.10) and r["surveillance"][1]["proche"] is False
    assert [a["id"] for a in r["declenchees"]] == [4]


def test_alertes_prix_nul_ignore():
    r = alertes_regles([{"id": 1, "symbole": "X", "type": "stop_loss", "statut": "active", "niveau": 1.0}], {"X": 0.0})
    assert r["surveillance"] == []


def test_api_tableau_de_bord(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-02-10T17:00:00")
    vide = client.get("/api/v1/tableau-de-bord", headers=u.h)
    assert vide.status_code == 200
    assert vide.json()["niveau_risque"]["niveau"] == "aucun"
    aller(client, u, "2020-03-20T17:00:00")
    assert acheter(client, u, 200)["statut"] == "execute"
    r = client.put("/api/v1/regles", json={"symbole": "TST", "type": "stop_loss", "seuil_pct": 10}, headers=u.h)
    assert r.status_code == 200, r.text
    d = client.get("/api/v1/tableau-de-bord", headers=u.h).json()
    assert d["niveau_risque"]["niveau"] in ("faible", "modere", "eleve")
    assert len(d["alertes"]["surveillance"]) == 1 and d["alertes"]["surveillance"][0]["symbole"] == "TST"
    assert {"position", "marche", "secteur"} <= set(d["repartition_detail"])


def test_api_tableau_de_bord_exige_connexion(client):
    assert client.get("/api/v1/tableau-de-bord").status_code == 401
