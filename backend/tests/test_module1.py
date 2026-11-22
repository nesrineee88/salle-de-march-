"""Module 1 (date, rendement total, indices, risque, Direct) : un test par défaut constaté le 22/11/2026."""
import threading
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd
import pytest

from app import config
from app.contexte import Contexte, acces_bac
from app.direct import routes as routes_direct
from app.marche.catalogue import Actif, Univers, charger_univers
from app.marche.moteur import MoteurMarche
from app.marche.stockage import Magasin
from app.risque import indicateurs as ind
from app.risque import suivi, synthese
from app.scenarios.surcouche import symboles_concernes
from app.trading import persistance

from .conftest import serie_synthetique
from .test_portefeuille_api import acheter, aller


def historique(client, u):
    return client.get("/api/v1/portefeuille/historique", headers=u.h).json()


# ------------------------------------------------------------------ 1. on ne triche plus avec la date
def test_reculer_est_refuse_et_ne_change_rien(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-02-03T17:00:00")
    assert acheter(client, u, 100)["statut"] == "execute"
    aller(client, u, "2020-03-20T17:00:00")
    assert acheter(client, u, 100, sens="vente")["statut"] == "execute"
    avant = client.get("/api/v1/portefeuille", headers=u.h).json()
    r = client.post("/api/v1/horloge/aller-a", json={"instant": "2020-02-03T17:00:00"}, headers=u.h)
    assert r.status_code == 409 and "Recommencer" in r.json()["detail"]
    assert client.get("/api/v1/portefeuille", headers=u.h).json() == avant


def test_recommencer_repart_du_capital_a_la_date_choisie(client, utilisateur, base_test):
    u = utilisateur()
    aller(client, u, "2020-03-02T17:00:00")
    assert acheter(client, u, 50)["statut"] == "execute"
    r = client.post("/api/v1/horloge/aller-a", json={"instant": "2020-02-03T17:00:00", "recommencer": True}, headers=u.h)
    assert r.status_code == 200 and r.json()["maintenant"] == "2020-02-03T17:00:00" and r.json()["en_pause"] is True
    p = client.get("/api/v1/portefeuille", headers=u.h).json()
    assert p["positions"] == [] and p["equity"] == p["capital_initial"]
    assert [x["jour"] for x in historique(client, u)["points"]] == ["2020-02-03"]
    with base_test.session() as s:
        etat = persistance.charger(s, u.id)
    assert etat["executions"] == [] and etat["horloge_instant"].startswith("2020-02-03T17:00")


def test_recommencer_respecte_la_fenetre(client, utilisateur):
    u = utilisateur()
    r = client.post("/api/v1/horloge/aller-a", json={"instant": "2010-01-01T17:00:00", "recommencer": True}, headers=u.h)
    assert r.status_code == 422


def test_une_requete_en_attente_ne_ressuscite_pas_le_portefeuille_reinitialise(client, utilisateur, ctx_test):
    u = utilisateur()
    aller(client, u, "2020-02-03T17:00:00")
    assert acheter(client, u, 10)["statut"] == "execute"
    ancien = ctx_test.bac(u.id)
    vu = []

    def lire():
        with acces_bac(ctx_test, u) as (bac, _t):
            vu.append(bac)

    with ancien.verrou:
        fil = threading.Thread(target=lire)
        fil.start()                                    # attend le verrou de l'ancien bac
        fil.join(0.2)
        neuf = ctx_test.reinitialiser(u.id)
    fil.join(5)
    assert vu == [neuf] and neuf.salle.compte(neuf.compte_id).positions == {}


# ------------------------------------------------------------------ 2. un saut donne un point par jour
def test_un_saut_enregistre_chaque_jour_traverse(client, utilisateur, base_test, magasin_test):
    u = utilisateur()
    aller(client, u, "2020-02-03T17:00:00")
    assert acheter(client, u, 500)["statut"] == "execute"
    aller(client, u, "2020-03-20T17:00:00")
    points = historique(client, u)["points"]
    attendus = [d.date().isoformat() for d in pd.date_range("2020-02-03", "2020-03-20")]
    assert [p["jour"] for p in points] == attendus
    cloture = magasin_test.prix_origine("TST").loc["2020-02-27", "close"]
    p27 = next(p for p in points if p["jour"] == "2020-02-27")
    assert p27["equity"] == pytest.approx(p27["cash"] + 500 * cloture, rel=1e-3)
    valeurs = [p["equity"] for p in points]
    affiche = client.get("/api/v1/portefeuille/analyse", headers=u.h).json()["performance"]["drawdown_max"]
    assert affiche == pytest.approx(ind.drawdown(valeurs)["max"], abs=1e-4) and affiche > 0
    with base_test.session() as s:
        assert set(attendus) <= {p["jour"] for p in persistance.lire_historique(s, u.id)}


def test_un_stop_est_declenche_pendant_un_saut(client, utilisateur, magasin_test):
    u = utilisateur()
    serie = magasin_test.prix_origine("CRY")
    aller(client, u, "2020-01-10T12:00:00")
    assert acheter(client, u, 20, symbole="CRY")["statut"] == "execute"
    moyen = client.get("/api/v1/portefeuille", headers=u.h).json()["positions"][0]["prix_moyen"]
    plus_bas = float(serie.loc["2020-01-11":"2020-03-25", "close"].min())
    if plus_bas >= moyen:
        pytest.skip("la série de test ne baisse pas")
    seuil = (1 - plus_bas / moyen) * 100 / 2
    assert client.put("/api/v1/regles", json={"symbole": "CRY", "type": "stop_loss", "seuil_pct": seuil}, headers=u.h).status_code == 200
    aller(client, u, "2020-03-26T12:00:00")
    regle = client.get("/api/v1/regles", headers=u.h).json()[0]
    assert regle["statut"] == "declenchee" and "2020-01-10" <= regle["declenchee_le"][:10] <= "2020-03-26"


@pytest.mark.parametrize("graine", range(12))
def test_le_raccourci_des_jours_calmes_ne_change_aucun_resultat(graine):
    from app.trading.salle import SalleDeMarche

    alea = np.random.default_rng(graine)
    univers = Univers(date(2020, 1, 1), date(2020, 12, 31), 0, {
        "A": Actif("A", "A", "action", "T", "semaine", session_utc=(time(14, 30), time(21, 0))),
        "C": Actif("C", "C", "crypto", "T", "continu")})
    magasin = Magasin({"A": serie_synthetique("2020-01-01", 150, "semaine", 100, graine),
                       "C": serie_synthetique("2020-01-01", 200, "continu", 60, graine + 50)})
    depart = datetime(2020, 1, 6, 17)
    seuils = {s: alea.uniform(0.02, 0.12, 4) for s in ("A", "C")}

    def jouer(raccourci):
        moteur = MoteurMarche(magasin, univers)
        salle = SalleDeMarche(moteur, univers)
        salle.ouvrir_compte("u")
        salle.avancer(depart)
        for s, x in seuils.items():
            assert salle.passer_ordre("u", s, "achat", 80, depart).statut == "execute"
            moyen = salle.compte("u").positions[s].prix_moyen
            salle.poser_regle("u", s, "stop_loss", -x[0], 0.5, depart)
            salle.poser_regle("u", s, "stop_suiveur" if graine % 2 else "take_profit", x[1], 0.5, depart)
            salle.passer_ordre("u", s, "achat", 5, depart, type="limite", prix_limite=moyen * (1 - x[2]))
            salle.passer_ordre("u", s, "vente", 5, depart, type="stop", prix_stop=moyen * (1 - x[3]))
        for j in pd.date_range("2020-01-06", "2020-05-15"):
            fin = datetime.combine(j.date(), time(23, 59, 59))
            (salle.avancer_journee if raccourci else salle.avancer)(fin, pas_s=900.0)
        etat = salle.exporter("u")
        return (etat["executions"], [(r["id"], r["statut"], r["declenchee_le"]) for r in etat["regles"]],
                [(o["id"], o["statut"]) for o in etat["ordres"]], etat["cash"])

    assert jouer(True) == jouer(False)


# ------------------------------------------------------------------ 3 et 4. l'indice part avec vous, dividendes compris
@pytest.fixture
def ctx_indices():
    def actif(s, classe="indice"):
        return Actif(s, s, classe, "Test", "semaine", tradable=classe != "indice")

    univers = Univers(date(2020, 1, 1), date(2020, 12, 31), 0, {s: actif(s) for s in ("^GSPC", "^SP500TR")})
    series = {"^GSPC": serie_synthetique("2020-01-01", 80, "semaine", 3000, 3),
              "^SP500TR": serie_synthetique("2020-01-01", 80, "semaine", 6000, 4)}
    magasin = Magasin(series)
    return Contexte(univers, magasin, MoteurMarche(magasin, univers))


def test_le_sp500_avec_dividendes_remplace_la_version_prix(ctx_indices):
    refs = suivi.references_disponibles(ctx_indices.magasin)
    assert [r["symbole"] for r in refs] == ["^SP500TR"] and refs[0]["dividendes"] is True
    sans = Magasin({"^GSPC": ctx_indices.magasin.prix_origine("^GSPC")})
    assert [r["symbole"] for r in suivi.references_disponibles(sans)] == ["^GSPC"]


def test_l_indice_part_de_la_premiere_transaction(ctx_indices):
    class E:
        instant = datetime(2020, 2, 3, 17, 0)

    t = datetime(2020, 3, 20, 17, 0)
    debut = suivi.debut_suivi([E()], t)
    valo = {"capital_initial": 100_000.0, "equity": 104_000.0, "cash": 4_000.0, "valeur_positions": 100_000.0}
    points = suivi.points_suivi([{"jour": "2020-01-02", "instant": "2020-01-02T23:59:59", "equity": 100_000.0}], valo, debut, t)
    assert [p["jour"] for p in points] == ["2020-02-03", "2020-03-20"]        # rien avant la première transaction
    s = suivi.serie_reference(ctx_indices.magasin, ctx_indices.moteur, "^SP500TR", points, 100_000.0)
    base = ctx_indices.moteur.cotation("^SP500TR", debut).prix
    fin = ctx_indices.moteur.cotation("^SP500TR", t).prix
    assert s == pytest.approx([100_000.0, 100_000.0 * fin / base])
    r = suivi.resumer(ctx_indices, points, valo, [E()], debut, t)
    assert r["rendement_total"] == pytest.approx(0.04) and r["references"][0]["depuis_debut"] == pytest.approx(fin / base - 1)
    assert r["references"][0]["ecart_points"] == pytest.approx((0.04 - (fin / base - 1)) * 100)


def test_l_indice_ne_lit_pas_la_cloture_du_jour_en_cours(ctx_indices):
    t = datetime(2020, 2, 3, 10, 0)
    avant = suivi.valeur_reference(ctx_indices.moteur, "^GSPC", t)
    assert avant == ctx_indices.moteur.cotation("^GSPC", t).prix
    assert avant != ctx_indices.magasin.barre_du_jour("^GSPC", t.date())["close"]


def test_sans_transaction_le_rendement_est_nul(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-02-10T17:00:00")
    s = client.get("/api/v1/tableau-de-bord", headers=u.h).json()["suivi"]
    assert s["a_commence"] is False and s["rendement_total"] == 0 and s["debut"] == "2020-02-10T17:00:00"


def test_rendement_total_et_resultat_du_jour(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-02-03T17:00:00")
    assert acheter(client, u, 300)["statut"] == "execute"
    aller(client, u, "2020-02-12T17:00:00")
    p = client.get("/api/v1/portefeuille", headers=u.h).json()
    s = client.get("/api/v1/tableau-de-bord", headers=u.h).json()["suivi"]
    veille = historique(client, u)["points"][-2]
    assert s["debut"] == "2020-02-03T17:00:00" and s["a_commence"] is True and veille["jour"] == "2020-02-11"
    assert s["rendement_total"] == pytest.approx(p["equity"] / p["capital_initial"] - 1)
    assert s["resultat_jour"] == pytest.approx(p["equity"] - veille["equity"])


def test_reference_inconnue_refusee(client, utilisateur):
    u = utilisateur()
    assert client.get("/api/v1/portefeuille/historique?reference=RIEN", headers=u.h).status_code == 422


# ------------------------------------------------------------------ 5 et 6. Direct en lecture seule, date conservée
def test_direct_fige_le_compte_et_rend_la_date(client, utilisateur, monkeypatch, ctx_test):
    idx = pd.DatetimeIndex(["2020-03-25", "2020-03-26"])
    flux = pd.DataFrame({"open": 120.0, "high": 125.0, "low": 119.0, "close": 123.0, "volume": 1000.0}, index=idx)
    monkeypatch.setattr(routes_direct, "telechargeur_actuel", lambda s: {"TST": flux})
    monkeypatch.setattr("app.contexte.maintenant_utc", lambda: datetime(2020, 3, 26, 16, 0))
    u = utilisateur()
    aller(client, u, "2020-02-03T17:00:00")
    assert acheter(client, u, 10)["statut"] == "execute"
    avant = client.get("/api/v1/portefeuille", headers=u.h).json()
    points = historique(client, u)["points"]
    assert client.post("/api/v1/direct/activer", headers=u.h).status_code == 200
    i = client.get("/api/v1/marche/instantane", headers=u.h).json()
    assert i["instant"].startswith("2020-03-26") and i["instant_compte"] == "2020-02-03T17:00:00"
    assert client.get("/api/v1/portefeuille", headers=u.h).json() == avant and historique(client, u)["points"] == points
    ordre = {"symbole": "TST", "sens": "vente", "quantite": 5, "type": "marche"}
    assert client.post("/api/v1/ordres", json=ordre, headers=u.h).status_code == 409
    assert client.put("/api/v1/regles", json={"symbole": "TST", "type": "stop_loss", "seuil_pct": 10}, headers=u.h).status_code == 409
    r = client.post("/api/v1/horloge/aller-a", json={"instant": "2020-01-10T17:00:00", "recommencer": True}, headers=u.h)
    assert r.status_code == 409
    assert client.post("/api/v1/direct/quitter", headers=u.h).status_code == 200
    assert client.get("/api/v1/marche/instantane", headers=u.h).json()["instant"] == "2020-02-03T17:00:00"
    assert client.get("/api/v1/portefeuille", headers=u.h).json() == avant


# ------------------------------------------------------------------ risque
def test_poids_et_notes_aux_seuils():
    assert sum(p for _, p, _, _ in synthese.FAMILLES) == pytest.approx(1.0)
    for _, _, bas, haut in synthese.FAMILLES:
        assert synthese.noter(0, bas, haut) == 0 and synthese.noter(bas, bas, haut) == pytest.approx(100 / 3)
        assert synthese.noter(haut, bas, haut) == pytest.approx(200 / 3) and synthese.noter(2 * haut, bas, haut) == pytest.approx(100)
        assert synthese.noter(9 * haut, bas, haut) == 100


def test_week_end_crypto_reporte_sur_le_lundi():
    jours = pd.date_range("2020-01-03", "2020-01-06")           # vendredi à lundi
    r = ind.rendements_actifs({"C": pd.Series([100.0, 80.0, 70.0, 75.0], index=jours),
                               "A": pd.Series([50.0, 51.0], index=jours[[0, 3]])})
    assert r["C"].tolist() == pytest.approx([-0.25])            # et non +7,1 % (dimanche → lundi)


def test_fenetre_de_250_seances_et_annualisation():
    j = pd.date_range("2020-01-01", periods=400)
    r = ind.rendements_actifs({"C": pd.Series(np.arange(1.0, 401.0), index=j)}, ind.SEANCES_RISQUE)
    assert len(r) == 250 and ind.seances_par_an(r.index) == 365
    assert ind.seances_par_an(pd.bdate_range("2020-01-01", periods=100)) == 252


def test_drawdown_des_poids():
    assert ind.drawdown_rendements([0.1, -0.5, 0.2]) == pytest.approx(0.5)
    assert ind.drawdown_rendements([-3.06, 1.2]) == 1.0         # WTI négatif : plafonné à 100 %


def test_les_indices_d_actions_suivent_une_crise_sur_les_actions():
    u = charger_univers(config.UNIVERS_YAML)
    assert {"^GSPC", "^SP500TR", "^NDX", "^DJI", "^990100-USD-STRD"} <= symboles_concernes(u, "classe", ("action",))


def test_la_fenetre_brute_est_inchangee():
    u = charger_univers(config.UNIVERS_YAML)
    assert u.debut == date(2019, 1, 2) and u.debut - timedelta(days=u.historique_prealable_jours) == date(2016, 11, 27)


VRAIES = all((config.CLEAN_DIR / f).exists() for f in ("KO.csv", "GC_F.csv")) and not config.MARQUEUR_SYNTHETIQUE.exists()


@pytest.mark.skipif(not VRAIES, reason="vraies données absentes")
@pytest.mark.parametrize("symbole, part, pondere, niveau", [("KO", 1.0, "modere", "eleve"), ("GC=F", 0.3, "faible", "faible")])
def test_exemples_valides_sur_les_vraies_donnees(symbole, part, pondere, niveau):
    u = charger_univers(config.UNIVERS_YAML)
    fichier = config.CLEAN_DIR / u[symbole].fichier
    prix = pd.read_csv(fichier, index_col="date", parse_dates=True)["close"][:"2026-10-30"].tail(420)
    serie = ind.rendements_portefeuille({symbole: part}, ind.rendements_actifs({symbole: prix}, ind.SEANCES_RISQUE))
    risque = {**ind.var_cvar(serie), "drawdown_poids": ind.drawdown_rendements(serie),
              "volatilite_annuelle_seances": ind.ecart_type(serie) * ind.seances_par_an(serie.index) ** 0.5}
    r = synthese.niveau_risque({"risque": risque, "repartition": {
        "position": [{"libelle": symbole, "part": part}], "secteur": [{"libelle": u[symbole].secteur, "part": part}]}})
    assert (r["niveau_pondere"], r["niveau"]) == (pondere, niveau)
