"""Assistant XAI : il comprend, il calcule comme le reste du projet, il ne voit pas le futur, il ne modifie rien."""
import json

import pandas as pd
import pytest

from app import config
from app.jeu import service as jeu
from app.jeu.modeles import PartieJeu
from app.marche.catalogue import charger_univers
from app.trading import persistance
from app.xai import reponses
from app.xai.comprendre import comprendre
from app.xai.routes import SUGGESTIONS

PLAN = {"perte_max": 15, "reaction": "tenir"}


@pytest.fixture(scope="module")
def univers():
    return charger_univers(config.UNIVERS_YAML)


def demander(client, u, question, symbole=None):
    r = client.post("/api/v1/xai/question", json={"question": question, "symbole": symbole}, headers=u.h)
    assert r.status_code == 200, r.text
    return r.json()


def investi(client, u):
    assert client.post("/api/v1/horloge/aller-a", json={"instant": "2020-02-28T17:00:00"}, headers=u.h).status_code == 200
    achat = {"symbole": "TST", "sens": "achat", "quantite": 12, "type": "marche"}
    assert client.post("/api/v1/ordres", json=achat, headers=u.h).json()["statut"] == "execute"


@pytest.mark.parametrize("question, intention, symbole", [
    ("Pourquoi ce niveau de risque ?", "risque", None),
    ("combien puis-je perdre", "risque", None),
    ("bonjour, quel est mon risque ?", "risque", None),
    ("c'est quoi mon risque", "risque", None),
    ("Pourquoi ai-je ce résultat ?", "resultat", None),
    ("combien j'ai gagné", "resultat", None),
    ("Comment va mon portefeuille", "portefeuille", None),
    ("combien ai-je de liquidités", "portefeuille", None),
    ("suis-je meilleur que le S&P 500 ?", "indice", None),
    ("Est-ce que Bitcoin va monter demain ?", "prediction", "BTC-USD"),
    ("le marché va-t-il chuter ? il va baisser", "prediction", None),
    ("vais-je perdre", "prediction", None),
    ("dois-je acheter Tesla ?", "conseil", "TSLA"),
    ("que me conseilles-tu", "conseil", None),
    ("Comment acheter Apple ?", "ordre", None),
    ("parle-moi d'Apple", "actif", "AAPL"),
    ("pourquoi je perds sur NVDA", "actif", "NVDA"),
    ("analyse de l’or", "actif", "GC=F"),
    ("et le maïs ?", "actif", "ZC=F"),
    ("dis-moi mon résultat", "resultat", None),
    ("mon argent disponible", "portefeuille", None),
    ("mais pourquoi je perds", "resultat", None),
    ("C’est quoi le RSI ?", "definition", None),
    ("c'est quoi un stop", "definition", None),
    ("explique le ratio de sharpe", "definition", None),
    ("c'est quoi la mourabaha", "definition", None),
    ("Quelle banque est la plus fragile ?", "stress", None),
    ("parle-moi de Bank of America", "actif", "BAC"),
    ("Comment est calculée la prime ?", "assurance", None),
    ("explique ma note au jeu", "jeu", None),
    ("note de risque", "risque", None),
    ("quelle date on est ?", "temps", None),
    ("d'où viennent les données ?", "sources", None),
    ("es-tu ChatGPT ?", "identite", None),
    ("par quelle leçon débuter", "formation", None),
    ("fondamentale et PER", "analyses", None),
    ("que dit le modèle pour Apple ?", "modele", "AAPL"),
    ("bonjour", "accueil", None),
    ("recette de couscous", "inconnu", None),
])
def test_comprend(univers, question, intention, symbole):
    lu = comprendre(question, univers)
    assert lu.intention == intention
    if symbole or intention in ("actif", "resultat", "portefeuille"):
        assert lu.symbole == symbole


@pytest.mark.parametrize("question, choc, classe, symbole", [
    ("Et si tout baisse de 10 % ?", -0.10, None, None),
    ("si les actions chutent de 12,5%", -0.125, "action", None),
    ("et si les cryptos montent de 20 %", 0.20, "crypto", None),
    ("si tesla perd 30 pourcent", -0.30, None, "TSLA"),
])
def test_comprend_un_choc(univers, question, choc, classe, symbole):
    lu = comprendre(question, univers)
    assert lu.intention == "choc" and lu.choc == pytest.approx(choc) and lu.classe == classe and lu.symbole == symbole


def test_cet_actif_vient_de_la_page(univers):
    assert comprendre("Explique-moi cet actif", univers, "MSFT").symbole == "MSFT"
    assert comprendre("Explique-moi cet actif", univers, "INCONNU").symbole is None


@pytest.mark.parametrize("page", sorted(SUGGESTIONS))
def test_chaque_suggestion_est_comprise(univers, page):
    for q in SUGGESTIONS[page]:
        assert comprendre(q, univers, "AAPL").intention not in ("inconnu", "accueil"), q


def test_chaque_intention_a_sa_reponse(univers):
    phrases = [q for qs in SUGGESTIONS.values() for q in qs]
    assert {comprendre(q, univers, "AAPL").intention for q in phrases} <= set(reponses.REPONSES) | {"modele"}


def test_la_ponctuation_reste_lisible():
    t = reponses.reponse("Prime : 12 % ? « oui » ; fin !", reponses.preuve("m"))["texte"]
    assert t == "Prime : 12 % ? « oui » ; fin !"
    assert not [c for c in t if ord(c) < 32]


def test_aucune_reponse_ne_contient_de_caractere_de_controle(client, utilisateur):
    u = utilisateur()
    for q in ("risque", "résultat", "quelle banque est fragile", "es-tu ChatGPT", "c'est quoi le RSI", "TST"):
        r = demander(client, u, q)
        assert not [c for c in r["texte"] + r["preuve"]["methode"] if ord(c) < 32], q


def test_connexion_et_question_obligatoires(client, utilisateur):
    assert client.post("/api/v1/xai/question", json={"question": "risque"}).status_code == 401
    assert client.get("/api/v1/xai/suggestions").status_code == 401
    u = utilisateur()
    for q in ("", "   ", "x" * 301):
        assert client.post("/api/v1/xai/question", json={"question": q}, headers=u.h).status_code == 422


@pytest.mark.parametrize("question", [
    "risque", "résultat", "mon portefeuille", "indice", "et si tout baisse de 10 %", "explique ma note au jeu", "quelle banque est fragile",
    "quelle date on est", "d'où viennent les données", "par quelle leçon débuter", "prime d'assurance", "TST", "VIDE",
    "es-tu ChatGPT", "bonjour", "fondamentale", "recette de couscous",
])
def test_repond_meme_sur_un_compte_vierge(client, utilisateur, question):
    r = demander(client, utilisateur(), question)
    assert r["texte"] and r["preuve"]["methode"] and r["preuve"]["limite"] and r["instant"]


def test_le_resultat_est_exactement_la_somme_des_barres(client, utilisateur):
    u = utilisateur()
    investi(client, u)
    r = demander(client, u, "Pourquoi ai-je ce résultat ?")
    pf = client.get("/api/v1/portefeuille", headers=u.h).json()
    assert sum(b["valeur"] for b in r["preuve"]["barres"]) == pytest.approx(pf["pnl_total"], abs=0.01)
    assert not any(b["nom"] == "Autres écarts" for b in r["preuve"]["barres"])


def test_le_risque_est_celui_du_dashboard(client, utilisateur):
    u = utilisateur()
    investi(client, u)
    n = client.get("/api/v1/tableau-de-bord", headers=u.h).json()["niveau_risque"]
    r = demander(client, u, "Pourquoi ce niveau de risque ?")
    if n["score"] is None:
        assert "incomplet" in r["preuve"]["methode"]
    else:
        assert sum(b["valeur"] for b in r["preuve"]["barres"]) == pytest.approx(n["score"])


def test_le_choc_est_la_valeur_fois_le_choc(client, utilisateur):
    u = utilisateur()
    investi(client, u)
    pf = client.get("/api/v1/portefeuille", headers=u.h).json()
    r = demander(client, u, "et si tout baisse de 10 % ?")
    assert sum(b["valeur"] for b in r["preuve"]["barres"]) == pytest.approx(-0.10 * pf["valeur_positions"])


def test_l_indice_suit_le_debut_du_portefeuille(client, utilisateur):
    u = utilisateur()
    investi(client, u)
    assert demander(client, u, "suis-je meilleur que l'indice ?")["texte"]


def test_rien_apres_la_date_simulee(client, utilisateur, monkeypatch):
    u = utilisateur()
    investi(client, u)
    vu = []
    from app.marche.moteur import MoteurMarche
    from app.marche.stockage import Magasin

    barres, cotation = Magasin.barres_terminees, MoteurMarche.cotation
    monkeypatch.setattr(Magasin, "barres_terminees", lambda self, s, avant, n=None: vu.append(str(avant)) or barres(self, s, avant, n))
    monkeypatch.setattr(MoteurMarche, "cotation", lambda self, s, t, *a, **k: vu.append(t.date().isoformat()) or cotation(self, s, t, *a, **k))
    for q in ("TST", "risque", "résultat", "indice", "et si tout baisse de 5 %"):
        demander(client, u, q)
    assert vu and max(vu) <= "2020-02-28"


def test_lecture_seule(client, utilisateur, base_test):
    u = utilisateur()
    investi(client, u)
    client.post("/api/v1/horloge/pause", headers=u.h)
    client.get("/api/v1/portefeuille", headers=u.h)
    with base_test.session() as s:
        avant = persistance.charger(s, u.id)
    for q in ("achète 100 TST", "vends tout", "reviens en 2019", "risque", "résultat", "dois-je vendre ?"):
        demander(client, u, q)
    with base_test.session() as s:
        assert persistance.charger(s, u.id) == avant


def test_la_note_du_jeu_est_decomposee(client, utilisateur, base_test):
    u = utilisateur()
    with base_test.session() as s:
        p = jeu.creer(s, u.id, "mystere", None, "acteur", PLAN)
        b = jeu._bobine(p.film)
        titre, sujet = b.film.titre, b.film.sujet
        p = jeu._ecrire(s, p, p.version, seance=b.dernier - 1, choix=[{"jour": j, "acte": "tenir"} for j in b.arrets])
        p = jeu.avancer(s, p, p.version)
        note = p.note
        g = jeu.vue(p)["generique"]
    r = demander(client, u, "explique ma note au jeu")
    assert f"{note}/100" in r["texte"]
    if not g["plafonnee"]:
        assert round(sum(x["valeur"] for x in r["preuve"]["barres"])) == note
    brut = json.dumps(r, ensure_ascii=False)
    assert titre not in brut and sujet not in brut            # mystère pas encore deviné


def test_une_partie_en_cours_ne_fuit_pas(client, utilisateur, base_test):
    u = utilisateur()
    with base_test.session() as s:
        p = jeu.creer(s, u.id, "mystere", None, "acteur", PLAN)
        titre = s.get(PartieJeu, p.id) and jeu._bobine(p.film).film.titre
    assert titre not in json.dumps(demander(client, u, "explique le film du jeu"), ensure_ascii=False)


def test_le_modele_garde_la_permission_de_la_page_ia(client, utilisateur):
    r = demander(client, utilisateur(), "que dit le modèle pour TST ?")
    assert r["intention"] == "modele" and "réservé" in r["texte"]


def test_les_contributions_du_modele_redonnent_sa_probabilite():
    import math

    import numpy as np

    from app.ia import analyses

    pytest.importorskip("sklearn")
    rng = np.random.default_rng(3)
    c = 100 + np.cumsum(rng.normal(0.02, 1, 420))
    c = np.maximum(c, 5)
    df = pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": rng.integers(1000, 9000, 420).astype(float)},
                      index=pd.bdate_range("2020-01-01", periods=420))
    brut = analyses.predire(df)
    r = reponses.expliquer_modele("Test", brut)
    logit = brut["intercept"] + sum(b["valeur"] for b in r["preuve"]["barres"])
    assert 1 / (1 + math.exp(-logit)) == pytest.approx(brut["proba_hausse"])
