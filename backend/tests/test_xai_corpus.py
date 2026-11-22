"""Assistant XAI : corpus de vraies questions d'élèves (fautes, abréviations, anglais), pages, suites de conversation, sommes exactes,
lecture seule, rien après la date simulée, séance mystère, temps de réponse."""
import json
import time

import pytest

from app import config
from app.jeu import service as jeu
from app.marche.catalogue import charger_univers
from app.trading import persistance
from app.xai import couverture
from app.xai.comprendre import GLOSSAIRE, comprendre
from app.xai.routes import SUGGESTIONS

PLAN = {"perte_max": 15, "reaction": "tenir"}

# (question, intention attendue, actif attendu ou None, banque attendue ou None)
CORPUS = [
    # risque
    ("c quoi mon risque", "risque", None, None), ("pk mon risque est eleve", "risque", None, None), ("mn risk", "risque", None, None),
    ("jsuis trop risqué ?", "risque", None, None), ("combien je peux perdre au pire", "risque", None, None),
    ("ma var c combien", "risque", None, None), ("pire baisse de mon portefeuil", "risque", None, None),
    ("est ce que je suis trop concentré", "risque", None, None), ("suis-je assez diversifié ?", "risque", None, None),
    ("why is my risk high", "risque", None, None), ("niveau de risque stp", "risque", None, None), ("ma volatilité ?", "risque", None, None),
    # résultat
    ("pq je perds", "resultat", None, None), ("combien jai gagné", "resultat", None, None), ("mon rendemant", "resultat", None, None),
    ("ma perf", "resultat", None, None), ("pourquoi je suis dans le rouge", "resultat", None, None),
    ("c quoi ma pire position", "resultat", None, None), ("jai perdu combien depuis le debut", "resultat", None, None),
    ("mes gains", "resultat", None, None), ("pourquoi ca baisse", "resultat", None, None),
    # portefeuille
    ("cb de cash il me reste", "portefeuille", None, None), ("mes positions", "portefeuille", None, None),
    ("quelle position pèse le plus", "portefeuille", None, None), ("ma plus grosse position", "portefeuille", None, None),
    ("mon solde", "portefeuille", None, None), ("répartition de mon portefeuille", "portefeuille", None, None),
    ("combien ai-je de liquidités", "portefeuille", None, None), ("valeur totale ?", "portefeuille", None, None),
    # tableau de bord
    ("résume mon tableau de bord", "dashboard", None, None), ("mon résultat du jour", "dashboard", None, None),
    ("bilan de ma journée", "dashboard", None, None), ("resume moi tout", "dashboard", None, None),
    ("dashboard stp", "dashboard", None, None), ("vue d'ensemble", "dashboard", None, None), ("ca donne quoi aujourd'hui", "dashboard", None, None),
    # indice
    ("je bats le marché ?", "indice", None, None), ("suis je meilleur que le sp500", "indice", None, None),
    ("compare moi au nasdaq", "indice", None, None), ("mieux que l'indice ou pas", "indice", None, None),
    # actifs
    ("explique apple", "actif", "AAPL", None), ("parle moi de tesla", "actif", "TSLA", None), ("et nvidia alors", "actif", "NVDA", None),
    ("le bitcoin", "actif", "BTC-USD", None), ("info sur l'or", "actif", "GC=F", None), ("microsoft ?", "actif", "MSFT", None),
    ("ethereum ca vaut combien", "actif", "ETH-USD", None), ("le petrole", "actif", "CL=F", None), ("coca cola", "actif", "KO", None),
    ("AMZN", "actif", "AMZN", None), ("analyse google", "actif", "GOOGL", None), ("boeing ca donne quoi", "actif", "BA", None),
    # comparer
    ("compare apple et microsoft", "comparer", "AAPL", None), ("tesla vs nvidia", "comparer", "TSLA", None),
    ("bitcoin ou ethereum lequel est plus risqué", "comparer", "BTC-USD", None), ("difference entre l'or et le bitcoin", "comparer", "GC=F", None),
    ("apple et amazon compare", "comparer", "AAPL", None), ("compare coca cola et pfizer", "comparer", "KO", None),
    # chocs
    ("et si tout baisse de 10%", "choc", None, None), ("si apple chute de 20 %", "choc", "AAPL", None),
    ("si les cryptos perdent 30%", "choc", None, None), ("krach de 15% sur les actions", "choc", None, None),
    ("et si le bitcoin monte de 50 %", "choc", "BTC-USD", None), ("impact si l'or baisse de 5 pourcent", "choc", "GC=F", None),
    # prédiction et conseil
    ("ca va monter demain ?", "prediction", None, None), ("bitcoin va exploser ?", "prediction", "BTC-USD", None),
    ("tesla va baisser la semaine prochaine", "prediction", "TSLA", None), ("tu prévois quoi pour apple", "prediction", "AAPL", None),
    ("le marché va s'effondrer ?", "prediction", None, None), ("je vais perdre ?", "prediction", None, None),
    ("dois je vendre tesla", "conseil", "TSLA", None), ("quelle action acheter", "conseil", None, None),
    ("tu acheterais nvidia ?", "conseil", "NVDA", None), ("je vends ou pas", "conseil", None, None), ("meilleur placement ?", "conseil", None, None),
    ("ou investir mon argent", "conseil", None, None),
    # définitions (glossaire)
    ("c quoi le rsi", "definition", None, None), ("kesk le macd", "definition", None, None), ("c koi une bougie", "definition", None, None),
    ("c'est quoi un gap", "definition", None, None), ("definition de la volatilité", "definition", None, None),
    ("c quoi le sharpe", "definition", None, None), ("cest quoi la var", "definition", None, None), ("c quoi la cvar", "definition", None, None),
    ("ca veut dire quoi drawdown", "definition", None, None), ("c quoi le hhi", "definition", None, None),
    ("c quoi un stop suiveur", "definition", None, None), ("c'est quoi un ordre limite", "definition", None, None),
    ("c quoi le spread", "definition", None, None), ("c quoi le slippage", "definition", None, None),
    ("c'est quoi les bandes de bollinger", "definition", None, None), ("c quoi une moyenne mobile", "definition", None, None),
    ("c quoi un support", "definition", None, None), ("c'est quoi fibonacci", "definition", None, None),
    ("what is a backtest", "definition", None, None), ("c quoi le surajustement", "definition", None, None),
    ("c'est quoi le cet1", "definition", None, None), ("c quoi les rwa", "definition", None, None), ("c quoi la lgd", "definition", None, None),
    ("c'est quoi la pd", "definition", None, None), ("c quoi vasicek", "definition", None, None), ("c quoi un sukuk", "definition", None, None),
    ("c quoi la mourabaha", "definition", None, None), ("c quoi le salam", "definition", None, None), ("c quoi istisna", "definition", None, None),
    ("c'est quoi les psia", "definition", None, None), ("c quoi un put", "definition", None, None), ("c quoi black scholes", "definition", None, None),
    ("c quoi la prime pure", "definition", None, None), ("c'est quoi une franchise", "definition", None, None),
    ("c quoi chain ladder", "definition", None, None), ("c quoi gdelt", "definition", None, None),
    ("c quoi le ton d'une actualité", "definition", None, None), ("c quoi le vix", "definition", None, None),
    ("c quoi le beta", "definition", None, None), ("c quoi le rendement total", "definition", None, None),
    ("c quoi un dividende", "definition", None, None), ("c'est quoi le coussin de conservation", "definition", None, None),
    ("c quoi le pire cas", "definition", None, None), ("c quoi le q-learning", "definition", None, None),
    ("c quoi une ia explicable", "definition", None, None),
    # stress test
    ("quelle banque est la plus fragile", "stress", None, None), ("pk aljazira est la plus fragile", "stress", None, "aljazira"),
    ("explique al rajhi", "stress", None, "alrajhi"), ("et snb ?", "stress", None, "snb"), ("banques islamiques vs conventionnelles", "stress", None, None),
    ("le pire cas des banques", "stress", None, None), ("riyad bank ça tient ?", "stress", None, "riyad"),
    ("saudi fransi est solide ?", "stress", None, "bsf"), ("stress test resultat", "stress", None, None),
    ("capital a reconstituer", "stress", None, None),
    # crédit
    ("c quoi le z-score", "credit", None, None), ("explique altman", "credit", None, None), ("risque de faillite d'une entreprise", "credit", None, None),
    # actualités
    ("que dit la presse sur tesla", "actualites", "TSLA", None), ("les news sur apple", "actualites", "AAPL", None),
    ("on dit quoi sur le bitcoin dans les journaux", "actualites", "BTC-USD", None), ("sentiment des actualités", "actualites", None, None),
    ("dernières nouvelles", "actualites", None, None),
    # ordres et règles
    ("mes ordres en attente", "ordres", None, None), ("pk mon stop a vendu plus bas", "ordres", None, None),
    ("mes regles actives", "ordres", None, None), ("pourquoi ma vente s'est faite plus bas", "ordres", None, None),
    ("comment acheter du bitcoin", "ordre", None, None), ("comment poser un stop", "ordre", None, None), ("comment annuler un ordre", "ordre", None, None),
    # assurance
    ("combien coûte de me protéger", "assurance", None, None), ("comment est calculée la prime", "assurance", None, None),
    ("proteger mon portefeuille", "assurance", None, None), ("pourquoi pas d'assureur", "assurance", None, None),
    # jeu
    ("explique ma note", "jeu", None, None), ("qu'aurait donné un autre choix au jeu", "jeu", None, None),
    ("si j'avais tenu au jeu", "jeu", None, None), ("c quoi la séance mystère", "jeu", None, None), ("montage alternatif", "jeu", None, None),
    # formation
    ("par quoi commencer", "formation", None, None), ("explique la leçon sur le risque", "formation", None, None),
    ("je debute", "formation", None, None), ("y a des quiz ?", "formation", None, None),
    # temps et sources
    ("on est quel jour", "temps", None, None), ("pourquoi je peux pas reculer", "temps", None, None), ("revenir en arriere", "temps", None, None),
    ("d'ou viennent les donnees", "sources", None, None), ("c'est des vrais prix ?", "sources", None, None),
    # page, identité, accueil, inconnu
    ("explique cette page", "page", None, None), ("a quoi sert cette page", "page", None, None), ("je fais quoi ici", "page", None, None),
    ("t'es qui", "identite", None, None), ("tu es chatgpt ?", "identite", None, None), ("comment tu marches", "identite", None, None),
    ("salut", "accueil", None, None), ("tu sers a quoi", "accueil", None, None), ("hey", "accueil", None, None),
    ("recette de crêpes", "inconnu", None, None), ("quel temps fait-il à tunis", "inconnu", None, None), ("asdfgh", "inconnu", None, None),
]


@pytest.fixture(scope="module")
def univers():
    return list(charger_univers(config.UNIVERS_YAML))


def test_le_corpus_compte_au_moins_150_questions():
    assert len(CORPUS) >= 150 and len({q for q, *_ in CORPUS}) == len(CORPUS)


@pytest.mark.parametrize("question, intention, symbole, banque", CORPUS)
def test_corpus(univers, question, intention, symbole, banque):
    lu = comprendre(question, univers)
    assert lu.intention == intention, (question, lu)
    if symbole:
        assert lu.symbole == symbole, (question, lu)
    if banque:
        assert lu.banque == banque, (question, lu)


def test_glossaire_au_moins_60_termes_avec_une_page():
    assert len(GLOSSAIRE) >= 60
    for cle, (motif, texte, href) in GLOSSAIRE.items():
        assert motif and 20 <= len(texte) <= 400 and href.startswith("/"), cle


def test_chaque_terme_du_glossaire_est_reconnu(univers):
    exemples = {"stop": "c'est quoi un stop", "limite": "c'est quoi un ordre limite", "ordre_marche": "c'est quoi un ordre au marché",
                "prix_revient": "c'est quoi le prix de revient", "plus_value": "c'est quoi une plus-value", "indice": "c'est quoi un indice",
                "moyenne_mobile": "c'est quoi une moyenne mobile", "support": "c'est quoi un support", "pire_cas": "c'est quoi le pire cas",
                "regime": "c'est quoi un régime de marché", "parite_risque": "c'est quoi la parité de risque", "xai": "c'est quoi une ia explicable",
                "ton": "c'est quoi le ton d'une actualité", "dcr": "c'est quoi le risque commercial déplacé", "psia": "c'est quoi les psia",
                "regression_logistique": "c'est quoi la régression logistique", "achat_complementaire": "c'est quoi un achat complémentaire"}
    for cle, (motif, _, _) in GLOSSAIRE.items():
        q = exemples.get(cle, f"c'est quoi le {cle.replace('_', ' ')}")
        lu = comprendre(q, univers)
        assert lu.intention in ("definition", "credit", "assurance"), (cle, q, lu)
        if lu.intention == "definition":
            assert lu.terme == cle, (cle, q, lu.terme)


@pytest.mark.parametrize("intention", sorted(couverture.SUITES))
def test_les_suites_proposees_sont_comprises(univers, intention):
    for q in couverture.SUITES[intention]:
        assert comprendre(q, univers, "AAPL", page="portefeuille").intention not in ("inconnu", "accueil"), q


def test_suite_de_conversation(univers):
    assert comprendre("et pour Bitcoin ?", univers, contexte={"intention": "actif", "symbole": "AAPL"}).symbole == "BTC-USD"
    lu = comprendre("et bitcoin ?", univers, contexte={"intention": "prediction", "symbole": "AAPL"})
    assert lu.intention == "prediction" and lu.symbole == "BTC-USD" and lu.suite
    lu = comprendre("pourquoi ?", univers, contexte={"intention": "risque", "symbole": None})
    assert lu.intention == "risque" and lu.suite
    assert comprendre("et en 2020 ?", univers, contexte={"intention": "indice"}).intention == "temps"
    assert comprendre("et lui ?", univers, contexte={"intention": "stress", "banque": "snb"}).banque == "snb"
    assert comprendre("pourquoi ?", univers).intention == "inconnu"                        # sans contexte : on le dit
    assert comprendre("c'est quoi le RSI ?", univers, contexte={"intention": "risque"}).intention == "definition"
    lu = comprendre("pourquoi ?", univers, contexte={"intention": "comparer", "symbole": "AAPL", "symbole2": "BTC-USD"})
    assert lu.intention == "comparer" and (lu.symbole, lu.symbole2) == ("AAPL", "BTC-USD")


def test_suite_d_une_comparaison_par_l_api(client, utilisateur):
    u = utilisateur()
    investi(client, u)
    r = demander(client, u, "pourquoi ?", contexte={"intention": "comparer", "symbole": "TST", "symbole2": None})
    assert r["intention"] == "actif" and "None" not in r["texte"]                 # sans second actif : on explique le premier


# ------------------------------------------------------------------ API
def demander(client, u, question, **extra):
    r = client.post("/api/v1/xai/question", json={"question": question, **extra}, headers=u.h)
    assert r.status_code == 200, r.text
    return r.json()


def investi(client, u):
    assert client.post("/api/v1/horloge/aller-a", json={"instant": "2020-02-28T17:00:00"}, headers=u.h).status_code == 200
    achat = {"symbole": "TST", "sens": "achat", "quantite": 12, "type": "marche"}
    assert client.post("/api/v1/ordres", json=achat, headers=u.h).json()["statut"] == "execute"


PAGES_MENU = ["", "marche", "actif", "portefeuille", "strategies", "jeu", "stress", "formation", "actuariat", "xai", "actualites",
              "credit", "ia", "compte", "admin", "actions"]


@pytest.mark.parametrize("page", PAGES_MENU)
def test_explique_cette_page_donne_un_chiffre_du_compte(client, utilisateur, page):
    u = utilisateur()
    investi(client, u)
    r = demander(client, u, "Explique cette page", page=page, symbole="TST" if page == "actif" else None)
    assert r["intention"] == "page" and "USD" in r["texte"] and "Cette page" in r["texte"]
    assert 2 <= r["texte"].count(".") <= 7


def test_page_inconnue_refusee_ou_tombe_sur_le_dashboard(client, utilisateur):
    u = utilisateur()
    assert client.post("/api/v1/xai/question", json={"question": "explique cette page", "page": "../etc"}, headers=u.h).status_code == 422
    assert "Dashboard" in demander(client, u, "explique cette page", page="inexistante")["texte"]


def test_contexte_invalide_ignore(client, utilisateur):
    u = utilisateur()
    r = demander(client, u, "pourquoi ?", contexte={"intention": "pirate", "symbole": "XXX"})
    assert r["intention"] == "inconnu"
    r = demander(client, u, "et pour TST ?", contexte={"intention": "actif", "symbole": "AAPL"})
    assert r["intention"] == "actif" and r["symbole"] == "TST"


def test_chaque_reponse_propose_deux_suites(client, utilisateur):
    u = utilisateur()
    for q in ("risque", "c quoi le rsi", "quelle banque est la plus fragile", "bonjour", "recette de crêpes"):
        r = demander(client, u, q)
        assert len(r["suivantes"]) == 2


def test_dashboard_somme_exacte(client, utilisateur):
    u = utilisateur()
    investi(client, u)
    r = demander(client, u, "résume mon tableau de bord")
    pf = client.get("/api/v1/portefeuille", headers=u.h).json()
    assert sum(b["valeur"] for b in r["preuve"]["barres"]) == pytest.approx(pf["equity"], abs=0.01)


def test_stress_sur_les_vraies_banques(client, utilisateur):
    u = utilisateur()
    r = demander(client, u, "quelle banque est la plus fragile ?")
    assert "AlJazira" in r["texte"] and "inventée" not in r["texte"] and "Pilier 3" in r["preuve"]["limite"]
    d = demander(client, u, "pourquoi AlJazira est la plus fragile ?")
    assert d["banque"] == "aljazira" and "rang 1 sur 9" in d["texte"]
    from app.stress import credit, donnees_reelles, scenarios
    b = next(x for x in donnees_reelles.charger() if x.cle == "aljazira")
    attendu = credit.simuler_scenario(b, scenarios.parametres("recession", "extreme"))
    assert sum(x["valeur"] for x in d["preuve"]["barres"]) == pytest.approx(attendu["capital_apres_md"])   # capital − perte = restant


def test_credit_somme_exacte(client, utilisateur):
    from app.credit import zscore
    r = demander(client, utilisateur(), "c'est quoi le z-score ?")
    z = zscore.calculer(zscore.EXEMPLES[0]["comptes"], "z")["z"]
    assert sum(b["valeur"] for b in r["preuve"]["barres"]) == pytest.approx(z) and "fictive" in r["texte"]


def test_actualites_somme_exacte(client, utilisateur):
    u = utilisateur()
    investi(client, u)
    r = demander(client, u, "sentiment des actualités")
    if r["preuve"]["barres"]:
        n = int(r["texte"].split(" ")[0])
        assert sum(b["valeur"] for b in r["preuve"]["barres"]) == n


def test_comparer_deux_actifs(client, utilisateur):
    u = utilisateur()
    investi(client, u)
    r = demander(client, u, "compare TST et CRY")
    assert r["intention"] in ("comparer", "inconnu")          # l'univers de test peut ne pas les connaître tous les deux
    assert r["texte"]


def test_rien_apres_la_date_simulee(client, utilisateur, monkeypatch):
    u = utilisateur()
    investi(client, u)
    vu = []
    from app.marche.moteur import MoteurMarche
    from app.marche.stockage import Magasin

    barres, cotation = Magasin.barres_terminees, MoteurMarche.cotation
    monkeypatch.setattr(Magasin, "barres_terminees", lambda self, s, avant, n=None: vu.append(str(avant)) or barres(self, s, avant, n))
    monkeypatch.setattr(MoteurMarche, "cotation", lambda self, s, t, *a, **k: vu.append(t.date().isoformat()) or cotation(self, s, t, *a, **k))
    for q in ("résume mon tableau de bord", "explique TST", "compare TST et CRY", "sentiment des actualités", "mes ordres en attente"):
        demander(client, u, q)
    demander(client, u, "explique cette page", page="actif", symbole="TST")
    assert vu and max(vu) <= "2020-02-28"


QUESTIONS_30 = [q for q, *_ in CORPUS[::5]][:30]


def test_lecture_seule_sur_30_questions(client, utilisateur, base_test):
    u = utilisateur()
    investi(client, u)
    client.post("/api/v1/horloge/pause", headers=u.h)
    client.get("/api/v1/portefeuille", headers=u.h)
    with base_test.session() as s:
        avant = persistance.charger(s, u.id)
    assert len(QUESTIONS_30) == 30
    for q in QUESTIONS_30:
        demander(client, u, q)
    with base_test.session() as s:
        assert persistance.charger(s, u.id) == avant


def test_aucun_caractere_de_controle(client, utilisateur):
    u = utilisateur()
    for q in ("résume mon tableau de bord", "quelle banque est la plus fragile", "c quoi le z-score", "explique cette page",
              "pourquoi ce niveau de risque ?", "que dit la presse sur TST ?", "bonjour"):
        r = demander(client, u, q)
        textes = [r["texte"], r["preuve"]["methode"], r["preuve"]["limite"], *r["preuve"]["donnees"], *(b["affiche"] for b in r["preuve"]["barres"])]
        for t in textes:                                  # sur les textes eux-mêmes : le JSON masquerait un « \x01 »
            assert not any(ord(c) < 32 for c in t), (q, t)
    assert "AlJazira : il faudrait" in demander(client, u, "quelle banque est la plus fragile")["texte"]   # le « : » n'est plus mangé


def test_seance_mystere_ne_fuit_pas_meme_avec_autre_choix(client, utilisateur, base_test):
    u = utilisateur()
    with base_test.session() as s:
        p = jeu.creer(s, u.id, "mystere", None, "acteur", PLAN)
        b = jeu._bobine(p.film)
        titre, sujet = b.film.titre, b.film.sujet
        p = jeu._ecrire(s, p, p.version, seance=b.dernier - 1, choix=[{"jour": j, "acte": "tenir"} for j in b.arrets])
        jeu.avancer(s, p, p.version)
    for q in ("qu'aurait donné un autre choix au jeu ?", "explique ma note", "explique cette page"):
        brut = json.dumps(demander(client, u, q, page="jeu"), ensure_ascii=False)
        assert titre not in brut and sujet not in brut, q


def test_autre_choix_au_jeu_donne_les_ecarts(client, utilisateur, base_test):
    u = utilisateur()
    with base_test.session() as s:
        p = jeu.creer(s, u.id, "mystere", None, "acteur", PLAN)
        b = jeu._bobine(p.film)
        p = jeu._ecrire(s, p, p.version, seance=b.dernier - 1, choix=[{"jour": j, "acte": "tenir"} for j in b.arrets])
        jeu.avancer(s, p, p.version)
    r = demander(client, u, "qu'aurait donné un autre choix au jeu ?")
    assert "montage alternatif" in r["texte"] and len(r["preuve"]["barres"]) >= 3


def test_temps_de_reponse_sur_50_questions(client, utilisateur):
    u = utilisateur()
    investi(client, u)
    questions = [q for q, *_ in CORPUS if "modele" not in q][:50]
    debut = time.perf_counter()
    for q in questions:
        demander(client, u, q)
    moyenne = (time.perf_counter() - debut) / len(questions)
    print(f"\nTemps moyen sur {len(questions)} questions : {moyenne * 1000:.0f} ms")
    assert moyenne < 0.3, f"{moyenne * 1000:.0f} ms en moyenne"


@pytest.mark.parametrize("page", sorted(SUGGESTIONS))
def test_suggestions_de_page_comprises(univers, page):
    for q in SUGGESTIONS[page]:
        assert comprendre(q, univers, "AAPL", page=page).intention not in ("inconnu", "accueil"), q
