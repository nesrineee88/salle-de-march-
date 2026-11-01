"""Test de résistance des banques : calculs vérifiés à la main, comparaison conventionnelle / islamique, test inversé, remplaçant statistique."""
import math

import pandas as pd
import pytest

from app.stress import historique, ia, modele
from app.stress.modele import Banque

AUCUN = {g: 0.0 for g in modele.GROUPES}


def banque_simple(**kw):
    base = dict(nom="B", actifs=100.0, densite_rwa=0.5, cet1=0.10, rentabilite=0.0, pd_base=0.02, lgd=0.5,
                part_groupes={"energie": 0.10, "metaux_precieux": 0, "metaux_industriels": 0, "agricole": 0}, part_trading=0.0)
    base.update(kw)
    return modele.valider_banque(base)


def test_sans_choc_et_sans_resultat_rien_ne_bouge():
    r = modele.stresser(banque_simple(), AUCUN)
    assert r["perte_brute"] == pytest.approx(0) and r["ratio_apres"] == pytest.approx(0.10) and r["statut"] == "ok"


def test_le_resultat_de_l_annee_n_est_pas_compte_dans_l_impact_immediat():
    b = banque_simple(rentabilite=0.02, cet1=0.10)
    r = modele.stresser(b, {**AUCUN, "energie": -0.30})
    assert r["ratio_apres"] < 0.10 < r["ratio_avec_resultat"]                           # 2 Md de résultat sur 50 de RWA = +4 points
    assert r["ratio_avec_resultat"] == pytest.approx(r["ratio_apres"] + 100 * 0.02 / 50)


def test_credit_a_la_main():
    # énergie −30 % : PD = 0,02 × exp(4×0,3)=0,02×3,3201=0,066402 ; LGD = 0,5×1,15 = 0,575
    # perte = 10 × (0,575×0,066402 − 0,5×0,02) = 10 × (0,0381812 − 0,01) = 0,281812 ; fonds propres 5 → 4,718188 ; ratio 4,718188 / 50
    r = modele.stresser(banque_simple(), {**AUCUN, "energie": -0.30})
    assert r["perte_brute"] == pytest.approx(0.281812, abs=1e-5)
    assert r["ratio_apres"] == pytest.approx((5 - 0.281812) / 50, abs=1e-6) and r["variation_points"] == pytest.approx((r["ratio_apres"] - 0.10) * 100)
    assert [c["cle"] for c in r["canaux"]] == ["credit_energie"]


def test_la_hausse_des_prix_aide_un_peu_mais_reste_bornee():
    r = modele.stresser(banque_simple(), {**AUCUN, "energie": 0.50})
    assert r["perte_brute"] < 0 and r["perte_brute"] > -0.20                            # multiplicateur de PD borné à 0,7
    assert modele._pd_stressee(0.02, -0.95) == pytest.approx(min(0.6, 0.02 * 8))          # plafond du multiplicateur
    assert modele._pd_stressee(0.5, -0.9) == 0.6                                           # plafond de la PD


def test_position_de_marche_gain_et_perte():
    b = banque_simple(part_groupes={g: 0 for g in modele.GROUPES}, part_trading=0.05)
    assert modele.stresser(b, {g: -0.20 for g in modele.GROUPES})["perte_brute"] == pytest.approx(100 * 0.05 * 0.20)
    assert modele.stresser(b, {g: 0.20 for g in modele.GROUPES})["perte_brute"] == pytest.approx(-1.0)


def islamique(**kw):
    base = dict(type="islamique", part_groupes={g: 0 for g in modele.GROUPES}, part_murabaha=0.2, part_stock_murabaha=0.5, part_salam=0.1, couverture_salam=0.4,
                part_istisna=0.1, repercussion_istisna=0.0, part_psia=0.0)
    base.update(kw)
    return banque_simple(**base)


def test_mourabaha_salam_istisna_a_la_main():
    chocs = {"energie": -0.2, "metaux_precieux": -0.2, "metaux_industriels": -0.2, "agricole": -0.2}
    r = modele.stresser(islamique(), chocs)
    c = {x["cle"]: x["perte"] for x in r["canaux"]}
    assert c["murabaha_stock"] == pytest.approx(20 * 0.5 * 0.2)                                 # 2,0
    assert c["salam_prix"] == pytest.approx(10 * 0.6 * 0.2)                                     # 1,2
    assert "istisna" in c and c["istisna"] == pytest.approx(0)                                  # aucun renchérissement : pas de surcoût
    chocs_hausse = {**chocs, "energie": 0.4}
    istisna = {x["cle"]: x["perte"] for x in modele.stresser(islamique(), chocs_hausse)["canaux"]}["istisna"]
    assert istisna == pytest.approx(10 * 0.5 * (min(0.6, 0.02 * math.exp(2.0 * 1.0 * 0.4)) - 0.02))
    couvert = {x["cle"]: x["perte"] for x in modele.stresser(islamique(repercussion_istisna=1.0), chocs_hausse)["canaux"]}["istisna"]
    assert couvert == pytest.approx(0)                                                          # coût entièrement répercuté


def test_partage_des_pertes_avec_les_deposants_et_risque_commercial_deplace():
    chocs = {g: -0.3 for g in modele.GROUPES}
    sans = modele.stresser(islamique(part_psia=0.0), chocs)
    avec = modele.stresser(islamique(part_psia=0.5, lissage=0.0), chocs)
    dcr = modele.stresser(islamique(part_psia=0.5, lissage=0.4), chocs)
    assert avec["perte_supportee"] == pytest.approx(sans["perte_brute"] * 0.5)                  # les déposants supportent la moitié
    assert dcr["perte_supportee"] == pytest.approx(sans["perte_brute"] * (0.5 + 0.5 * 0.4))      # la banque en absorbe 40 % : risque commercial déplacé
    assert dcr["ratio_apres"] < avec["ratio_apres"] and avec["ratio_apres"] > sans["ratio_apres"]
    assert any(c["cle"] == "partage_psia" and c["perte"] < 0 for c in avec["canaux"])


def test_statuts_et_seuils():
    b = banque_simple(cet1=0.05, densite_rwa=1.0)
    assert modele.stresser(b, AUCUN)["statut"] == "sous_coussin"                                 # 5 % : au-dessus de 4,5 mais sous 7
    assert modele.stresser(b, {**AUCUN, "energie": -0.9})["statut"] == "sous_minimum"


def test_test_inverse():
    b = banque_simple(cet1=0.08, densite_rwa=1.0, part_groupes={"energie": 0.4, "metaux_precieux": 0.1, "metaux_industriels": 0.1, "agricole": 0.1})
    r = modele.choc_inverse(b, 0.045)
    assert r["choc"] is not None and -0.95 < r["choc"] < 0
    assert modele.stresser(b, {g: r["choc"] for g in modele.GROUPES})["ratio_apres"] == pytest.approx(0.045, abs=2e-3)
    assert modele.stresser(b, {g: r["choc"] + 0.02 for g in modele.GROUPES})["ratio_apres"] > 0.045
    solide = banque_simple(cet1=0.30, part_groupes={g: 0 for g in modele.GROUPES})
    assert modele.choc_inverse(solide)["choc"] is None and "95 %" in modele.choc_inverse(solide)["message"]
    assert modele.choc_inverse(banque_simple(cet1=0.03))["choc"] == 0.0


@pytest.mark.parametrize("d, texte", [
    ({"type": "autre"}, "conventionnelle"), ({"actifs": -1}, "actifs"), ({"cet1": 2}, "CET1"), ({"inconnu": 1}, "inconnu"),
    ({"part_murabaha": 0.1}, "conventionnelle n'a ni"),
    ({"type": "islamique", "part_murabaha": 0.9, "part_salam": 0.5}, "dépasse"),
    ({"part_groupes": {"energie": 2.0}}, "Énergie"),
])
def test_banques_refusees(d, texte):
    with pytest.raises(ValueError, match=texte):
        modele.valider_banque(d)


def test_chocs_refuses():
    with pytest.raises(ValueError, match="compris entre"):
        modele.valider_chocs({"energie": -2})
    with pytest.raises(ValueError, match="Groupe inconnu"):
        modele.valider_chocs({"or": 0.1})


def test_panel_synthetique_est_valide_et_etiquete():
    p = modele.panel_synthetique()
    assert len(p) == 12 and {b.type for b in p} == {"conventionnelle", "islamique"}
    for b in p:
        modele.valider_banque(b.en_dict())
        assert "synthétique" in b.nom and b.synthetique
        r = modele.stresser(b, {g: -0.4 for g in modele.GROUPES})
        assert r["perte_brute"] > 0                                         # un choc de −40 % partout fait toujours perdre de l'argent


# ------------------------------------------------------------------ chocs historiques sur les vraies séries
def test_chocs_historiques_utilisent_les_series_du_magasin():
    from datetime import date
    from app.marche.stockage import Magasin
    idx = pd.bdate_range("2020-02-10", "2020-05-15")
    prix = pd.Series([100.0] * len(idx), index=idx)
    prix.loc["2020-03-23":] = 60.0
    df = pd.DataFrame({"open": prix, "high": prix, "low": prix, "close": prix, "volume": 1.0})
    neg = df.copy(); neg["close"] = -5.0
    m = Magasin({"CL=F": df, "GC=F": neg})
    v, utilises = historique.choc_groupe(m, ["CL=F", "BZ=F"], date(2020, 2, 19), date(2020, 4, 30))
    assert v == pytest.approx(-0.40) and utilises == ["CL=F"]                                       # BZ=F absent : ignoré
    assert historique.choc_groupe(m, ["GC=F"], date(2020, 2, 19), date(2020, 4, 30)) == (None, [])  # prix négatifs : ignorés
    f = {x["cle"]: x for x in historique.chocs_historiques(m)}
    assert f["covid_2020"]["chocs"]["energie"] == pytest.approx(-0.4) and f["covid_2020"]["chocs"]["agricole"] is None and f["covid_2020"]["notes"]


# ------------------------------------------------------------------ remplaçant statistique
def test_le_remplacant_reproduit_le_modele_structurel():
    pytest.importorskip("sklearn")
    r = ia.entrainer(1500)
    par_cle = {c["cle"]: c for c in r["comparaison"]}
    assert par_cle["boost"]["r2"] > 0.7 and par_cle["foret"]["r2"] > 0.55 and par_cle["boost"]["erreur_absolue_moyenne"] < r["ecart_type_cible"]
    assert par_cle["boost"]["r2"] > par_cle["ridge"]["r2"]                  # les interactions (exposition × choc) ne sont pas linéaires
    assert r["meilleur"] in par_cle and len(r["importance"]) == 10 and r["importance"][0]["importance"] >= r["importance"][-1]["importance"]
    b = modele.panel_synthetique()[0]
    chocs = {g: -0.3 for g in modele.GROUPES}
    e = ia.expliquer(b, chocs, "boost", 1500)
    assert abs(e["prediction_points"] - e["reference_structurelle_points"]) < 1.5 and len(e["attributions"]) == 10
    with pytest.raises(ValueError, match="inconnu"):
        ia.expliquer(b, chocs, "reseau", 1500)


# ------------------------------------------------------------------ API
def test_api(client, utilisateur):
    pytest.importorskip("sklearn")
    u = utilisateur("t@example.com", "Trader", role="trader")
    b = client.get("/api/v1/stress/banques", headers=u.h).json()
    assert len(b["banques"]) == 12 and "INVENTÉES" in b["avertissement"] and b["seuil_minimum"] == 0.045
    isl = next(x for x in b["banques"] if x["type"] == "islamique")
    r = client.post("/api/v1/stress/simuler", json={"banque": isl, "chocs": {"energie": -0.3, "agricole": -0.2}}, headers=u.h)
    assert r.status_code == 200 and r.json()["perte_brute"] > 0 and any(c["cle"].startswith("murabaha") for c in r.json()["canaux"])
    assert client.post("/api/v1/stress/simuler", json={"banque": {"cet1": 9}, "chocs": {}}, headers=u.h).status_code == 422
    c = client.post("/api/v1/stress/comparer", json={"chocs": {g: -0.3 for g in modele.GROUPES}}, headers=u.h).json()
    assert len(c["banques"]) == 12 and c["banques"][0]["variation_points"] <= c["banques"][-1]["variation_points"] and set(c["par_type"]) == {"conventionnelle", "islamique"}
    i = client.post("/api/v1/stress/inverse", json={"banque": isl}, headers=u.h).json()
    assert "minimum" in i and "coussin" in i
    assert client.get("/api/v1/stress/chocs-historiques", headers=u.h).json()["fenetres"][0]["cle"] == "petrole_2018"
    comp = client.post("/api/v1/stress/ia/comparaison", headers=u.h)
    assert comp.status_code == 200 and "référence" in comp.json()["avertissement"]
    e = client.post("/api/v1/stress/ia/explication", json={"banque": isl, "chocs": {"energie": -0.3}, "modele": "ridge"}, headers=u.h)
    assert e.status_code == 200 and e.json()["attributions"]
    assert client.post("/api/v1/stress/ia/explication", json={"banque": isl, "chocs": {}, "modele": "x"}, headers=u.h).status_code == 422


def test_ia_reservee_aux_roles_avances(client, utilisateur):
    appr = utilisateur()
    assert client.post("/api/v1/stress/ia/comparaison", headers=appr.h).status_code == 403
    assert client.get("/api/v1/stress/banques", headers=appr.h).status_code == 200
    assert client.get("/api/v1/stress/banques").status_code == 401
