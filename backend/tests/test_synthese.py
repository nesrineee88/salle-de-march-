"""Synthèse du tableau de bord : niveau de risque global et alertes des règles stop-loss / take-profit."""
import pytest

from app.risque.synthese import alertes_regles, niveau_risque

from .test_portefeuille_api import acheter, aller


def _analyse(var=None, secteurs=None, positions=None, profil=None, cvar=None, vol=None, dd=None):
    """Analyse minimale au format de risque.analyse.analyser (parts exprimées sur la valeur totale)."""
    secteurs = secteurs or []
    positions = positions or []
    risque = None
    if var is not None:
        risque = {"var": var, "jours": 250, "cvar": var * 1.4 if cvar is None else cvar,
                  "volatilite_annuelle_seances": var * 10 if vol is None else vol, "drawdown_poids": var * 5 if dd is None else dd}
    return {
        "risque": risque,
        "repartition": {
            "secteur": [{"libelle": s, "part": p} for s, p in secteurs] + [{"libelle": "Liquidités", "part": 1 - sum(p for _, p in secteurs)}],
            "position": [{"libelle": s, "part": p} for s, p in positions],
        },
        "profil": profil or {"statut": "profil_absent"},
    }


def _famille(r, cle):
    return next(f for f in r["familles"] if f["cle"] == cle)


def test_portefeuille_sans_position_niveau_aucun():
    r = niveau_risque(_analyse())
    assert r["niveau"] == "aucun" and r["familles"] == [] and r["part_investie"] == 0.0 and r["score"] is None


def test_portefeuille_faible_risque():
    # 30 % investis, répartis : VaR 0,4 %, position max 10 %, secteur max 20 %.
    r = niveau_risque(_analyse(var=0.004, secteurs=[("Santé", 0.2), ("Énergie", 0.1)], positions=[("JNJ", 0.1), ("PFE", 0.1), ("XOM", 0.1)]))
    assert r["niveau"] == "faible" and r["part_investie"] == pytest.approx(0.3)
    assert all(f["rang"] == 0 for f in r["familles"])
    assert r["score"] == pytest.approx(sum(f["note"] * f["poids"] for f in r["familles"]))


def test_le_plancher_empeche_la_moyenne_de_masquer_une_concentration():
    # 100 % sur une action calme : la moyenne seule dirait modéré ou moins.
    r = niveau_risque(_analyse(var=0.008, secteurs=[("Consommation", 1.0)], positions=[("KO", 1.0)]))
    assert r["niveau_pondere"] != "eleve" and r["niveau"] == "eleve"
    assert r["plancher"] == {"niveau": "eleve", "cle": "concentration", "note": pytest.approx(100), "releve": True}


def test_concentration_sectorielle_prise_en_compte():
    # 90 % en technologie, deux lignes de 45 % : c'est le secteur qui porte la note.
    r = niveau_risque(_analyse(var=0.015, secteurs=[("Technologie", 0.9)], positions=[("AAPL", 0.45), ("MSFT", 0.45)]))
    c = _famille(r, "concentration")
    assert (c["nature"], c["libelle"], c["rang"]) == ("secteur", "Technologie", 2) and r["niveau"] == "eleve"


def test_seuils_var_aux_bornes():
    # Bornes incluses dans le niveau inférieur : 1 % pile reste faible, 2,5 % pile reste modéré.
    for var, rang in ((0.01, 0), (0.025, 1), (0.0251, 2)):
        r = niveau_risque(_analyse(var=var, secteurs=[("A", 0.1)], positions=[("X", 0.1)]))
        assert _famille(r, "var")["rang"] == rang


def test_le_profil_est_une_alerte_a_part():
    r = niveau_risque(_analyse(var=0.002, secteurs=[("A", 0.1)], positions=[("X", 0.1)],
                               profil={"statut": "depasse", "perte_actuelle": 0.12, "perte_tolerance": 0.10}))
    assert r["niveau"] == "faible"
    assert r["profil"] == {"statut": "depasse", "perte_actuelle": 0.12, "tolerance": 0.10}


def test_historique_trop_court_calcul_incomplet():
    # Moins de 30 séances : rien n'est inventé, seule la concentration est donnée.
    r = niveau_risque(_analyse(var=None, secteurs=[("A", 0.9)], positions=[("X", 0.9)]))
    assert r["niveau"] == "incomplet" and r["calcul_complet"] is False and r["score"] is None
    assert _famille(r, "var")["note"] is None and r["plancher"]["niveau"] == "eleve"


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
    assert d["niveau_risque"]["niveau"] in ("faible", "modere", "eleve") and len(d["niveau_risque"]["familles"]) == 5
    assert len(d["alertes"]["surveillance"]) == 1 and d["alertes"]["surveillance"][0]["symbole"] == "TST"
    assert {"position", "marche", "secteur"} <= set(d["repartition_detail"])


def test_api_tableau_de_bord_exige_connexion(client):
    assert client.get("/api/v1/tableau-de-bord").status_code == 401
