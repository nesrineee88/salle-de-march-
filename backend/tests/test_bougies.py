"""Bougies en unités de temps (1 min à 1 jour) construites à partir des ticks simulés, sans regarder le futur."""
from datetime import datetime

import numpy as np
import pytest

from app.analyse.bougies import UNITES, bougies_seance

from .test_portefeuille_api import aller

# Séance de 10 minutes, 3 ticks : 14:30 → 100, 14:35 → 110, 14:40 → 90 (prix linéaire entre deux ticks, comme le moteur).
DEBUT, FIN = datetime(2020, 3, 2, 14, 30), datetime(2020, 3, 2, 14, 40)
CHEMIN = np.array([100.0, 110.0, 90.0])
APRES = datetime(2020, 3, 2, 22, 0)
ts = lambda d: int((d - datetime(1970, 1, 1)).total_seconds())  # noqa: E731


def _ohlc(b):
    return tuple(round(b[k], 6) for k in ("open", "high", "low", "close"))


def test_cinq_minutes_a_la_main():
    b = bougies_seance(DEBUT, FIN, CHEMIN, APRES, UNITES["5min"])
    assert [x["t"] for x in b] == [ts(DEBUT), ts(datetime(2020, 3, 2, 14, 35))]
    assert _ohlc(b[0]) == (100, 110, 100, 110)
    assert _ohlc(b[1]) == (110, 110, 90, 90)
    assert not any(x["en_formation"] for x in b)


def test_une_minute_suit_l_interpolation():
    b = bougies_seance(DEBUT, FIN, CHEMIN, APRES, UNITES["1min"])
    assert len(b) == 10
    assert _ohlc(b[1]) == (102, 104, 102, 104)          # 14:31 → 14:32 : de 102 à 104 (+2 par minute)
    assert _ohlc(b[6]) == (106, 106, 102, 102)          # 14:36 → 14:37 : de 106 à 102 (−4 par minute)
    assert _ohlc(b[7]) == (102, 102, 98, 98)            # 14:37 → 14:38


def test_une_heure_contient_le_tick_interieur():
    (b,) = bougies_seance(DEBUT, FIN, CHEMIN, APRES, UNITES["1h"])
    assert b["t"] == ts(datetime(2020, 3, 2, 14, 0))     # alignée sur l'heure pleine (UTC)
    assert _ohlc(b) == (100, 110, 90, 90)


def test_pas_de_regard_sur_le_futur():
    # À 14:37:30, la deuxième bougie s'arrête au prix de cet instant (110 → 100) et elle est marquée « en formation ».
    b = bougies_seance(DEBUT, FIN, CHEMIN, datetime(2020, 3, 2, 14, 37, 30), UNITES["5min"])
    assert len(b) == 2 and _ohlc(b[1]) == (110, 110, 100, 100) and b[1]["en_formation"] is True
    assert bougies_seance(DEBUT, FIN, CHEMIN, datetime(2020, 3, 2, 14, 0), UNITES["5min"]) == []     # avant l'ouverture


def test_api_bougies_intrajournalieres(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-20T16:00:00")
    r = client.get("/api/v1/bougies/TST?unite=15min&barres=40", headers=u.h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["intrajournalier"] is True and len(d["bougies"]) == 40
    t = [b["t"] for b in d["bougies"]]
    assert t == sorted(t) and all(b % 900 == 0 for b in t)
    assert t[-1] <= ts(datetime(2020, 3, 20, 16, 0))                 # jamais après l'instant simulé
    assert all(b["volume"] is None for b in d["bougies"])             # volume intrajournalier non inventé
    assert set(d["indicateurs"]) >= {"rsi", "macd", "sma_courte"} and len(d["indicateurs"]["rsi"]) == 40
    assert d["pas_ticks_s"] == pytest.approx((6.5 * 3600) / 95)


def test_api_bougies_jour_et_erreurs(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-20T16:00:00")
    d = client.get("/api/v1/bougies/TST?unite=1j&barres=10", headers=u.h).json()
    assert d["intrajournalier"] is False and len(d["bougies"]) == 10 and d["bougies"][0]["volume"] is not None
    assert client.get("/api/v1/bougies/TST?unite=3min", headers=u.h).status_code == 422
    assert client.get("/api/v1/bougies/INCONNU?unite=1h", headers=u.h).status_code in (404, 503)


def test_api_bougies_renvoie_les_niveaux(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-20T16:00:00")
    n = client.get("/api/v1/bougies/TST?unite=1j&barres=50", headers=u.h).json()["niveaux"]
    assert set(n) == {"supports_resistances", "cassures", "tendances", "fibonacci"}
    assert n["fibonacci"] is None or len(n["fibonacci"]["niveaux"]) == 7
    assert all(x["type"] in ("support", "resistance") and x["touches"] >= 2 for x in n["supports_resistances"])
