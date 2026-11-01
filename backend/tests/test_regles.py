"""Règles automatiques sur prix PLATS (le prix est constant sur chaque séance) : chaque déclenchement se vérifie à la main."""
from datetime import date

import pytest

from app.trading.modeles import ACHAT, ANNULE, EXECUTE, LIMITE, VENTE
from app.trading.salle import SalleDeMarche

from .test_trading import a, construire, plat

LUN, MAR, MER, JEU = date(2020, 1, 6), date(2020, 1, 7), date(2020, 1, 8), date(2020, 1, 9)


def salle_avec(prix_par_jour, quantite=100):
    s, _ = construire({"TST": plat(prix_par_jour)})
    s.ouvrir_compte("c", 100_000.0)
    if quantite:
        assert s.passer_ordre("c", "TST", ACHAT, quantite, a(LUN)).statut == EXECUTE
    return s


def ordres_de_regles(s):
    return [o for o in s.compte("c").ordres.values() if o.origine]


# ------------------------------------------------------------------ stop-loss
def test_stop_loss_vend_toute_la_position_au_marche_quand_le_prix_perd_30_pour_cent():
    s = salle_avec([(LUN, 100.0), (MAR, 69.0)])                    # prix de revient 100,025 : seuil 70,0175
    r = s.poser_regle("c", "TST", "stop_loss", -0.30, 1.0, a(LUN))
    assert s.avancer(a(LUN, 20)) == []                              # le prix tient encore : rien ne se passe
    nouvelles = s.avancer(a(MAR))
    c = s.compte("c")
    assert "TST" not in c.positions and r.statut == "declenchee"
    (ordre,) = ordres_de_regles(s)
    assert ordre.origine == f"regle:{r.id}" and ordre.sens == VENTE and ordre.statut == EXECUTE
    assert ordre.prix_moyen == pytest.approx(69.0 * (1 - 0.00025), rel=1e-4)       # meilleur acheteur du carnet
    assert nouvelles and nouvelles[-1].pnl == pytest.approx((ordre.prix_moyen - 100.025) * 100, rel=1e-6) and nouvelles[-1].pnl < 0
    assert "vendu 100" in r.motif and r.declenchee_le is not None


def test_stop_loss_sur_un_gap_s_execute_au_prix_du_marche_pas_au_prix_du_seuil():
    s = salle_avec([(LUN, 100.0), (MAR, 50.0)])                    # le prix saute bien en dessous du seuil (70,02)
    s.poser_regle("c", "TST", "stop_loss", -0.30, 1.0, a(LUN))
    s.avancer(a(MAR))
    (ordre,) = ordres_de_regles(s)
    assert ordre.prix_moyen == pytest.approx(50.0, rel=1e-3) and ordre.prix_moyen < 60


def test_la_regle_attend_l_ouverture_du_marche():
    s = salle_avec([(LUN, 100.0), (MAR, 69.0)])
    r = s.poser_regle("c", "TST", "stop_loss", -0.30, 1.0, a(LUN))
    s.avancer(a(MAR, 10))                                           # 10 h UTC : la séance n'est pas ouverte
    assert "TST" in s.compte("c").positions and r.active
    s.avancer(a(MAR, 17))
    assert "TST" not in s.compte("c").positions and r.statut == "declenchee"


def test_la_sortie_de_protection_passe_avant_une_vente_en_attente():
    s = salle_avec([(LUN, 100.0), (MAR, 69.0)])
    limite = s.passer_ordre("c", "TST", VENTE, 100, a(LUN, 18), type=LIMITE, prix_limite=150.0)    # réserve toute la quantité
    assert limite.ouvert
    s.poser_regle("c", "TST", "stop_loss", -0.30, 1.0, a(LUN, 18))
    s.avancer(a(MAR))
    assert limite.statut == ANNULE and "protection" in limite.motif
    assert "TST" not in s.compte("c").positions


# ------------------------------------------------------------------ prise de profit, OCO, achat complémentaire, stop suiveur
def test_prise_de_profit_partielle_et_le_stop_loss_reste_actif():
    s = salle_avec([(LUN, 100.0), (MAR, 160.0)])
    sl = s.poser_regle("c", "TST", "stop_loss", -0.30, 1.0, a(LUN))
    tp = s.poser_regle("c", "TST", "take_profit", 0.50, 0.5, a(LUN))        # seuil 150,04 ; vend la moitié
    s.avancer(a(MAR))
    c = s.compte("c")
    assert c.positions["TST"].quantite == pytest.approx(50.0) and tp.statut == "declenchee"
    assert sl.active                                                         # il reste de quoi protéger
    (ordre,) = ordres_de_regles(s)
    assert ordre.quantite == pytest.approx(50.0) and ordre.prix_moyen == pytest.approx(160 * (1 - 0.00025), rel=1e-4)


def test_oco_quand_une_regle_solde_la_position_les_autres_sont_annulees():
    s = salle_avec([(LUN, 100.0), (MAR, 160.0)])
    sl = s.poser_regle("c", "TST", "stop_loss", -0.30, 1.0, a(LUN))
    tp = s.poser_regle("c", "TST", "take_profit", 0.50, 1.0, a(LUN))
    s.avancer(a(MAR))
    assert "TST" not in s.compte("c").positions
    assert tp.statut == "declenchee" and sl.statut == "annulee" and "clôturée" in sl.motif


def test_achat_complementaire_renforce_la_position_et_met_a_jour_le_prix_de_revient():
    s = salle_avec([(LUN, 100.0), (MER, 160.0)])
    r = s.poser_regle("c", "TST", "achat_complementaire", 0.50, 0.25, a(LUN))
    s.avancer(a(MER))
    pos = s.compte("c").positions["TST"]
    assert r.statut == "declenchee" and pos.quantite == pytest.approx(125.0)
    achat = 160 * (1 + 0.00025)
    assert pos.prix_moyen == pytest.approx((100 * 100.025 + 25 * achat) / 125, rel=1e-4)
    assert "acheté 25" in r.motif


def test_achat_complementaire_refuse_faute_de_liquidites_n_est_pas_silencieux():
    s = salle_avec([(LUN, 100.0), (MER, 160.0)], quantite=0)
    s.passer_ordre("c", "TST", ACHAT, 990, a(LUN))                               # presque tout le capital
    r = s.poser_regle("c", "TST", "achat_complementaire", 0.50, 1.0, a(LUN))     # voudrait doubler la position
    s.avancer(a(MER))
    assert r.statut == "echec" and "liquidités" in r.motif and s.compte("c").positions["TST"].quantite == pytest.approx(990.0)


def test_stop_suiveur_monte_avec_le_prix_puis_sort_au_recul():
    s = salle_avec([(LUN, 100.0), (MAR, 120.0), (MER, 107.0)])
    r = s.poser_regle("c", "TST", "stop_suiveur", 0.10, 1.0, a(LUN))
    s.avancer(a(MAR))
    assert r.active and r.plus_haut == pytest.approx(120.0, rel=1e-3)               # il a suivi la hausse
    s.avancer(a(MER))                                                                # 107 <= 120 x 0,9 = 108
    assert r.statut == "declenchee" and "TST" not in s.compte("c").positions


# ------------------------------------------------------------------ validations
def test_validations_a_la_pose():
    s = salle_avec([(LUN, 100.0), (MAR, 69.0)], quantite=0)
    with pytest.raises(ValueError, match="aucune position"):
        s.poser_regle("c", "TST", "stop_loss", -0.30, 1.0, a(LUN))
    s.passer_ordre("c", "TST", ACHAT, 10, a(LUN))
    for type_, seuil, part, message in [
        ("inconnu", -0.3, 1.0, "type de règle"), ("stop_loss", 0.1, 1.0, "hors limites"), ("stop_loss", -1.2, 1.0, "hors limites"),
        ("take_profit", -0.1, 1.0, "hors limites"), ("stop_suiveur", 0.99, 1.0, "hors limites"),
        ("stop_loss", float("nan"), 1.0, "seuil invalide"), ("stop_loss", -0.3, 0.0, "part"), ("stop_loss", -0.3, 1.5, "part"),
    ]:
        with pytest.raises(ValueError, match=message):
            s.poser_regle("c", "TST", type_, seuil, part, a(LUN))
    with pytest.raises(ValueError, match="déjà dépassé"):                            # à 69, le prix perd déjà 31 %
        s.poser_regle("c", "TST", "stop_loss", -0.30, 1.0, a(MAR))
    with pytest.raises(ValueError, match="non négociable"):
        s.poser_regle("c", "IDX", "stop_loss", -0.3, 1.0, a(LUN))


def test_objectif_deja_atteint_est_refuse():
    s = salle_avec([(LUN, 100.0), (MAR, 160.0)])
    with pytest.raises(ValueError, match="déjà atteint"):
        s.poser_regle("c", "TST", "take_profit", 0.50, 1.0, a(MAR))


def test_une_seule_regle_active_par_actif_et_par_type_et_annulation():
    s = salle_avec([(LUN, 100.0), (MAR, 90.0)])
    r1 = s.poser_regle("c", "TST", "stop_loss", -0.30, 1.0, a(LUN))
    r2 = s.poser_regle("c", "TST", "stop_loss", -0.20, 1.0, a(LUN))
    assert r1.statut == "annulee" and "remplacée" in r1.motif and r2.active and r2.id == r1.id + 1
    assert s.annuler_regle("c", r2.id).statut == "annulee"
    with pytest.raises(ValueError, match="plus active"):
        s.annuler_regle("c", r2.id)
    with pytest.raises(KeyError):
        s.annuler_regle("c", 999)


def test_la_regle_s_annule_si_la_position_a_ete_vendue_a_la_main():
    s = salle_avec([(LUN, 100.0), (MAR, 69.0)])
    r = s.poser_regle("c", "TST", "stop_loss", -0.30, 1.0, a(LUN))
    assert s.passer_ordre("c", "TST", VENTE, 100, a(LUN, 18)).statut == EXECUTE
    s.avancer(a(MAR))
    assert r.statut == "annulee" and "plus de position" in r.motif and ordres_de_regles(s) == []


def test_le_stop_suiveur_ne_regarde_pas_le_passe_de_sa_pose():
    s = salle_avec([(LUN, 100.0), (MAR, 69.0), (MER, 100.0), (JEU, 85.0)])
    s.avancer(a(MAR, 18))
    r = s.poser_regle("c", "TST", "stop_suiveur", 0.10, 1.0, a(MAR, 18))            # le plus haut de départ est 69, pas 100
    assert r.plus_haut == pytest.approx(69.0, rel=1e-3)
    s.avancer(a(MER))
    assert r.active and r.plus_haut == pytest.approx(100.0, rel=1e-3) and "TST" in s.compte("c").positions
    s.avancer(a(JEU))                                                                # 85 <= 100 x 0,9
    assert r.statut == "declenchee" and "TST" not in s.compte("c").positions


# ------------------------------------------------------------------ persistance
def test_export_import_conserve_regles_et_origine_des_ordres():
    s = salle_avec([(LUN, 100.0), (MAR, 160.0)])
    s.poser_regle("c", "TST", "stop_loss", -0.30, 1.0, a(LUN))
    s.poser_regle("c", "TST", "take_profit", 0.50, 0.5, a(LUN))
    s.avancer(a(MAR))
    etat = s.exporter("c")
    s2, _ = construire({"TST": plat([(LUN, 100.0), (MAR, 160.0)])})
    s2.ouvrir_compte("c", 100_000.0)
    s2.importer("c", etat)
    assert [(r.id, r.type, r.statut, r.part) for r in s2.compte("c").regles.values()] == \
           [(r["id"], r["type"], r["statut"], r["part"]) for r in etat["regles"]]
    assert [o.origine for o in s2.compte("c").ordres.values() if o.origine] == ["regle:2"]
    nouvelle = s2.poser_regle("c", "TST", "stop_suiveur", 0.1, 1.0, a(MAR))
    assert nouvelle.id == 3                                                           # la numérotation continue
