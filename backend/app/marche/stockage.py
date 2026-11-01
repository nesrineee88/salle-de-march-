"""Accès en lecture aux données propres, sans jamais révéler le futur."""
from __future__ import annotations

from bisect import bisect_left
from datetime import date
from pathlib import Path

import pandas as pd

from .catalogue import Univers


class DonneeIndisponible(LookupError):
    """Aucune donnée pour cet actif à cette date (fichier absent ou avant la première cotation)."""


class _Etat:
    """Photo des données servies : remplacée d'un bloc quand un scénario de crise change (jamais modifiée sur place)."""
    __slots__ = ("series", "dates", "lignes", "clotures")

    def __init__(self, series: dict[str, pd.DataFrame], directs: "dict[str, set[date]] | None" = None):
        self.series = {s: df.sort_index() for s, df in series.items() if len(df)}
        # Index de recherche rapide (la simulation interroge ces données des milliers de fois).
        self.dates: dict[str, list[date]] = {}
        self.lignes: dict[str, dict[date, dict]] = {}
        self.clotures: dict[str, list[float]] = {}
        for symbole, df in self.series.items():
            dates = [d.date() for d in df.index]
            self.dates[symbole] = dates
            self.clotures[symbole] = [float(x) for x in df["close"]]
            colonnes = ["open", "high", "low", "close", "volume"]
            self.lignes[symbole] = {
                d: dict(zip(colonnes, (float(v) for v in ligne)))
                for d, ligne in zip(dates, df[colonnes].itertuples(index=False, name=None))
            }
            for d in (directs or {}).get(symbole, ()):
                if d in self.lignes[symbole]:
                    self.lignes[symbole][d]["direct"] = True        # barre issue du flux en direct (mode Direct)


class Magasin:
    def __init__(self, series: dict[str, pd.DataFrame]):
        self._base = {s: df.sort_index() for s, df in series.items() if len(df)}   # prix d'origine, jamais modifiés
        self._etat = _Etat(self._base)
        self.multiplicateurs_actifs = 0                  # nombre de scénarios appliqués (information)
        self._mult: dict[str, pd.Series] = {}
        self._direct: dict[str, pd.DataFrame] = {}       # barres journalières récentes du flux en direct (après la fin de l'instantané)

    @property
    def _series(self) -> dict[str, pd.DataFrame]:
        return self._etat.series

    def appliquer_scenarios(self, multiplicateurs: "dict[str, pd.Series]") -> None:
        """Remplace les prix servis par les prix d'origine multipliés, jour par jour, par `multiplicateurs[symbole]`
        (série indexée par date ; les jours absents valent 1). Les prix d'origine restent intacts : on peut retirer un scénario.
        Les barres du flux en direct ne sont jamais multipliées."""
        self._mult = dict(multiplicateurs)
        self._reconstruire()

    def poser_direct(self, barres: "dict[str, pd.DataFrame]") -> None:
        """Enregistre les barres journalières récentes du flux en direct. Seules les dates postérieures à la dernière barre
        de l'instantané sont gardées (l'historique d'origine n'est jamais remplacé)."""
        garde = {}
        for symbole, df in barres.items():
            if symbole not in self._base or df is None or not len(df):
                continue
            df = df[["open", "high", "low", "close", "volume"]].dropna(subset=["open", "high", "low", "close"])
            df = df[df.index > self._base[symbole].index[-1]]
            if len(df):
                garde[symbole] = df.sort_index()
        self._direct = garde
        self._reconstruire()

    def a_du_direct(self) -> bool:
        return bool(self._direct)

    def _reconstruire(self) -> None:
        series, directs = {}, {}
        for symbole, df in self._base.items():
            m = self._mult.get(symbole)
            if m is not None and len(m):
                facteur = m.reindex(df.index).fillna(1.0).to_numpy()
                df = df.copy()
                for col in ("open", "high", "low", "close"):
                    df[col] = df[col].to_numpy() * facteur
            live = self._direct.get(symbole)
            if live is not None:
                colonnes = ["open", "high", "low", "close", "volume"]
                df = pd.concat([df[colonnes], live[colonnes]])
                directs[symbole] = {d.date() for d in live.index}
            series[symbole] = df
        self._etat = _Etat(series, directs)              # un seul remplacement : les lecteurs voient l'ancien ou le nouvel état

    def series_origine(self) -> dict[str, pd.DataFrame]:
        """Prix d'origine de tous les actifs (lecture seule : ne pas modifier)."""
        return self._base

    def prix_origine(self, symbole: str) -> pd.DataFrame:
        try:
            return self._base[symbole]
        except KeyError:
            raise DonneeIndisponible(f"aucune donnée chargée pour {symbole}") from None

    @classmethod
    def charger(cls, dossier_clean: Path, univers: Univers) -> "Magasin":
        series: dict[str, pd.DataFrame] = {}
        for actif in univers:
            chemin = dossier_clean / actif.fichier
            if chemin.exists():
                series[actif.symbole] = pd.read_csv(chemin, index_col="date", parse_dates=["date"])
        return cls(series)

    def disponibles(self) -> set[str]:
        return set(self._etat.series)

    def a_des_donnees(self, symbole: str) -> bool:
        return symbole in self._etat.series

    def _serie(self, symbole: str) -> pd.DataFrame:
        try:
            return self._etat.series[symbole]
        except KeyError:
            raise DonneeIndisponible(f"aucune donnée chargée pour {symbole}") from None

    def periode(self, symbole: str) -> tuple[date, date]:
        s = self._serie(symbole)
        return s.index[0].date(), s.index[-1].date()

    def barre_du_jour(self, symbole: str, jour: date) -> dict | None:
        """Barre OHLCV du jour (dict) ou None si le marché n'a pas coté ce jour-là."""
        etat = self._etat
        if symbole not in etat.series:
            self._serie(symbole)
        return etat.lignes[symbole].get(jour)

    def barres_terminees(self, symbole: str, avant: date, n: int | None = None) -> pd.DataFrame:
        """Barres STRICTEMENT antérieures au jour `avant` (la barre du jour n'est jamais terminée)."""
        s = self._serie(symbole)
        passe = s.loc[: pd.Timestamp(avant) - pd.Timedelta(days=1)]
        return passe.tail(n) if n else passe

    def derniere_cloture_avant(self, symbole: str, jour: date) -> float | None:
        etat = self._etat
        if symbole not in etat.series:
            self._serie(symbole)
        i = bisect_left(etat.dates[symbole], jour)          # nombre de barres strictement avant `jour`
        return etat.clotures[symbole][i - 1] if i > 0 else None

    def cloture_avant_derniere(self, symbole: str, jour: date) -> float | None:
        """Clôture de l'avant-dernière barre terminée avant `jour` (sert à mesurer la variation d'un marché fermé)."""
        etat = self._etat
        if symbole not in etat.series:
            self._serie(symbole)
        i = bisect_left(etat.dates[symbole], jour)
        return etat.clotures[symbole][i - 2] if i >= 2 else None
