"""Scénarios de crise (surcouche de prix), actualités datées et sentiment."""
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import func, select

from app.scenarios import sentiment, service, surcouche
from app.scenarios.modeles import ActualiteDb, ScenarioDb
from app.scenarios.surcouche import Parametres


# ------------------------------------------------------------------ mathématiques de la surcouche
def test_multiplicateur_choc_puis_recuperation():
    dates = pd.date_range("2020-01-01", periods=200)
    p = Parametres(date(2020, 1, 11), "tous", (), -0.30, 0.60, 100)
    m = surcouche.multiplicateur(dates, p)
    assert np.all(m[:10] == 1.0)                                  # avant la date de début : rien
    assert m[10] == pytest.approx(0.70)                           # le jour même : le choc complet
    assert m[10 + 50] == pytest.approx(1 - 0.30 * (1 - 0.60 * 0.5))
    assert m[10 + 100] == pytest.approx(1 - 0.30 * 0.40)          # 60 % du choc regagné
    assert m[-1] == pytest.approx(0.88)                           # puis stable


def test_choc_permanent_et_choc_positif():
    dates = pd.date_range("2020-01-01", periods=30)
    m = surcouche.multiplicateur(dates, Parametres(date(2020, 1, 5), "tous", (), 0.15, 0.0, 0))
    assert m[3] == 1.0 and np.all(m[4:] == pytest.approx(1.15))


@pytest.mark.parametrize("p, message", [
    (Parametres(date(2020, 2, 1), "tous", (), 0.0, 0, 0), "ne pas être nul"),
    (Parametres(date(2020, 2, 1), "tous", (), -0.99, 0, 0), "entre −95"),
    (Parametres(date(2020, 2, 1), "tous", (), -0.3, 1.5, 10), "part récupérée"),
    (Parametres(date(2020, 2, 1), "tous", (), -0.3, 0.5, 0), "au moins 1 jour"),
    (Parametres(date(2020, 2, 1), "classe", (), -0.3, 0, 0), "au moins un élément"),
    (Parametres(date(2020, 2, 1), "classe", ("bonds",), -0.3, 0, 0), "Classe inconnue"),
])
def test_verification_des_parametres(p, message):
    with pytest.raises(ValueError, match=message):
        surcouche.verifier(p)


def test_perimetres(univers_test):
    assert surcouche.symboles_concernes(univers_test, "classe", ["crypto"]) == {"CRY"}
    assert surcouche.symboles_concernes(univers_test, "tous", []) == {"TST", "CRY", "WTI", "VIDE"}
    assert surcouche.symboles_concernes(univers_test, "actifs", ["WTI"]) == {"WTI"}
    assert surcouche.symboles_concernes(univers_test, "secteur", ["Test"]) == {"TST", "CRY", "WTI", "VIDE"}


def test_l_indice_de_reference_suit_les_actions_et_le_vix_jamais():
    from datetime import time

    from app.marche.catalogue import Actif, Univers
    u = Univers(date(2020, 1, 1), date(2020, 12, 31), 0, {
        "AAA": Actif("AAA", "A", "action", "Tech", "semaine"),
        "^GSPC": Actif("^GSPC", "S&P", "indice", "Indice", "semaine", tradable=False),
        "^VIX": Actif("^VIX", "VIX", "indice", "Indice", "semaine", tradable=False),
        "OIL": Actif("OIL", "Pétrole", "matiere", "Énergie", "semaine"),
    })
    assert surcouche.symboles_concernes(u, "tous", []) == {"AAA", "OIL", "^GSPC"}
    assert surcouche.symboles_concernes(u, "secteur", ["Énergie"]) == {"OIL"}      # pas d'action : l'indice ne bouge pas


# ------------------------------------------------------------------ le magasin sert les prix modifiés
def test_magasin_multiplie_puis_restitue(magasin_test):
    avant = magasin_test.barre_du_jour("TST", date(2020, 2, 10))
    serie = magasin_test.series_origine()["TST"]
    m = pd.Series(0.5, index=serie.index[serie.index >= "2020-02-01"])
    magasin_test.appliquer_scenarios({"TST": m})
    apres = magasin_test.barre_du_jour("TST", date(2020, 2, 10))
    assert apres["close"] == pytest.approx(avant["close"] * 0.5) and apres["high"] >= apres["low"]
    assert apres["volume"] == avant["volume"]                                      # le volume n'est pas touché
    assert magasin_test.derniere_cloture_avant("TST", date(2020, 2, 11)) == pytest.approx(
        magasin_test.series_origine()["TST"].loc["2020-02-10", "close"] * 0.5)
    ancien = magasin_test.barre_du_jour("TST", date(2020, 1, 15))
    assert ancien["close"] == pytest.approx(serie.loc["2020-01-15", "close"])      # avant le début : intact
    magasin_test.appliquer_scenarios({})
    assert magasin_test.barre_du_jour("TST", date(2020, 2, 10))["close"] == pytest.approx(avant["close"])


# ------------------------------------------------------------------ API administrateur
def corps_scenario(**kw):
    base = {"nom": "Krach test", "date_debut": "2020-02-10", "portee_type": "actifs", "portee_valeurs": ["TST"],
            "choc_pct": -30, "recuperation_pct": 0, "duree_recuperation_jours": 0}
    base.update(kw)
    return base


def aller(client, u, instant):
    assert client.post("/api/v1/horloge/aller-a", json={"instant": instant}, headers=u.h).status_code == 200


def test_reserve_a_l_administrateur(client, utilisateur):
    u = utilisateur()
    for methode, chemin in [("get", "/api/v1/admin/scenarios"), ("get", "/api/v1/admin/scenarios/modeles"),
                            ("get", "/api/v1/admin/actualites"), ("post", "/api/v1/admin/actualites/reperes")]:
        assert getattr(client, methode)(chemin, headers=u.h).status_code == 403
    assert client.post("/api/v1/admin/scenarios", json=corps_scenario(), headers=u.h).status_code == 403
    assert client.get("/api/v1/admin/scenarios").status_code == 401


def test_creation_modifie_les_prix_vus_par_tous_et_peut_etre_retiree(client, utilisateur):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    aller(client, bob, "2020-02-20T17:00:00")
    avant = client.get("/api/v1/historique/TST?barres=60", headers=bob.h).json()
    r = client.post("/api/v1/admin/scenarios", json=corps_scenario(), headers=admin.h)
    assert r.status_code == 201, r.text
    assert r.json()["scenarios_appliques"] == 1 and "déjà dépassé" in r.json()["avertissement"]
    sid = r.json()["scenario"]["id"]
    apres = client.get("/api/v1/historique/TST?barres=60", headers=bob.h).json()
    par_date = lambda h: {b["date"]: b for b in h if not b["en_formation"]}
    a, b = par_date(avant), par_date(apres)
    assert b["2020-02-07"]["close"] == pytest.approx(a["2020-02-07"]["close"])             # veille du choc : intacte
    assert b["2020-02-10"]["open"] == pytest.approx(a["2020-02-10"]["open"] * 0.70)        # le choc apparaît à l'ouverture
    assert b["2020-02-19"]["close"] == pytest.approx(a["2020-02-19"]["close"] * 0.70)

    assert client.patch(f"/api/v1/admin/scenarios/{sid}", json={"actif": False}, headers=admin.h).json()["scenarios_appliques"] == 0
    retour = par_date(client.get("/api/v1/historique/TST?barres=60", headers=bob.h).json())
    assert retour["2020-02-19"]["close"] == pytest.approx(a["2020-02-19"]["close"])
    client.patch(f"/api/v1/admin/scenarios/{sid}", json={"actif": True}, headers=admin.h)
    assert client.delete(f"/api/v1/admin/scenarios/{sid}", headers=admin.h).status_code == 204
    assert client.delete(f"/api/v1/admin/scenarios/{sid}", headers=admin.h).status_code == 404
    final = par_date(client.get("/api/v1/historique/TST?barres=60", headers=bob.h).json())
    assert final["2020-02-19"]["close"] == pytest.approx(a["2020-02-19"]["close"])
    actions = [x["action"] for x in client.get("/api/v1/admin/audit", headers=admin.h).json()]
    assert {"admin.scenario.creer", "admin.scenario.desactiver", "admin.scenario.activer", "admin.scenario.supprimer"} <= set(actions)


def test_le_choc_declenche_le_stop_loss_d_un_utilisateur(client, utilisateur):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    aller(client, bob, "2020-02-05T17:00:00")
    assert client.post("/api/v1/ordres", json={"symbole": "TST", "sens": "achat", "quantite": 10, "type": "marche"}, headers=bob.h).status_code == 201
    assert client.put("/api/v1/regles", json={"symbole": "TST", "type": "stop_loss", "seuil_pct": 20, "part_pct": 100}, headers=bob.h).status_code == 200
    client.post("/api/v1/admin/scenarios", json=corps_scenario(choc_pct=-40), headers=admin.h)
    aller(client, bob, "2020-02-12T17:00:00")
    pos = client.get("/api/v1/portefeuille", headers=bob.h).json()["positions"]
    assert pos == [] or all(p["symbole"] != "TST" for p in pos)                           # la règle a vendu après le choc


@pytest.mark.parametrize("modif, texte", [
    ({"choc_pct": 0}, "nul"),
    ({"date_debut": "2019-01-01"}, "période rejouée"),
    ({"portee_valeurs": ["XXX"]}, "inconnu"),
    ({"portee_type": "secteur", "portee_valeurs": ["Poterie"]}, "Secteur inconnu"),
    ({"recuperation_pct": 50, "duree_recuperation_jours": 0}, "au moins 1 jour"),
    ({"portee_type": "actifs", "portee_valeurs": []}, "au moins un élément"),
])
def test_refus_des_scenarios_invalides(client, utilisateur, modif, texte):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    r = client.post("/api/v1/admin/scenarios", json=corps_scenario(**modif), headers=admin.h)
    assert r.status_code == 422 and texte in r.json()["detail"], r.text


def test_annonce_liee_au_scenario(client, utilisateur, base_test):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    r = client.post("/api/v1/admin/scenarios", json=corps_scenario(annonce="Krach soudain sur TST"), headers=admin.h)
    sid = r.json()["scenario"]["id"]
    with base_test.session() as s:
        a = s.scalar(select(ActualiteDb).where(ActualiteDb.scenario_id == sid))
        assert a.type_source == "scenario" and a.date == date(2020, 2, 10) and "fictive" in a.note_source
    client.patch(f"/api/v1/admin/scenarios/{sid}", json={"actif": False}, headers=admin.h)
    with base_test.session() as s:
        assert s.scalar(select(ActualiteDb).where(ActualiteDb.scenario_id == sid)).actif is False
    client.delete(f"/api/v1/admin/scenarios/{sid}", headers=admin.h)
    with base_test.session() as s:
        assert s.scalar(select(func.count()).select_from(ActualiteDb).where(ActualiteDb.scenario_id == sid)) == 0


# ------------------------------------------------------------------ actualités
def test_actualites_visibles_a_partir_de_8h_le_jour_de_parution(client, utilisateur):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    r = client.post("/api/v1/admin/actualites", json={"date": "2020-02-10", "titre": "Résultats solides, le titre bondit", "texte": "", "symboles": ["TST"]}, headers=admin.h)
    assert r.status_code == 201 and r.json()["type_source"] == "fictif"
    aller(client, bob, "2020-02-10T07:59:00")
    assert client.get("/api/v1/actualites", headers=bob.h).json()["actualites"] == []     # avant 08:00 : invisible
    aller(client, bob, "2020-02-10T08:00:00")
    liste = client.get("/api/v1/actualites", headers=bob.h).json()["actualites"]
    assert len(liste) == 1 and liste[0]["sentiment"]["etiquette"] == "positif"
    assert liste[0]["impact"][0]["rendement_1j"] is None                                  # la séance du jour n'est pas terminée
    aller(client, bob, "2020-01-15T12:00:00")                                             # retour en arrière : plus visible
    assert client.get("/api/v1/actualites", headers=bob.h).json()["actualites"] == []


def test_impact_sans_fuite_du_futur(client, utilisateur, magasin_test):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    client.post("/api/v1/admin/actualites", json={"date": "2020-02-10", "titre": "Annonce", "symboles": ["TST"]}, headers=admin.h)
    serie = magasin_test.series_origine()["TST"]["close"]
    veille, jour = serie.loc["2020-02-07"], serie.loc["2020-02-10"]
    cinquieme = serie.iloc[serie.index.get_loc(pd.Timestamp("2020-02-10")) + 4]
    aller(client, bob, "2020-02-11T10:00:00")                                             # séance du 10 terminée, pas celle du 14
    i = client.get("/api/v1/actualites", headers=bob.h).json()["actualites"][0]["impact"][0]
    assert i["rendement_1j"] == pytest.approx(jour / veille - 1) and i["rendement_5j"] is None
    aller(client, bob, "2020-02-20T10:00:00")
    i = client.get("/api/v1/actualites", headers=bob.h).json()["actualites"][0]["impact"][0]
    assert i["rendement_5j"] == pytest.approx(cinquieme / veille - 1)


def test_filtre_par_actif_et_nouvelle_generale(client, utilisateur):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    for titre, symboles in [("Spécifique TST", ["TST"]), ("Spécifique CRY", ["CRY"]), ("Générale", [])]:
        client.post("/api/v1/admin/actualites", json={"date": "2020-02-03", "titre": titre, "symboles": symboles}, headers=admin.h)
    aller(client, bob, "2020-02-20T10:00:00")
    titres = lambda q: sorted(a["titre"] for a in client.get("/api/v1/actualites" + q, headers=bob.h).json()["actualites"])
    assert titres("") == ["Générale", "Spécifique CRY", "Spécifique TST"]
    assert titres("?symbole=TST") == ["Générale", "Spécifique TST"]
    assert client.get("/api/v1/actualites?symbole=NOPE", headers=bob.h).status_code == 404


def test_desactivation_et_suppression_d_une_actualite(client, utilisateur):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    nid = client.post("/api/v1/admin/actualites", json={"date": "2020-02-03", "titre": "À retirer"}, headers=admin.h).json()["id"]
    aller(client, bob, "2020-02-20T10:00:00")
    assert len(client.get("/api/v1/actualites", headers=bob.h).json()["actualites"]) == 1
    client.patch(f"/api/v1/admin/actualites/{nid}", json={"actif": False}, headers=admin.h)
    assert client.get("/api/v1/actualites", headers=bob.h).json()["actualites"] == []
    assert client.delete(f"/api/v1/admin/actualites/{nid}", headers=admin.h).status_code == 204
    assert client.delete(f"/api/v1/admin/actualites/{nid}", headers=admin.h).status_code == 404
    assert client.post("/api/v1/admin/actualites", json={"date": "2019-01-01", "titre": "Hors période"}, headers=admin.h).status_code == 422
    assert client.post("/api/v1/admin/actualites", json={"date": "2020-02-03", "titre": "Actif inconnu", "symboles": ["XXX"]}, headers=admin.h).status_code == 422


def test_reperes_historiques_idempotents(client, utilisateur, base_test):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    n = client.post("/api/v1/admin/actualites/reperes", headers=admin.h).json()["ajoutees"]
    assert n >= 20
    assert client.post("/api/v1/admin/actualites/reperes", headers=admin.h).json()["ajoutees"] == 0
    with base_test.session() as s:
        types = set(s.scalars(select(ActualiteDb.type_source)))
        assert types == {"historique"}
        assert all("à vérifier" in a.note_source for a in s.scalars(select(ActualiteDb)))


def test_etude_sentiment_et_ses_limites(client, utilisateur):
    admin = utilisateur("admin@example.com", "Chef", role="admin")
    bob = utilisateur("bob@example.com", "Bob")
    jours = pd.bdate_range("2020-01-06", periods=8)
    for i, j in enumerate(jours):
        titre = "Le titre bondit après des résultats solides" if i % 2 == 0 else "Le titre chute, craintes de faillite"
        client.post("/api/v1/admin/actualites", json={"date": j.date().isoformat(), "titre": titre, "symboles": ["TST"]}, headers=admin.h)
    aller(client, bob, "2020-03-10T10:00:00")
    e = client.get("/api/v1/actualites/etude", headers=bob.h).json()
    assert e["nb_actualites"] == 8 and e["nb_non_neutres"] >= 6 and 0 <= e["concordance"] <= 1
    assert e["correlation"] is None or -1 <= e["correlation"] <= 1
    assert "trop petit" in e["avertissement"]                                             # 8 actualités : pas de conclusion


# ------------------------------------------------------------------ sentiment
@pytest.mark.parametrize("texte, attendu", [
    ("Les marchés plongent après la faillite d'une grande banque", "negatif"),
    ("Strong earnings beat expectations, shares surge", "positif"),
    ("Le bénéfice n'est pas en hausse", "neutre"),
    ("Apple presents a new phone", "neutre"),
    ("Les indices s'effondrent, la panique gagne les marchés", "negatif"),
    ("Record de bénéfices et croissance solide", "positif"),
])
def test_sentiment(texte, attendu):
    assert sentiment.analyser(texte).etiquette == attendu


def test_sentiment_negation_et_explication():
    s = sentiment.analyser("Les ventes ne montent pas")
    assert "pas montent" in s.mots_negatifs and s.score < 0
    assert -1 <= sentiment.analyser("hausse " * 20).score <= 1
    assert sentiment.analyser("").etiquette == "neutre"


def test_une_hausse_de_taux_n_est_pas_comptee_comme_une_bonne_nouvelle():
    assert sentiment.analyser("La Fed relève ses taux").etiquette == "neutre"


# ------------------------------------------------------------------ démarrage
def test_initialisation_applique_les_scenarios_et_seme_les_reperes(ctx_test, base_test):
    from app.contexte import initialiser_scenarios
    with base_test.session() as s:
        s.add(ScenarioDb(nom="Persisté", date_debut=date(2020, 2, 10), portee_type="actifs", portee_valeurs=["TST"], choc=-0.5,
                         recuperation=0.0, duree_recuperation_jours=0, actif=True))
        s.commit()
    avant = ctx_test.magasin.series_origine()["TST"].loc["2020-02-12", "close"]
    initialiser_scenarios(ctx_test)
    assert ctx_test.magasin.barre_du_jour("TST", date(2020, 2, 12))["close"] == pytest.approx(avant * 0.5)
    with base_test.session() as s:
        assert s.scalar(select(func.count()).select_from(ActualiteDb)) >= 20
    initialiser_scenarios(ctx_test)                                       # idempotent
    with base_test.session() as s:
        assert s.scalar(select(func.count()).select_from(ActualiteDb).where(ActualiteDb.titre.like("La Russie%"))) == 1
