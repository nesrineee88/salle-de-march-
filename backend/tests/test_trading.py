"""Tests du moteur de trading sur des prix PLATS (prix constant sur toute la séance) pour que chaque
chiffre soit vérifiable à la main."""
import random
from datetime import date, datetime, time, timedelta

import pandas as pd
import pytest

from app.marche.catalogue import Actif, Univers
from app.marche.moteur import MoteurMarche
from app.marche.stockage import Magasin
from app.trading.carnet import FRAIS_BPS, construire_carnet
from app.trading.modeles import ACHAT, ANNULE, EN_ATTENTE, EXECUTE, LIMITE, REJETE, STOP, VENTE
from app.trading.salle import SalleDeMarche

from .conftest import serie_synthetique

LUN, MAR, MER = date(2020, 1, 6), date(2020, 1, 7), date(2020, 1, 8)


def plat(jours_prix):
    idx = pd.DatetimeIndex([pd.Timestamp(j) for j, _ in jours_prix], name="date")
    p = [x for _, x in jours_prix]
    return pd.DataFrame({"open": p, "high": p, "low": p, "close": p, "volume": 1000.0, "corrige": False}, index=idx)


def a(j, h=17, m=0):
    return datetime(j.year, j.month, j.day, h, m)


def construire(series, extra_actifs=None):
    actifs = {
        "TST": Actif("TST", "Action", "action", "T", "semaine", session_utc=(time(14, 30), time(21, 0))),
        "CRY": Actif("CRY", "Crypto", "crypto", "T", "continu"),
        "WTI": Actif("WTI", "Pétrole", "matiere", "É", "semaine", negatif_ok=True),
        "IDX": Actif("IDX", "Indice", "indice", "I", "semaine", tradable=False),
    }
    actifs.update(extra_actifs or {})
    univers = Univers(date(2020, 1, 1), date(2020, 12, 31), 0, actifs)
    moteur = MoteurMarche(Magasin(series), univers)
    return SalleDeMarche(moteur, univers), univers


@pytest.fixture
def salle():
    s, _ = construire({"TST": plat([(LUN, 100.0), (MAR, 85.0), (MER, 98.0)])})
    s.ouvrir_compte("c", 100_000.0)
    return s


# ------------------------------------------------------------------ carnet
def test_carnet_forme_et_prix_negatif():
    c = construire_carnet("X", "action", 100.0)
    assert c.meilleur_vente == pytest.approx(100.025) and c.meilleur_achat == pytest.approx(99.975)
    assert c.spread == pytest.approx(0.05) and len(c.ventes) == len(c.achats) == 10
    assert all(x.prix < y.prix for x, y in zip(c.ventes, c.ventes[1:]))
    assert all(x.prix > y.prix for x, y in zip(c.achats, c.achats[1:]))
    neg = construire_carnet("WTI", "matiere", -37.0)
    assert neg.meilleur_vente > -37.0 > neg.meilleur_achat and neg.spread > 0


# ------------------------------------------------------------------ marché
def test_achat_au_marche_chiffres_exacts(salle):
    o = salle.passer_ordre("c", "TST", ACHAT, 10, a(LUN))
    assert o.statut == EXECUTE and o.prix_moyen == pytest.approx(100.025)
    c = salle.compte("c")
    frais = 5 * 100.025 * 10 / 1e4
    assert c.cash == pytest.approx(100_000 - 1000.25 - frais)
    assert c.positions["TST"].quantite == 10 and c.positions["TST"].prix_moyen == pytest.approx(100.025)
    assert c.frais_cumules == pytest.approx(frais)


def test_slippage_consomme_plusieurs_niveaux(salle):
    o = salle.passer_ordre("c", "TST", ACHAT, 600, a(LUN))      # niveaux : 200 + 300 + 100
    assert o.statut == EXECUTE
    ex = salle.compte("c").executions
    assert [round(e.quantite) for e in ex] == [200, 300, 100]
    attendu = (200 * 100.025 + 300 * 100.05 + 100 * 100.075) / 600
    assert o.prix_moyen == pytest.approx(attendu) and o.prix_moyen > 100.025


def test_carnet_epuise_annule_le_reste():
    s, _ = construire({"TST": plat([(LUN, 100.0)])})
    s.ouvrir_compte("riche", 1e9)
    o = s.passer_ordre("riche", "TST", ACHAT, 10_000, a(LUN))   # profondeur totale : 6500 actions
    assert o.statut == ANNULE and o.quantite_executee == pytest.approx(6500) and "reste annulé" in o.motif


def test_vente_realise_le_pnl(salle):
    salle.passer_ordre("c", "TST", ACHAT, 10, a(LUN))
    o = salle.passer_ordre("c", "TST", VENTE, 10, a(LUN, 18))
    assert o.statut == EXECUTE
    c = salle.compte("c")
    assert "TST" not in c.positions
    prix_vente = c.executions[-1].prix
    assert 99.975 <= prix_vente < 99.99                      # meilleur achat + petit impact résiduel de l'achat
    assert c.pnl_realise == pytest.approx((prix_vente - 100.025) * 10)


def test_les_executions_portent_le_gain_realise(salle):
    salle.passer_ordre("c", "TST", ACHAT, 10, a(LUN))
    salle.passer_ordre("c", "TST", VENTE, 4, a(LUN, 18))
    achat, vente = salle.compte("c").executions
    assert achat.pnl is None
    assert vente.pnl == pytest.approx((vente.prix - achat.prix) * 4)
    assert salle.compte("c").pnl_realise == pytest.approx(vente.pnl)


@pytest.mark.parametrize("q", [0, -5, float("nan"), float("inf")])
def test_quantites_invalides(salle, q):
    assert salle.passer_ordre("c", "TST", ACHAT, q, a(LUN)).statut == REJETE


def test_rejets_metier(salle):
    assert "inconnu" in salle.passer_ordre("c", "ZZZ", ACHAT, 1, a(LUN)).motif
    assert "négociable" in salle.passer_ordre("c", "IDX", ACHAT, 1, a(LUN)).motif
    assert "position insuffisante" in salle.passer_ordre("c", "TST", VENTE, 1, a(LUN)).motif
    assert "liquidités" in salle.passer_ordre("c", "TST", ACHAT, 5000, a(LUN)).motif
    assert "sens invalide" in salle.passer_ordre("c", "TST", "prêt", 1, a(LUN)).motif
    assert "type" in salle.passer_ordre("c", "TST", ACHAT, 1, a(LUN), type="magique").motif
    with pytest.raises(KeyError):
        salle.passer_ordre("fantome", "TST", ACHAT, 1, a(LUN))
    assert salle.compte("c").cash == 100_000          # un rejet ne coûte rien


def test_marche_ferme_refuse_le_marche_mais_accepte_la_limite(salle):
    samedi = datetime(2020, 1, 4, 12, 0)
    assert "marché fermé" in salle.passer_ordre("c", "TST", ACHAT, 1, a(LUN, 9)).motif   # avant l'ouverture
    s, _ = construire({"TST": plat([(date(2020, 1, 3), 100.0), (LUN, 100.0)]),
                       "CRY": plat([(date(2020, 1, 4), 50.0)])})
    s.ouvrir_compte("c", 10_000)
    assert s.passer_ordre("c", "TST", ACHAT, 1, samedi).statut == REJETE
    en_attente = s.passer_ordre("c", "TST", ACHAT, 1, samedi, type=LIMITE, prix_limite=99)
    assert en_attente.statut == EN_ATTENTE
    assert s.passer_ordre("c", "CRY", ACHAT, 1, samedi).statut == EXECUTE              # crypto 7j/7


# ------------------------------------------------------------------ limite
def test_limite_attend_puis_s_execute_avec_amelioration_de_prix(salle):
    o = salle.passer_ordre("c", "TST", ACHAT, 10, a(LUN), type=LIMITE, prix_limite=99)
    assert o.statut == EN_ATTENTE and o.quantite_executee == 0
    reserve = 10 * 99 * (1 + 5e-4)
    assert salle.valorisation("c", a(LUN))["cash_disponible"] == pytest.approx(100_000 - reserve)

    nouvelles = salle.avancer(a(MAR))
    assert o.statut == EXECUTE and len(nouvelles) == 1
    assert o.prix_moyen == pytest.approx(85.02125)
    assert o.prix_moyen < 99                                  # exécuté au prix du marché, mieux que la limite
    assert nouvelles[0].instant >= o.cree_le


def test_limite_marketable_s_execute_tout_de_suite_et_respecte_la_limite(salle):
    o = salle.passer_ordre("c", "TST", ACHAT, 300, a(LUN), type=LIMITE, prix_limite=100.03)
    # seul le niveau 1 (200 actions à 100.025) respecte la limite ; le reste attend
    assert o.statut == "partiel" and o.quantite_executee == pytest.approx(200) and o.reste == pytest.approx(100)


def test_annuler_libere_la_reserve_et_ne_peut_se_faire_qu_une_fois():
    s, _ = construire({"TST": plat([(LUN, 100.0)])})
    s.ouvrir_compte("c", 10_000)
    premier = s.passer_ordre("c", "TST", ACHAT, 60, a(LUN), type=LIMITE, prix_limite=90)
    refuse = s.passer_ordre("c", "TST", ACHAT, 60, a(LUN), type=LIMITE, prix_limite=90)
    assert premier.statut == EN_ATTENTE and refuse.statut == REJETE and "liquidités" in refuse.motif
    assert s.annuler_ordre("c", premier.id).statut == ANNULE
    assert s.passer_ordre("c", "TST", ACHAT, 60, a(LUN), type=LIMITE, prix_limite=90).statut == EN_ATTENTE
    with pytest.raises(ValueError):
        s.annuler_ordre("c", premier.id)
    with pytest.raises(KeyError):
        s.annuler_ordre("c", 999)


def test_une_vente_en_attente_reserve_la_quantite(salle):
    salle.passer_ordre("c", "TST", ACHAT, 10, a(LUN))
    assert salle.passer_ordre("c", "TST", VENTE, 6, a(LUN), type=LIMITE, prix_limite=120).statut == EN_ATTENTE
    assert "position insuffisante" in salle.passer_ordre("c", "TST", VENTE, 6, a(LUN)).motif
    assert salle.passer_ordre("c", "TST", VENTE, 4, a(LUN, 18)).statut == EXECUTE


# ------------------------------------------------------------------ stop
def test_stop_loss_sur_gap_s_execute_au_prix_du_marche_pas_au_prix_du_stop(salle):
    salle.passer_ordre("c", "TST", ACHAT, 10, a(LUN))
    stop = salle.passer_ordre("c", "TST", VENTE, 10, a(LUN), type=STOP, prix_stop=90)
    assert stop.statut == EN_ATTENTE
    salle.avancer(a(LUN, 20))
    assert stop.statut == EN_ATTENTE and not stop.declenche          # lundi : 100 > 90

    salle.avancer(a(MAR))                                            # mardi : ouverture à 85, sous le stop
    assert stop.declenche and stop.statut == EXECUTE
    assert stop.prix_moyen == pytest.approx(85 - 0.02125)
    assert stop.prix_moyen < 90                                      # le gap coûte plus que prévu
    assert salle.compte("c").pnl_realise == pytest.approx((84.97875 - 100.025) * 10)


def test_stop_non_declenche_si_le_prix_reste_au_dessus():
    s, _ = construire({"TST": plat([(LUN, 100.0), (MAR, 95.0)])})
    s.ouvrir_compte("c", 100_000)
    s.passer_ordre("c", "TST", ACHAT, 10, a(LUN))
    stop = s.passer_ordre("c", "TST", VENTE, 10, a(LUN), type=STOP, prix_stop=90)
    s.avancer(a(MAR))
    assert stop.statut == EN_ATTENTE and not stop.declenche


def test_stop_deja_atteint_est_refuse(salle):
    salle.passer_ordre("c", "TST", ACHAT, 10, a(LUN))
    o = salle.passer_ordre("c", "TST", VENTE, 10, a(LUN), type=STOP, prix_stop=105)
    assert o.statut == REJETE and "déjà atteint" in o.motif
    o2 = salle.passer_ordre("c", "TST", ACHAT, 1, a(LUN), type=STOP, prix_stop=95)
    assert o2.statut == REJETE and "déjà atteint" in o2.motif


def test_stop_achat_se_declenche_a_la_hausse():
    s, _ = construire({"TST": plat([(LUN, 100.0), (MAR, 110.0)])})
    s.ouvrir_compte("c", 100_000)
    o = s.passer_ordre("c", "TST", ACHAT, 10, a(LUN), type=STOP, prix_stop=105)
    s.avancer(a(MAR))
    assert o.declenche and o.statut == EXECUTE and o.prix_moyen == pytest.approx(110.0275)


# ------------------------------------------------------------------ impact
def test_impact_de_marche_se_resorbe_avec_le_temps_et_disparait_si_le_temps_recule(salle):
    salle.passer_ordre("c", "TST", ACHAT, 600, a(LUN))
    ref0 = salle.carnet("TST", a(LUN))[0].prix_reference
    assert ref0 == pytest.approx(100.15, abs=0.01)
    ref30 = salle.carnet("TST", a(LUN, 17, 30))[0].prix_reference
    assert ref30 - 100 == pytest.approx((ref0 - 100) / 2, rel=0.02)
    ref_3h = salle.carnet("TST", a(LUN, 20, 0))[0].prix_reference
    assert ref_3h - 100 < 0.01
    assert salle.carnet("TST", a(LUN, 16))[0].prix_reference == 100.0   # avant l'ordre : impact remis à zéro


# ------------------------------------------------------------------ prix négatif
def test_achat_a_prix_negatif_ne_plante_pas_et_la_comptabilite_reste_coherente():
    s, _ = construire({"WTI": plat([(LUN, -10.0)])})
    s.ouvrir_compte("c", 10_000)
    o = s.passer_ordre("c", "WTI", ACHAT, 10, a(LUN))
    assert o.statut == EXECUTE and o.prix_moyen < 0
    assert s.compte("c").cash > 10_000 - 0.1                    # acheter à prix négatif encaisse de l'argent
    v = s.valorisation("c", a(LUN))
    assert abs(v["pnl_total"]) < 5
    lim = s.passer_ordre("c", "WTI", VENTE, 5, a(LUN), type=LIMITE, prix_limite=-8)
    assert lim.statut in (EN_ATTENTE, EXECUTE)                  # une limite négative est permise pour le WTI


def test_prix_limite_negatif_refuse_pour_un_actif_ordinaire(salle):
    assert "positif" in salle.passer_ordre("c", "TST", ACHAT, 1, a(LUN), type=LIMITE, prix_limite=-1).motif


# ------------------------------------------------------------------ comptabilité
@pytest.mark.parametrize("graine", range(8))
def test_invariants_comptables_sur_ordres_aleatoires(graine):
    rng = random.Random(graine)
    serie = serie_synthetique("2020-01-01", 40, "semaine", 100, graine)
    s, _ = construire({"TST": serie})
    s.ouvrir_compte("c", 50_000)
    jours = [d.date() for d in serie.index]
    t = datetime(jours[0].year, jours[0].month, jours[0].day, 15, 0)
    for _ in range(80):
        t += timedelta(minutes=rng.randint(10, 600))
        s.avancer(t)
        sens = rng.choice([ACHAT, VENTE])
        type_ = rng.choice(["marche", "limite", "stop"])
        cot = s._moteur.cotation("TST", t)
        px = cot.prix
        kw = {}
        if type_ == "limite":
            kw["prix_limite"] = px * rng.uniform(0.95, 1.05)
        if type_ == "stop":
            kw["prix_stop"] = px * (rng.uniform(0.9, 0.99) if sens == VENTE else rng.uniform(1.01, 1.1))
        o = s.passer_ordre("c", "TST", sens, rng.randint(1, 200), t, type=type_, **kw)
        if o.ouvert and rng.random() < 0.3:
            s.annuler_ordre("c", o.id)
    s.avancer(t + timedelta(days=3))

    c = s.compte("c")
    v = s.valorisation("c", t + timedelta(days=3))
    assert c.cash >= -1e-6                                               # jamais de découvert
    assert all(p.quantite > 0 for p in c.positions.values())
    assert v["equity"] - c.capital_initial == pytest.approx(
        c.pnl_realise + v["pnl_latent"] - c.frais_cumules, abs=1e-6)
    assert sum(e.quantite for e in c.executions if e.sens == ACHAT) - sum(
        e.quantite for e in c.executions if e.sens == VENTE) == pytest.approx(
        sum(p.quantite for p in c.positions.values()))
    for e in c.executions:                                               # aucune exécution avant la création
        assert e.instant >= c.ordres[e.ordre_id].cree_le
    assert all(0 <= o.quantite_executee <= o.quantite + 1e-9 for o in c.ordres.values())
    assert FRAIS_BPS["action"] > 0


def test_comptes():
    s, _ = construire({"TST": plat([(LUN, 100.0)])})
    s.ouvrir_compte("x", 5000)
    with pytest.raises(ValueError):
        s.ouvrir_compte("x", 5000)
    for mauvais in (0, -1, float("nan")):
        with pytest.raises(ValueError):
            s.ouvrir_compte("y", mauvais)
