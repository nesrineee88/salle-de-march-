"""Stress de crédit sur les banques RÉELLES : contrôles du CSV, exemples à la main, valeurs de référence, routes. Sans réseau."""
import csv
import math

import pytest

from app.stress import credit, donnees_reelles, modele
from pipeline import banques as pipeline_banques

REFERENCE = {   # PD départ, CET1 adverse, sévère, extrême, hausse vers 4,5 %, hausse vers 7 % (LGD 45 %)
    "alrajhi": (0.00748, 0.15553, 0.13962, 0.10849, 0.23889, 0.18972),
    "alinma": (0.00916, 0.12530, 0.11152, 0.08553, 0.22728, 0.16440),
    "albilad": (0.00975, 0.13676, 0.12106, 0.09176, 0.23514, 0.17831),
    "aljazira": (0.01030, 0.11130, 0.09612, 0.06808, 0.18764, 0.12734),
    "snb": (0.00681, 0.16947, 0.15762, 0.13402, 0.33233, 0.26958),
    "riyad": (0.01121, 0.12493, 0.11126, 0.08637, 0.25177, 0.18227),
    "sab": (0.02529, 0.12933, 0.11053, 0.08081, 0.28214, 0.21390),
    "bsf": (0.00969, 0.15213, 0.13887, 0.11409, 0.31386, 0.24679),
    "saib": (0.02002, 0.12397, 0.10355, 0.06997, 0.22844, 0.17024),
}
ORDRE = ("central", "adverse", "severe", "extreme")


@pytest.fixture(scope="module")
def banques():
    return donnees_reelles.charger()


def lignes_brutes():
    with donnees_reelles.CHEMIN.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------ le CSV
def test_chaque_ligne_du_csv_est_coherente():
    lignes = lignes_brutes()
    assert len(lignes) == 9
    for x in lignes:
        assert abs(float(x["cet1_capital"]) / float(x["actifs_ponderes"]) - float(x["cet1_ratio"])) < 0.00011, x["cle"]
        ecart = float(x["prets_defaut"]) + float(x["prets_sains"]) - float(x["provisions"]) - float(x["prets_nets"])
        assert abs(ecart) <= 2, x["cle"]
        assert x["source_url"].startswith("https://") and x["page_km1"] and x["page_cr1"] and x["date_collecte"] and len(x["sha256"]) == 64
        assert x["ratio_type"] == "CET1" and x["estime"] == "non"


def test_quatre_islamiques_cinq_conventionnelles_un_seul_pays(banques):
    assert [b.type for b in banques].count("islamique") == 4 and [b.type for b in banques].count("conventionnelle") == 5
    r = donnees_reelles.resume(banques)
    assert r["pays"] == ["SA"] and r["devises"] == ["SAR"] and r["dates_arrete"] == ["2025-12-31"]


def test_aucun_statut_relu_sans_relecture_humaine(banques):
    assert all(b.statut == "a_relire" for b in banques)


def test_csv_mal_forme_nomme_la_ligne_fautive(tmp_path):
    lignes = lignes_brutes()
    lignes[2]["cet1_ratio"] = "0.2000"
    f = tmp_path / "b.csv"
    with f.open("w", encoding="utf-8", newline="") as s:
        w = csv.DictWriter(s, fieldnames=donnees_reelles.COLONNES)
        w.writeheader()
        w.writerows(lignes)
    with pytest.raises(donnees_reelles.ErreurDonneesBanques, match="ligne 4, colonne « cet1_ratio »"):
        donnees_reelles.charger(f)
    lignes[2]["cet1_ratio"] = lignes_brutes()[2]["cet1_ratio"]
    lignes[0]["prets_nets"] = str(float(lignes[0]["prets_nets"]) + 10)
    with f.open("w", encoding="utf-8", newline="") as s:
        w = csv.DictWriter(s, fieldnames=donnees_reelles.COLONNES)
        w.writeheader()
        w.writerows(lignes)
    with pytest.raises(donnees_reelles.ErreurDonneesBanques, match="ligne 2, colonne « prets_nets »"):
        donnees_reelles.charger(f)


def test_csv_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        donnees_reelles.charger(tmp_path / "absent.csv")


# ------------------------------------------------------------------ exemples à la main
def test_exemple_1_douze_vers_neuf_virgule_soixante_quinze():
    # perte = 100 × 0,05 × 0,45 = 2,25 ; (12 − 2,25) / 100 = 9,75 %
    assert credit.cet1_apres(12, 100, 100, 0.05, 0.45) == pytest.approx(0.0975, abs=1e-12)


def test_exemple_2_credit_et_marche():
    # 60 × 0,03 × 0,45 = 0,81 ; 5 × 0,25 = 1,25 ; (7,2 − 2,06) / 60 = 8,5667 %
    assert credit.cet1_apres(7.2, 60, 60, 0.03, 0.45, titres=5, baisse_titres=-0.25) == pytest.approx(0.085667, abs=1e-6)


def test_hausse_qui_casse_seize_virgule_six_points():
    # (7,2 − 0,045 × 60) / (60 × 0,45) = 4,5 / 27
    h = credit.hausse_qui_casse(7.2, 60, 60, 0.45)
    assert h == pytest.approx(0.166667, abs=1e-6)
    assert credit.cet1_apres(7.2, 60, 60, h, 0.45) == pytest.approx(0.045, abs=1e-12)


def test_vasicek_a_la_main():
    pd = 0.01
    r = credit.correlation(pd)
    w = (1 - math.exp(-0.5)) / (1 - math.exp(-50))
    assert r == pytest.approx(0.12 * w + 0.24 * (1 - w))
    n = credit.NORMALE
    assert credit.pd_stressee(pd, 0.999) == pytest.approx(n.cdf((n.inv_cdf(pd) + math.sqrt(r) * n.inv_cdf(0.999)) / math.sqrt(1 - r)))
    assert credit.pd_stressee(pd, None) == pd and credit.pd_stressee(0.0, 0.99) == 0.0


# ------------------------------------------------------------------ valeurs de référence
@pytest.mark.parametrize("cle", list(REFERENCE))
def test_valeurs_de_reference(banques, cle):
    b = next(x for x in banques if x.cle == cle)
    pd0, adv, sev, ext, v45, v7 = REFERENCE[cle]
    r = {s: credit.stresser_banque(b, s, 0.45) for s in ORDRE}
    assert r["central"]["pd_avant"] == pytest.approx(pd0, abs=1e-3)
    assert r["adverse"]["cet1_apres"] == pytest.approx(adv, abs=1e-3)
    assert r["severe"]["cet1_apres"] == pytest.approx(sev, abs=1e-3)
    assert r["extreme"]["cet1_apres"] == pytest.approx(ext, abs=1e-3)
    assert r["adverse"]["hausse_vers_4_5"] == pytest.approx(v45, abs=1e-3)
    assert r["adverse"]["hausse_vers_7"] == pytest.approx(v7, abs=1e-3)


def test_moyennes_simples_par_groupe(banques):
    central = credit.comparer(banques, "central")["groupes"]
    extreme = credit.comparer(banques, "extreme")["groupes"]
    assert central["islamique"]["cet1_apres"] == pytest.approx(0.14327, abs=1e-3)
    assert extreme["islamique"]["cet1_apres"] == pytest.approx(0.08847, abs=1e-3)
    assert central["conventionnelle"]["cet1_apres"] == pytest.approx(0.15329, abs=1e-3)
    assert extreme["conventionnelle"]["cet1_apres"] == pytest.approx(0.09705, abs=1e-3)


def test_central_redonne_les_chiffres_publies(banques):
    for b in banques:
        r = credit.stresser_banque(b, "central")
        assert r["perte"] == 0 and r["cet1_apres"] == pytest.approx(b.cet1_ratio, abs=0.00011)


# ------------------------------------------------------------------ cohérence
def test_scenarios_ordonnes_pour_chaque_banque(banques):
    for b in banques:
        v = [credit.stresser_banque(b, s)["cet1_apres"] for s in ORDRE]
        assert v[0] > v[1] > v[2] > v[3], b.cle


def test_lgd_plus_haute_baisse_toujours_le_cet1(banques):
    for b in banques:
        for s in ORDRE[1:]:
            v = [credit.stresser_banque(b, s, l)["cet1_apres"] for l in (0.25, 0.45, 0.60, 0.75)]
            assert v == sorted(v, reverse=True) and len(set(v)) == 4, (b.cle, s)


def test_appliquer_la_hausse_qui_casse_redonne_le_seuil(banques):
    for b in banques:
        for lgd in (0.25, 0.45, 0.75):
            for seuil in (credit.SEUIL_MINIMUM, credit.SEUIL_COUSSIN):
                h = credit.hausse_qui_casse(b.cet1_capital, b.actifs_ponderes, b.prets_bruts, lgd, seuil)
                assert credit.cet1_apres(b.cet1_capital, b.actifs_ponderes, b.prets_bruts, h, lgd) == pytest.approx(seuil, abs=1e-12)


def test_les_barres_xai_tombent_juste(banques):
    for b in banques:
        r = credit.stresser_banque(b, "extreme")
        depart, perte, reste = (x["valeur_md"] for x in r["barres"])
        assert depart + perte == pytest.approx(reste, abs=1e-9) and -perte == pytest.approx(r["perte_md"])


def test_phrase_calculee():
    proche = {"islamique": {"points_perdus": 5.0}, "conventionnelle": {"points_perdus": 5.2}}
    assert "presque autant" in credit.phrase_duel(proche)
    loin = {"islamique": {"points_perdus": 4.0}, "conventionnelle": {"points_perdus": 5.0}}
    assert "islamiques" in credit.phrase_duel(loin)


@pytest.mark.parametrize("scenario, lgd", [("inconnu", 0.45), ("adverse", 0.2), ("adverse", 0.8), ("adverse", float("nan"))])
def test_valider_refuse(scenario, lgd):
    with pytest.raises(ValueError):
        credit.valider(scenario, lgd)


# ------------------------------------------------------------------ routes
def test_routes_reelles(client, utilisateur):
    u = utilisateur()
    b = client.get("/api/v1/stress/reelles/banques", headers=u.h)
    assert b.status_code == 200
    j = b.json()
    assert len(j["banques"]) == 9 and j["resume"]["nb"] == 9
    for x in j["banques"]:
        assert "synthétique" not in x["nom"].lower() and x["source_url"].startswith("https://") and x["page_km1"] and x["page_cr1"]
        assert not {"cet1_capital", "actifs_ponderes", "prets_defaut", "prets_sains", "provisions"} & set(x)   # chiffres bruts gardés au serveur
    c = client.post("/api/v1/stress/reelles/comparer", json={"scenario": "extreme", "lgd": 0.45}, headers=u.h)
    assert c.status_code == 200
    cj = c.json()
    assert len(cj["resultats"]) == 9 and cj["groupes"]["islamique"]["cet1_apres"] == pytest.approx(0.08847, abs=1e-3) and cj["phrase"]
    noms_inventes = {bq.nom for bq in modele.panel_synthetique()}
    assert not noms_inventes & {r["banque"] for r in cj["resultats"]}
    for clef in ("cet1_avant", "cet1_apres", "pd_avant", "pd_stressee", "perte", "statut", "hausse_vers_4_5", "hausse_vers_7"):
        assert clef in cj["resultats"][0]
    m = client.get("/api/v1/stress/reelles/matrice?lgd=0.45", headers=u.h)
    assert m.status_code == 200 and len(m.json()["lignes"]) == 9 and m.json()["classement"][0] == "aljazira"


def test_simulation_sur_les_banques_choisies(client, utilisateur):
    u = utilisateur()
    une = client.post("/api/v1/stress/reelles/comparer", json={"scenario": "adverse", "banques": ["aljazira"]}, headers=u.h).json()
    assert [r["cle"] for r in une["resultats"]] == ["aljazira"] and une["resultats"][0]["cet1_apres"] == pytest.approx(0.11130, abs=1e-3)
    assert une["resultats"][0]["prets_defaut_md"] == pytest.approx(1.164659) and set(une["groupes"]) == {"islamique"} and une["phrase"] == ""
    deux = client.post("/api/v1/stress/reelles/comparer", json={"scenario": "extreme", "banques": ["snb", "aljazira"]}, headers=u.h).json()
    assert {r["cle"] for r in deux["resultats"]} == {"snb", "aljazira"} and set(deux["groupes"]) == {"islamique", "conventionnelle"}
    assert client.post("/api/v1/stress/reelles/comparer", json={"banques": ["inventee"]}, headers=u.h).status_code == 422
    assert client.post("/api/v1/stress/reelles/comparer", json={"banques": []}, headers=u.h).status_code == 422


def test_routes_reelles_422_et_authentification(client, utilisateur):
    u = utilisateur()
    assert client.post("/api/v1/stress/reelles/comparer", json={"scenario": "pandemie"}, headers=u.h).status_code == 422
    assert client.post("/api/v1/stress/reelles/comparer", json={"scenario": "adverse", "lgd": 0.9}, headers=u.h).status_code == 422
    assert client.get("/api/v1/stress/reelles/matrice?lgd=0.1", headers=u.h).status_code == 422
    assert client.get("/api/v1/stress/reelles/banques").status_code == 401


def test_csv_absent_donne_503(client, utilisateur, monkeypatch, tmp_path):
    monkeypatch.setattr(donnees_reelles, "CHEMIN", tmp_path / "absent.csv")
    assert client.get("/api/v1/stress/reelles/banques", headers=utilisateur().h).status_code == 503


# ------------------------------------------------------------------ collecte (sans réseau)
def test_robots_refus_respecte(monkeypatch, tmp_path):
    appels = []

    def faux_telecharger(url, sortie, delai=70):
        appels.append(url)
        sortie.write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        return 200

    monkeypatch.setattr(pipeline_banques, "BRUTS", tmp_path)
    monkeypatch.setattr(pipeline_banques, "telecharger", faux_telecharger)
    ligne = lignes_brutes()[0]
    assert pipeline_banques.verifier(ligne) is False
    assert appels == ["https://www.alrajhibank.com.sa/robots.txt"]          # aucun PDF demandé


def test_robots_illisible_vaut_refus(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline_banques, "BRUTS", tmp_path)
    monkeypatch.setattr(pipeline_banques, "telecharger", lambda url, sortie, delai=70: 0)
    assert pipeline_banques.autorisation("https://exemple.invalid/a.pdf") == (False, pipeline_banques.PAUSE)


def test_synthese_pour_l_assistant_xai():
    s = credit.synthese_xai("extreme")
    assert s["pire"]["cle"] == "aljazira" and s["sous_7"] == 2
    assert s["canaux"][0]["perte"] == pytest.approx(s["pire"]["perte_md"]) and "Pilier 3" in s["limite"]


# ------------------------------------------------------------------ scénarios : type de crise × intensité
from app.stress import scenarios  # noqa: E402

TYPES = ("recession", "defauts", "actifs", "combine")
NIVEAUX = ("moderee", "severe", "extreme")


def aljazira(banques):
    return next(b for b in banques if b.cle == "aljazira")


def test_catalogue_complet_et_chaque_parametre_a_son_origine():
    c = scenarios.catalogue()
    assert [t["cle"] for t in c["types"]] == list(TYPES) and [i["cle"] for i in c["intensites"]] == list(NIVEAUX)
    for t in c["types"]:
        for p in t["intensites"].values():
            for levier in ("quantile", "hausse", "lgd"):
                v = p[levier]
                assert (v["origine"] is None) == (v["statut"] is None)
                if v["statut"]:
                    assert v["statut"] in ("publiee", "hypothese", "mesuree", "manuel") and v["justification"]
    assert {x["nom"] for x in c["non_calculables"]} >= {"Hausse des taux", "Baisse des marchés"}


def test_parametres_exacts_du_catalogue():
    def val(t, i, levier):
        return scenarios.parametres(t, i)[levier]["valeur"]
    assert [val("recession", i, "quantile") for i in NIVEAUX] == [0.95, 0.99, 0.999]
    assert {val("recession", i, "lgd") for i in NIVEAUX} == {0.45}
    assert [val("defauts", i, "hausse") for i in NIVEAUX] == [0.02, 0.05, 0.10] and {val("defauts", i, "quantile") for i in NIVEAUX} == {None}
    assert [val("actifs", i, "lgd") for i in NIVEAUX] == [0.55, 0.65, 0.75] and {val("actifs", i, "quantile") for i in NIVEAUX} == {0.95}
    assert [(val("combine", i, "quantile"), val("combine", i, "hausse"), val("combine", i, "lgd")) for i in NIVEAUX] == [
        (0.95, 0.01, 0.55), (0.99, 0.02, 0.65), (0.999, 0.03, 0.75)]
    assert scenarios.parametres("recession", "extreme")["quantile"]["statut"] == "publiee"
    assert scenarios.parametres("recession", "moderee")["quantile"]["statut"] == "hypothese"


def test_recession_redonne_l_ancien_moteur(banques):
    for b in banques:
        for niveau, ancien in zip(NIVEAUX, ("adverse", "severe", "extreme")):
            r = credit.simuler_scenario(b, scenarios.parametres("recession", niveau))
            assert r["cet1_apres"] == pytest.approx(REFERENCE[b.cle][1 + NIVEAUX.index(niveau)], abs=1e-3)
            assert r["cet1_apres"] == pytest.approx(credit.stresser_banque(b, ancien)["cet1_apres"], abs=1e-15)


def test_hausse_des_defauts_a_la_main(banques):
    # AlJazira, sévère : +5 points. Perte = 113,02961 × 0,05 × 0,45 = 2,5431662 Md ; CET1 = (15,065179 − 2,5431662) / 122,69
    r = credit.simuler_scenario(aljazira(banques), scenarios.parametres("defauts", "severe"))
    assert r["pd_stressee"] == pytest.approx(r["pd_avant"] + 0.05, abs=1e-15)
    assert r["perte_md"] == pytest.approx(113.02961 * 0.05 * 0.45, abs=1e-9)
    assert r["cet1_apres"] == pytest.approx((15.065179 - 2.5431662) / 122.69, abs=1e-8)


def test_degradation_des_actifs_a_la_main(banques):
    # même PD qu'une récession modérée ; perte multipliée par LGD / 45 %
    b = aljazira(banques)
    recession = credit.simuler_scenario(b, scenarios.parametres("recession", "moderee"))
    for niveau, lgd in zip(NIVEAUX, (0.55, 0.65, 0.75)):
        r = credit.simuler_scenario(b, scenarios.parametres("actifs", niveau))
        assert r["pd_stressee"] == pytest.approx(recession["pd_stressee"]) and r["perte"] == pytest.approx(recession["perte"] * lgd / 0.45)
        assert {c["cle"] for c in r["canaux"]} == {"crise", "garanties"}


def test_choc_combine_ordre_et_pas_de_double_comptage(banques):
    for b in banques:
        for niveau in NIVEAUX:
            p = scenarios.parametres("combine", niveau)
            r = credit.simuler_scenario(b, p)
            pd_crise = credit.pd_stressee(b.pd_depart, p["quantile"]["valeur"])
            assert r["pd_crise"] == pytest.approx(pd_crise)                                           # 1. crise générale
            assert r["pd_stressee"] == pytest.approx(pd_crise + p["hausse"]["valeur"])                # 2. défauts en plus, sur la même PD
            assert r["perte"] == pytest.approx(b.prets_bruts * (r["pd_stressee"] - b.pd_depart) * p["lgd"]["valeur"])   # 3. une seule LGD
            assert sum(c["perte"] for c in r["canaux"]) == pytest.approx(r["perte"], rel=1e-12)        # la ventilation tombe juste
            assert r["perte"] <= b.prets_sains * p["lgd"]["valeur"] + 1e-6                             # jamais plus que les prêts sains


def test_la_pd_ne_depasse_jamais_cent_pour_cent(banques):
    r = credit.simuler_banque(aljazira(banques), 0.999, 2.0, 0.75)
    assert r["pd_stressee"] == 1.0 and r["perte"] == pytest.approx(aljazira(banques).prets_sains * 0.75)


def test_intensites_ordonnees_pour_chaque_type_et_chaque_banque(banques):
    for b in banques:
        for t in TYPES:
            v = [credit.simuler_scenario(b, scenarios.parametres(t, i))["cet1_apres"] for i in NIVEAUX]
            assert v[0] > v[1] > v[2], (b.cle, t)


def test_lgd_imposee_et_refus():
    p = scenarios.parametres("actifs", "severe", 0.30)
    assert p["lgd"]["valeur"] == 0.30 and p["lgd"]["statut"] == "manuel"
    for mauvais in (("inconnu", "severe", None), ("recession", "forte", None), ("recession", "severe", 0.9)):
        with pytest.raises(ValueError):
            scenarios.parametres(*mauvais)


def test_solution_capital_a_reconstituer_a_la_main(banques):
    # AlJazira, choc combiné extrême : capital restant = 15,065179 − perte ; besoin = seuil × 122,69 − restant
    b = aljazira(banques)
    r = credit.simuler_scenario(b, scenarios.parametres("combine", "extreme"))
    restant = 15.065179 - r["perte_md"]
    assert r["besoin_7_md"] == pytest.approx(0.07 * 122.69 - restant, abs=1e-9)
    assert r["besoin_4_5_md"] == pytest.approx(0.045 * 122.69 - restant, abs=1e-9)
    assert "sous le minimum" in r["conclusion"] and "Solution" in r["conclusion"]
    apres = (restant + r["besoin_7_md"]) / 122.69
    assert apres == pytest.approx(0.07, abs=1e-12)                                   # reconstituer ce capital redonne exactement 7 %
    solide = credit.simuler_scenario(b, scenarios.parametres("recession", "moderee"))
    assert solide["besoin_7_md"] == 0 and solide["besoin_4_5_md"] == 0 and "résiste" in solide["conclusion"]
    coussin = credit.simuler_scenario(b, scenarios.parametres("recession", "extreme"))
    assert coussin["besoin_4_5_md"] == 0 and coussin["besoin_7_md"] > 0 and "sous 7 %" in coussin["conclusion"]


def test_conclusion_de_la_comparaison(banques):
    comp = credit.comparer_scenario(banques, scenarios.parametres("combine", "extreme"))
    c = comp["conclusion"]
    pire = min(comp["resultats"], key=lambda r: r["cet1_apres"])
    assert c["sous_7"] == 8 and c["sous_4_5"] == 7 and c["pire"] == pire["cle"] == "saib"
    assert c["besoin_7_md"] == pytest.approx(sum(r["besoin_7_md"] for r in comp["resultats"])) and "Solution" in c["texte"]
    assert pire["cet1_apres"] < 0 and "dépassent tout son capital" in pire["conclusion"] and "−0,03 %" in c["texte"]
    calme = credit.comparer_scenario(banques, scenarios.parametres("recession", "moderee"))["conclusion"]
    assert calme["besoin_7_md"] == 0 and "Aucun capital" in calme["texte"]


def test_route_scenario_type_et_intensite(client, utilisateur):
    u = utilisateur()
    r = client.post("/api/v1/stress/reelles/comparer", json={"type": "combine", "intensite": "extreme", "banques": ["aljazira", "snb"]}, headers=u.h)
    assert r.status_code == 200
    j = r.json()
    assert j["parametres"]["lgd"]["valeur"] == 0.75 and j["parametres"]["hausse"]["statut"] == "hypothese"
    assert all(x["parametres"]["type"] == "combine" for x in j["resultats"]) and len(j["resultats"]) == 2
    rec = client.post("/api/v1/stress/reelles/comparer", json={"type": "recession", "intensite": "moderee", "banques": ["aljazira"]}, headers=u.h).json()
    assert rec["resultats"][0]["cet1_apres"] == pytest.approx(0.11130, abs=1e-3)
    imp = client.post("/api/v1/stress/reelles/comparer", json={"type": "recession", "intensite": "severe", "lgd": 0.6}, headers=u.h).json()
    assert imp["parametres"]["lgd"]["statut"] == "manuel" and len(imp["resultats"]) == 9
    for corps in ({"type": "covid"}, {"type": "recession", "intensite": "forte"}, {"type": "recession", "lgd": 0.1}):
        assert client.post("/api/v1/stress/reelles/comparer", json=corps, headers=u.h).status_code == 422
    assert {t["cle"] for t in client.get("/api/v1/stress/reelles/banques", headers=u.h).json()["catalogue"]["types"]} == set(TYPES)
