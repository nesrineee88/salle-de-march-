"""Nettoyage des données brutes -> données propres + rapport de qualité.

Règles (voir docs/DECISIONS.md, D4 et D7) :
- le brut n'est JAMAIS modifié ; le propre est recalculable à tout moment ;
- on ne comble JAMAIS un trou par une valeur inventée : le moteur utilise le dernier prix connu ;
- tout ce qui est corrigé ou supprimé est compté dans le rapport ;
- un prix négatif n'est conservé que pour les actifs marqués `negatif_ok` (WTI, avril 2020).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.marche.catalogue import Actif

COLONNES_PRIX = ["open", "high", "low", "close"]
COLONNES = COLONNES_PRIX + ["volume"]
SEUIL_MOUVEMENT_SUSPECT = 0.50      # variation journalière à signaler (jamais supprimée)
TROU_MAX_JOURS = {"semaine": 5, "continu": 2}


@dataclass
class RapportActif:
    symbole: str
    lignes_brutes: int = 0
    lignes_propres: int = 0
    premiere_date: str | None = None
    derniere_date: str | None = None
    doublons_supprimes: int = 0
    lignes_hors_fenetre: int = 0
    lignes_vides_supprimees: int = 0
    lignes_incompletes_supprimees: int = 0
    prix_non_positifs_supprimes: int = 0
    prix_negatifs_conserves: int = 0
    barres_corrigees: int = 0
    correction_max_pct: float = 0.0      # plus grand écart (en %) entre un plus haut / plus bas d'origine et sa valeur corrigée
    volumes_manquants: int = 0
    trous_longs: list[dict] = field(default_factory=list)
    mouvements_suspects: list[dict] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    def en_dict(self) -> dict:
        return asdict(self)


def nettoyer_dataframe(
    brut: pd.DataFrame, actif: Actif, debut: date, fin: date
) -> tuple[pd.DataFrame, RapportActif]:
    """`brut` : index = dates, colonnes open/high/low/close/volume (casse libre)."""
    rapport = RapportActif(symbole=actif.symbole, lignes_brutes=len(brut))

    df = brut.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    for col in COLONNES:
        if col not in df.columns:
            df[col] = np.nan
    df = df[COLONNES].apply(pd.to_numeric, errors="coerce")

    # Index = dates calendaires sans heure ni fuseau.
    idx = pd.to_datetime(df.index, errors="coerce")
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    df.index = idx.normalize()
    df.index.name = "date"
    df = df[~df.index.isna()]

    # 1. Doublons : on garde la dernière occurrence d'une date.
    masque_doublon = df.index.duplicated(keep="last")
    rapport.doublons_supprimes = int(masque_doublon.sum())
    df = df[~masque_doublon].sort_index()

    # 2. Fenêtre (avec historique préalable déjà inclus par l'appelant dans `debut`).
    dans_fenetre = (df.index >= pd.Timestamp(debut)) & (df.index <= pd.Timestamp(fin))
    rapport.lignes_hors_fenetre = int((~dans_fenetre).sum())
    df = df[dans_fenetre]

    # 3. Lignes entièrement vides, puis lignes dont un prix manque (impossible à réparer honnêtement).
    vides = df[COLONNES_PRIX].isna().all(axis=1)
    rapport.lignes_vides_supprimees = int(vides.sum())
    df = df[~vides]
    incompletes = df[COLONNES_PRIX].isna().any(axis=1)
    rapport.lignes_incompletes_supprimees = int(incompletes.sum())
    df = df[~incompletes]

    # 4. Prix <= 0.
    non_positifs = (df[COLONNES_PRIX] <= 0).any(axis=1)
    if actif.negatif_ok:
        rapport.prix_negatifs_conserves = int(non_positifs.sum())
        if rapport.prix_negatifs_conserves:
            rapport.avertissements.append(
                f"{rapport.prix_negatifs_conserves} barre(s) avec prix <= 0 conservée(s) (cas réel autorisé)."
            )
    else:
        rapport.prix_non_positifs_supprimes = int(non_positifs.sum())
        df = df[~non_positifs]

    # 5. Cohérence OHLC : high = max(o,h,l,c), low = min(o,h,l,c). Les corrections sont comptées.
    haut = df[COLONNES_PRIX].max(axis=1)
    bas = df[COLONNES_PRIX].min(axis=1)
    corrigees = (df["high"] < haut) | (df["low"] > bas)
    rapport.barres_corrigees = int(corrigees.sum())
    if rapport.barres_corrigees:
        ecart_haut = ((haut - df["high"]) / haut.abs().replace(0, np.nan)).where(corrigees)
        ecart_bas = ((df["low"] - bas) / bas.abs().replace(0, np.nan)).where(corrigees)
        pire = np.nanmax(np.concatenate([ecart_haut.to_numpy(dtype=float), ecart_bas.to_numpy(dtype=float)]))
        rapport.correction_max_pct = round(float(pire) * 100, 4) if np.isfinite(pire) else 0.0
    df = df.assign(high=haut, low=bas, corrige=corrigees.astype(bool))

    # 6. Volume manquant -> 0 (compté). Les indices et certains futures n'ont pas de volume.
    manquants = df["volume"].isna()
    rapport.volumes_manquants = int(manquants.sum())
    df["volume"] = df["volume"].fillna(0.0)

    # 7. Trous longs et mouvements suspects : signalés, jamais « réparés ».
    seuil = TROU_MAX_JOURS[actif.calendrier]
    if len(df) > 1:
        ecarts = df.index.to_series().diff().dt.days
        for d in ecarts[ecarts > seuil].index:
            precedent = df.index[df.index.get_loc(d) - 1]
            rapport.trous_longs.append(
                {"de": precedent.date().isoformat(), "a": d.date().isoformat(), "jours": int(ecarts[d])}
            )
        precedent_close = df["close"].shift(1)
        variation = (df["close"] - precedent_close) / precedent_close.abs()
        for d, v in variation[variation.abs() > SEUIL_MOUVEMENT_SUSPECT].items():
            rapport.mouvements_suspects.append(
                {"date": d.date().isoformat(), "variation": round(float(v), 4)}
            )

    rapport.lignes_propres = len(df)
    if len(df):
        rapport.premiere_date = df.index[0].date().isoformat()
        rapport.derniere_date = df.index[-1].date().isoformat()
    else:
        rapport.avertissements.append("Aucune ligne exploitable après nettoyage.")
    df = df[COLONNES + ["corrige"]]
    return df, rapport


def fenetre_brute(debut: date, historique_prealable_jours: int) -> date:
    """Premier jour à conserver (historique préalable inclus)."""
    return debut - timedelta(days=historique_prealable_jours)
