"""Protéger son portefeuille : formules à la main, équivalence avec la bourse, rien du futur, lecture seule."""
import math

import numpy as np
import pandas as pd
import pytest

from app.protection import calcul
from app.trading import persistance


def serie(rendements, debut="2015-01-01"):
    return pd.Series(100 * np.cumprod(1 + np.asarray(rendements, dtype=float)), index=pd.bdate_range(debut, periods=len(rendements)))


def test_indemnite_a_la_main():
    assert calcul.indemnite(0.18, 0.10, 0.25) == pytest.approx(0.08)            # 50 000 × 8 % = 4 000 USD
    assert calcul.indemnite(0.05, 0.10, 0.25) == 0
    assert calcul.indemnite(0.60, 0.10, 0.25) == pytest.approx(0.25)


def test_prime_a_la_main():
    pure = 0.04 * 3000                                                          # fréquence × coût moyen
    assert pure * (1 + calcul.MARGE) / (1 - calcul.FRAIS) == pytest.approx(169.4118, abs=1e-4)


def test_l_indemnite_est_un_put_spread():
    for perte in np.linspace(-0.3, 0.9, 61):
        fin = 1 - perte
        spread = max(0.0, 0.90 - fin) - max(0.0, 0.65 - fin)
        assert calcul.indemnite(perte, 0.10, 0.25) == pytest.approx(spread)


def test_black_scholes_parite_et_bornes():
    k, vol, t = 0.9, 0.25, 0.5
    put = calcul.put_black_scholes(k, vol, t)
    d1 = (math.log(1 / k) + vol * vol * t / 2) / (vol * math.sqrt(t))
    call = calcul.NORMALE.cdf(d1) - k * calcul.NORMALE.cdf(d1 - vol * math.sqrt(t))
    assert call - put == pytest.approx(1 - k)                                    # parité call-put, taux nul
    assert calcul.put_black_scholes(1.2, 0.0, 0.5) == pytest.approx(0.2)
    assert calcul.put_black_scholes(0.0, 0.3, 0.5) == 0


def test_le_tarif_compte_les_vrais_sinistres():
    rng = np.random.default_rng(4)
    r = rng.normal(0.0002, 0.012, 1600)
    r[900:930] = -0.01                                                           # une vraie chute de 26 %
    cours = {"A": serie(r)}
    res = calcul.tarifer(cours, {"A": 50_000}, 0.10, 0.25, 91)
    assert res["tarifable"] and res["sinistres"] > 0
    assert res["prime_pure"] == pytest.approx(res["frequence"] * res["cout_moyen"])
    assert res["prime"] == pytest.approx(res["prime_pure"] * 1.2 / 0.85)
    assert res["marge"] + res["frais"] + res["prime_pure"] == pytest.approx(res["prime"])
    assert res["pire"]["perte"] >= res["pire"]["indemnite"] > 0
    assert res["pire"]["avec_assurance"] == pytest.approx(-res["pire"]["perte"] + res["pire"]["indemnite"] - res["prime"])
    plus_haute = calcul.tarifer(cours, {"A": 50_000}, 0.15, 0.25, 91)
    assert plus_haute["prime"] < res["prime"]                                    # franchise plus haute, prime plus basse


def test_sans_sinistre_on_ne_tarifie_pas():
    cours = {"A": serie(np.full(1600, 0.0003))}
    res = calcul.tarifer(cours, {"A": 10_000}, 0.10, 0.25, 30)
    assert not res["tarifable"] and res["prime"] is None and res["pire"]["avec_assurance"] is None
    assert res["prix_bourse"] >= 0


def test_historique_trop_court():
    with pytest.raises(ValueError, match="historique"):
        calcul.tarifer({"A": serie(np.zeros(40))}, {"A": 1}, 0.10, 0.25, 91)


def test_les_poids_suivent_les_valeurs_detenues():
    rng = np.random.default_rng(1)
    a, b = serie(rng.normal(0, 0.02, 1200)), serie(rng.normal(0, 0.002, 1200))
    risque = calcul.tarifer({"A": a, "B": b}, {"A": 9_000, "B": 1_000}, 0.05, 0.25, 30)
    calme = calcul.tarifer({"A": a, "B": b}, {"A": 1_000, "B": 9_000}, 0.05, 0.25, 30)
    assert risque["prix_bourse"] / risque["capital"] > calme["prix_bourse"] / calme["capital"]


def investir(client, u):
    assert client.post("/api/v1/horloge/aller-a", json={"instant": "2020-03-20T17:00:00"}, headers=u.h).status_code == 200
    for symbole, q in (("TST", 20), ("CRY", 10)):
        r = client.post("/api/v1/ordres", json={"symbole": symbole, "sens": "achat", "quantite": q, "type": "marche"}, headers=u.h)
        assert r.json()["statut"] == "execute", r.text


def test_api_vide_et_bornes(client, utilisateur):
    u = utilisateur()
    assert client.get("/api/v1/protection/devis").status_code == 401
    assert client.get("/api/v1/protection/devis", headers=u.h).json()["vide"] is True
    for q in ("franchise=0.5", "plafond=0.9", "jours=7", "perimetre=voitures"):
        assert client.get(f"/api/v1/protection/devis?{q}", headers=u.h).status_code == 422


def test_api_historique_insuffisant_et_lecture_seule(client, utilisateur, base_test):
    u = utilisateur()
    investir(client, u)
    client.post("/api/v1/horloge/pause", headers=u.h)
    with base_test.session() as s:
        avant = persistance.charger(s, u.id)
    r = client.get("/api/v1/protection/devis?jours=30", headers=u.h)
    assert r.status_code == 422 and "historique" in r.json()["detail"]          # séries de test : 60 et 90 jours
    with base_test.session() as s:
        assert persistance.charger(s, u.id) == avant


def test_api_ne_lit_que_le_passe(client, utilisateur, monkeypatch):
    u = utilisateur()
    investir(client, u)
    from app.marche.stockage import Magasin
    vu = []
    origine = Magasin.barres_terminees
    monkeypatch.setattr(Magasin, "barres_terminees", lambda self, s, avant, n=None: vu.append(avant) or origine(self, s, avant, n))
    client.get("/api/v1/protection/devis?jours=30&perimetre=crypto", headers=u.h)
    assert vu and max(vu).isoformat() <= "2020-03-20"
