"""Indicateurs techniques : valeurs vérifiables à la main, absence de fuite du futur, route de l'API."""
import numpy as np
import pytest

from app.analyse import indicateurs as ind

nan = np.nan


def egal(a, b, tol=1e-9):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    assert a.shape == b.shape
    assert np.array_equal(np.isnan(a), np.isnan(b)), f"{a} != {b}"
    assert np.allclose(a[~np.isnan(a)], b[~np.isnan(b)], atol=tol)


# ------------------------------------------------------------------ calculs à la main
def test_sma():
    egal(ind.sma([1, 2, 3, 4, 5], 3), [nan, nan, 2, 3, 4])


def test_ema_amorcee_par_une_moyenne_simple():
    # amorce : (1+2+3)/3 = 2 ; puis 0,5 × 4 + 0,5 × 2 = 3 ; puis 0,5 × 5 + 0,5 × 3 = 4
    egal(ind.ema([1, 2, 3, 4, 5], 3), [nan, nan, 2, 3, 4])


def test_bollinger_serie_constante_et_ecart_type_de_population():
    milieu, haute, basse = ind.bollinger([10, 10, 10, 10], n=3)
    egal(milieu, [nan, nan, 10, 10]); egal(haute, [nan, nan, 10, 10]); egal(basse, [nan, nan, 10, 10])
    milieu, haute, basse = ind.bollinger([1, 2, 3], n=3, k=2)
    ecart = (2 / 3) ** 0.5                                   # écart-type de la population de {1, 2, 3}
    assert milieu[2] == pytest.approx(2) and haute[2] == pytest.approx(2 + 2 * ecart) and basse[2] == pytest.approx(2 - 2 * ecart)


def test_rsi_extremes_et_valeur_calculee_a_la_main():
    assert ind.rsi(np.arange(1.0, 40.0), 14)[-1] == pytest.approx(100.0)          # que des hausses
    assert ind.rsi(np.arange(40.0, 1.0, -1), 14)[-1] == pytest.approx(0.0)        # que des baisses
    assert ind.rsi(np.full(30, 5.0), 14)[-1] == pytest.approx(50.0)               # série plate
    # clôtures 10, 11, 10, 12 avec n = 2 : amorce 50 ; puis gain moyen 1,25, perte moyenne 0,25, RS = 5
    egal(ind.rsi([10, 11, 10, 12], 2), [nan, nan, 50.0, 100 - 100 / 6])


def test_rsi_reste_entre_0_et_100_sur_une_marche_aleatoire():
    c = 100 + np.cumsum(np.random.default_rng(1).normal(0, 1, 400))
    r = ind.rsi(c, 14)
    assert np.nanmin(r) >= 0 and np.nanmax(r) <= 100


def test_macd_serie_constante_nulle_et_tendance_haussiere_positive():
    ligne, signal, histo = ind.macd(np.full(80, 7.0))
    for s in (ligne, signal, histo):
        assert np.allclose(s[~np.isnan(s)], 0.0, atol=1e-9)
    # droite de pente 1 : la ligne MACD tend vers la différence des retards des deux moyennes, (26 - 1) / 2 - (12 - 1) / 2 = 7
    ligne, signal, _ = ind.macd(np.arange(1.0, 201.0))
    assert ligne[-1] == pytest.approx(7.0, abs=1e-6) and signal[-1] == pytest.approx(7.0, abs=1e-6)
    # hausse qui accélère : la ligne passe au-dessus de son signal (momentum haussier)
    ligne, signal, histo = ind.macd(np.arange(1.0, 101.0) ** 2)
    assert ligne[-1] > signal[-1] > 0 and histo[-1] > 0


def test_atr_constante_et_ecart_d_ouverture():
    haut, bas, cloture = [11] * 20, [9] * 20, [10] * 20
    assert ind.atr(haut, bas, cloture, 14)[-1] == pytest.approx(2.0)
    # un gap : la veille clôture à 10, le lendemain tout reste entre 15 et 16 -> amplitude vraie 6, pas 1
    egal(ind.atr([11, 16], [9, 15], [10, 15.5], n=1), [2, 6])


def test_premieres_valeurs_absentes_tant_que_l_historique_est_trop_court():
    c = np.arange(1.0, 61.0)
    assert np.isnan(ind.sma(c, 20)[18]) and not np.isnan(ind.sma(c, 20)[19])
    assert np.isnan(ind.rsi(c, 14)[13]) and not np.isnan(ind.rsi(c, 14)[14])
    ligne, signal, _ = ind.macd(c)
    assert np.isnan(ligne[24]) and not np.isnan(ligne[25]) and np.isnan(signal[32]) and not np.isnan(signal[33])
    assert np.isnan(ind.atr(c + 1, c - 1, c, 14)[12]) and not np.isnan(ind.atr(c + 1, c - 1, c, 14)[13])
    assert np.all(np.isnan(ind.sma([1.0, 2.0], 5)))                                 # moins de points que la fenêtre


def test_prix_negatifs_acceptes():
    c = np.array([5.0, 2.0, -3.0, -37.63, 10.0, 12.0, 11.0])        # le WTI du 20 avril 2020
    assert ind.sma(c, 3)[3] == pytest.approx((2.0 - 3.0 - 37.63) / 3)
    assert not np.isnan(ind.rsi(c, 3)[-1])


def test_calculer_tout_aligne_sur_les_bougies_et_met_null_pour_l_absence():
    barres = [{"open": 10 + i, "high": 11 + i, "low": 9 + i, "close": 10 + i} for i in range(60)]
    r = ind.calculer_tout(barres)
    assert set(r) >= {"sma_courte", "sma_longue", "ema", "bollinger_haute", "rsi", "macd", "macd_signal", "atr"}
    assert all(len(v) == 60 for v in r.values())
    assert r["sma_courte"][0] is None and r["sma_courte"][-1] is not None
    assert r["sma_longue"][48] is None and r["sma_longue"][49] is not None


# ------------------------------------------------------------------ API
def aller(client, u, instant):
    assert client.post("/api/v1/horloge/aller-a", json={"instant": instant}, headers=u.h).status_code == 200


def test_route_indicateurs_alignee_sur_l_historique(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-10T17:00:00")
    h = client.get("/api/v1/historique/TST?barres=30", headers=u.h).json()
    r = client.get("/api/v1/indicateurs/TST?barres=30", headers=u.h)
    assert r.status_code == 200
    corps = r.json()
    assert corps["dates"] == [b["date"] for b in h]
    assert all(len(v) == len(h) for v in corps["series"].values())
    assert corps["series"]["rsi"][-1] is not None and 0 <= corps["series"]["rsi"][-1] <= 100
    assert corps["parametres"]["rsi"] == 14


def test_route_indicateurs_erreurs_et_authentification(client, utilisateur):
    u = utilisateur()
    assert client.get("/api/v1/indicateurs/TST").status_code == 401
    assert client.get("/api/v1/indicateurs/NOPE", headers=u.h).status_code == 404
    assert client.get("/api/v1/indicateurs/VIDE", headers=u.h).status_code == 503
    assert client.get("/api/v1/indicateurs/TST?barres=0", headers=u.h).status_code == 422


def test_aucune_fuite_du_futur_les_valeurs_passees_ne_changent_pas(client, utilisateur):
    """Une valeur calculée pour un jour terminé est la même, qu'on la lise ce jour-là ou plus tard."""
    u = utilisateur()
    aller(client, u, "2020-02-20T17:00:00")
    tot = client.get("/api/v1/indicateurs/TST?barres=200", headers=u.h).json()
    aller(client, u, "2020-03-10T17:00:00")
    tard = client.get("/api/v1/indicateurs/TST?barres=200", headers=u.h).json()
    communs = [d for d in tot["dates"][:-1] if d in tard["dates"]]          # sans la bougie du jour, encore en formation
    assert len(communs) > 20
    for nom, valeurs in tot["series"].items():
        a = dict(zip(tot["dates"], valeurs)); b = dict(zip(tard["dates"], tard["series"][nom]))
        for d in communs:
            assert (a[d] is None) == (b[d] is None), (nom, d)
            if a[d] is not None:
                assert a[d] == pytest.approx(b[d], abs=1e-6), (nom, d)
