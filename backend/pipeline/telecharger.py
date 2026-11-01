"""Téléchargement de l'instantané figé (Yahoo Finance via yfinance).

Principe (docs/DECISIONS.md, D2 et D4) :
- on télécharge UNE fois, on fige les fichiers dans data/raw/ avec un MANIFEST.json (empreintes SHA-256) ;
- `verifier_instantane` permet à chaque membre de l'équipe de vérifier qu'il a les mêmes fichiers ;
- un fichier brut existant n'est jamais écrasé sans `--force`.

Ce module n'a pas pu être exécuté contre le vrai Yahoo depuis l'environnement de développement
(réseau bloqué) : les fonctions pures sont testées, le téléchargement réel doit être lancé sur
la machine d'un membre de l'équipe.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from app.marche.catalogue import Actif, Univers

from .nettoyer import fenetre_brute

COLONNES = ["open", "high", "low", "close", "volume"]
Telechargeur = Callable[[str, date, date], pd.DataFrame]


def normaliser_yfinance(df: pd.DataFrame) -> pd.DataFrame:
    """Rend un DataFrame yfinance (colonnes simples ou MultiIndex) au format open/high/low/close/volume."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLONNES, index=pd.DatetimeIndex([], name="date"))
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    out.columns = [str(c).strip().lower() for c in out.columns]
    manquantes = [c for c in COLONNES if c not in out.columns]
    if manquantes:
        raise ValueError(f"colonnes manquantes dans la réponse : {manquantes}")
    out = out[COLONNES]
    idx = pd.to_datetime(out.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    out.index = idx.normalize()
    out.index.name = "date"
    return out.sort_index()


def telechargeur_yfinance(symbole: str, debut: date, fin: date) -> pd.DataFrame:
    import yfinance as yf  # import tardif : seulement nécessaire pour le vrai téléchargement

    brut = yf.download(
        symbole,
        start=debut.isoformat(),
        end=(fin + timedelta(days=1)).isoformat(),   # `end` est exclusif chez Yahoo
        auto_adjust=True,                            # prix ajustés des splits et dividendes
        progress=False,
    )
    return normaliser_yfinance(brut)


def sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def telecharger_univers(
    univers: Univers,
    dossier_raw: Path,
    telechargeur: Telechargeur = telechargeur_yfinance,
    force: bool = False,
    symboles: list[str] | None = None,
    source: str = "yfinance",
) -> dict:
    """Télécharge les actifs manquants, puis met à jour le MANIFEST. Retourne le manifest."""
    dossier_raw.mkdir(parents=True, exist_ok=True)
    debut = fenetre_brute(univers.debut, univers.historique_prealable_jours)
    chemin_manifest = dossier_raw / "MANIFEST.json"
    manifest = (
        json.loads(chemin_manifest.read_text(encoding="utf-8"))
        if chemin_manifest.exists()
        else {"fichiers": {}}
    )

    cibles: list[Actif] = [a for a in univers if symboles is None or a.symbole in symboles]
    erreurs: dict[str, str] = {}
    for actif in cibles:
        chemin = dossier_raw / actif.fichier
        if chemin.exists() and not force:
            continue                                  # instantané figé : on ne retélécharge pas
        try:
            df = telechargeur(actif.symbole, debut, univers.fin)
        except Exception as exc:                      # réseau, symbole inconnu, quota...
            erreurs[actif.symbole] = f"{type(exc).__name__}: {exc}"
            continue
        if len(df) == 0:
            erreurs[actif.symbole] = "réponse vide"
            continue
        df.to_csv(chemin, index_label="date", float_format="%.10g")
        manifest["fichiers"][actif.fichier] = {
            "symbole": actif.symbole,
            "sha256": sha256_fichier(chemin),
            "lignes": int(len(df)),
            "premiere_date": df.index[0].date().isoformat(),
            "derniere_date": df.index[-1].date().isoformat(),
        }

    manifest.update(
        {
            "source": source,
            "auto_adjust": True,
            "fenetre_brute": [debut.isoformat(), univers.fin.isoformat()],
            "mis_a_jour_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "erreurs": erreurs,
        }
    )
    chemin_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def verifier_instantane(dossier_raw: Path) -> list[str]:
    """Compare chaque fichier au MANIFEST. Retourne la liste des problèmes (vide = tout est identique)."""
    chemin_manifest = dossier_raw / "MANIFEST.json"
    if not chemin_manifest.exists():
        return ["MANIFEST.json absent : lancer d'abord le téléchargement."]
    manifest = json.loads(chemin_manifest.read_text(encoding="utf-8"))
    problemes: list[str] = []
    for nom, info in manifest.get("fichiers", {}).items():
        chemin = dossier_raw / nom
        if not chemin.exists():
            problemes.append(f"{nom} : fichier absent")
        elif sha256_fichier(chemin) != info["sha256"]:
            problemes.append(f"{nom} : contenu différent du manifest (fichier modifié ?)")
    return problemes
