import json
from datetime import date

import pandas as pd
import pytest

from app.marche.catalogue import Actif, Univers
from pipeline.telecharger import (
    normaliser_yfinance,
    telecharger_univers,
    verifier_instantane,
)


def fausse_reponse(symbole, debut, fin):
    idx = pd.DatetimeIndex(["2020-01-02", "2020-01-03"], name="Date")
    return pd.DataFrame(
        {"Open": [1.0, 2.0], "High": [2.0, 3.0], "Low": [0.5, 1.5], "Close": [1.5, 2.5], "Volume": [10, 20]},
        index=idx,
    )


def univers_mini():
    return Univers(
        date(2020, 1, 1), date(2020, 12, 31), 10,
        {
            "AAA": Actif("AAA", "A", "action", "T", "semaine"),
            "CL=F": Actif("CL=F", "WTI", "matiere", "É", "semaine", negatif_ok=True),
        },
    )


def test_normaliser_colonnes_multiindex_comme_yfinance_recent():
    df = fausse_reponse("AAA", None, None)
    df.columns = pd.MultiIndex.from_product([df.columns, ["AAA"]])
    out = normaliser_yfinance(df)
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    assert out.index.name == "date" and out.index[0] == pd.Timestamp("2020-01-02")


def test_normaliser_reponse_vide_et_colonnes_manquantes():
    assert len(normaliser_yfinance(pd.DataFrame())) == 0
    with pytest.raises(ValueError):
        normaliser_yfinance(pd.DataFrame({"Close": [1.0]}, index=pd.DatetimeIndex(["2020-01-02"])))


def test_instantane_manifest_verification_et_non_ecrasement(tmp_path):
    appels = []

    def telechargeur(symbole, debut, fin):
        appels.append(symbole)
        return normaliser_yfinance(fausse_reponse(symbole, debut, fin))

    manifest = telecharger_univers(univers_mini(), tmp_path, telechargeur)
    assert set(manifest["fichiers"]) == {"AAA.csv", "CL_F.csv"} and manifest["erreurs"] == {}
    assert verifier_instantane(tmp_path) == []

    # 2e lancement : instantané figé, aucun nouvel appel réseau
    telecharger_univers(univers_mini(), tmp_path, telechargeur)
    assert appels == ["AAA", "CL=F"]

    # --force retélécharge
    telecharger_univers(univers_mini(), tmp_path, telechargeur, force=True)
    assert len(appels) == 4

    # un fichier modifié à la main est détecté
    (tmp_path / "AAA.csv").write_text("date,open,high,low,close,volume\n2020-01-02,9,9,9,9,9\n")
    problemes = verifier_instantane(tmp_path)
    assert len(problemes) == 1 and "AAA.csv" in problemes[0]


def test_erreur_reseau_et_reponse_vide_sont_rapportees_sans_planter(tmp_path):
    def telechargeur(symbole, debut, fin):
        if symbole == "AAA":
            raise ConnectionError("réseau coupé")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    manifest = telecharger_univers(univers_mini(), tmp_path, telechargeur)
    assert "ConnectionError" in manifest["erreurs"]["AAA"]
    assert manifest["erreurs"]["CL=F"] == "réponse vide"
    assert manifest["fichiers"] == {}


def test_verifier_sans_manifest(tmp_path):
    assert "MANIFEST.json absent" in verifier_instantane(tmp_path)[0]
    json.loads("{}")
