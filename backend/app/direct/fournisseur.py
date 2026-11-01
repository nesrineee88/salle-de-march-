"""Mode Direct (bêta) : prix récents de Yahoo Finance, à l'heure réelle.

Le simulateur rejoue d'ordinaire un instantané figé. En mode Direct, l'horloge de l'utilisateur suit l'heure réelle et les prix des
derniers jours (donc de « maintenant ») viennent de Yahoo Finance, rafraîchis toutes les minutes tant qu'un utilisateur est en Direct.
Les cours sont **différés** (souvent d'environ 15 minutes pour les actions américaines) et la source n'est pas officielle.
Le téléchargement réel est injectable (`telechargeur`) : tout le reste est testé avec un faux flux ; l'appel à Yahoo lui-même
n'a pas pu être exécuté depuis l'environnement de développement (réseau bloqué)."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable

import numpy as np
import pandas as pd

from ..marche.catalogue import Univers
from ..marche.moteur import MoteurMarche
from ..marche.stockage import Magasin

journal = logging.getLogger("salle_de_marche")
INTERVALLE_S = 60.0
PERIODE_YAHOO = "3mo"          # assez pour combler l'écart entre la fin de l'instantané et aujourd'hui

Telechargeur = Callable[[list[str]], "dict[str, pd.DataFrame]"]


def telechargeur_yahoo(symboles: list[str]) -> "dict[str, pd.DataFrame]":
    """Barres journalières des derniers mois (la barre du jour est partielle et son « close » est le dernier prix)."""
    import yfinance as yf                                   # import tardif : seulement pour le vrai flux

    brut = yf.download(symboles, period=PERIODE_YAHOO, interval="1d", auto_adjust=True, group_by="ticker",
                       progress=False, threads=True)
    sortie: dict[str, pd.DataFrame] = {}
    for s in symboles:
        try:
            df = brut[s] if isinstance(brut.columns, pd.MultiIndex) else brut
        except KeyError:
            continue
        df = df.rename(columns=str.lower).rename(columns={"adj close": "close"})
        if not {"open", "high", "low", "close"} <= set(df.columns):
            continue
        if "volume" not in df.columns:
            df["volume"] = 0.0
        df = df[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
        df.index = pd.DatetimeIndex(pd.to_datetime(df.index)).tz_localize(None).normalize()
        if len(df):
            sortie[s] = df
    return sortie


def flux_demonstration(magasin: Magasin) -> Telechargeur:
    """Faux flux pour tester le mode Direct sans Internet (SDM_DIRECT_DEMO=1). Les prix sont INVENTÉS : une marche au hasard
    qui prolonge l'instantané jusqu'à aujourd'hui. L'interface le signale ; ne jamais le présenter comme de vrais cours."""
    def telecharger(symboles: list[str]) -> "dict[str, pd.DataFrame]":
        aujourdhui = pd.Timestamp(datetime.now(timezone.utc).date())
        sortie = {}
        for s in symboles:
            base = magasin.series_origine().get(s)
            if base is None:
                continue
            jours = pd.date_range(base.index[-1] + pd.Timedelta(days=1), aujourdhui)
            if len(jours) == 0:
                continue
            rng = np.random.default_rng(abs(hash((s, len(jours)))) % (2**32))
            prix = float(base["close"].iloc[-1])
            lignes = []
            for _ in jours:
                ouv = prix
                prix = prix * float(np.exp(rng.normal(0, 0.01)))
                lignes.append((ouv, max(ouv, prix) * 1.003, min(ouv, prix) * 0.997, prix, 1000.0))
            # le dernier prix bouge un peu à chaque appel, comme un flux vivant
            c = lignes[-1]
            lignes[-1] = (c[0], c[1], c[2], c[3] * float(np.exp(np.random.default_rng().normal(0, 0.0005))), c[4])
            sortie[s] = pd.DataFrame(lignes, index=jours, columns=["open", "high", "low", "close", "volume"])
        return sortie
    return telecharger


class FournisseurDirect:
    def __init__(self, magasin: Magasin, moteur: MoteurMarche, univers: Univers, telechargeur: Telechargeur = telechargeur_yahoo):
        self._magasin, self._moteur, self._univers = magasin, moteur, univers
        self._telechargeur = telechargeur
        self._verrou = threading.Lock()
        self._fil: threading.Thread | None = None
        self._utilisateurs: set[int] = set()
        self.derniere_maj: datetime | None = None
        self.erreur: str | None = None
        self.nb_symboles = 0
        self.demo = False                                        # flux inventé (SDM_DIRECT_DEMO) : à signaler partout

    # ------------------------------------------------------------------ rafraîchissement
    def rafraichir(self) -> bool:
        """Télécharge et applique les barres récentes. Renvoie False (sans rien casser) si le flux échoue : les derniers prix restent servis."""
        symboles = sorted(a.symbole for a in self._univers if self._magasin.a_des_donnees(a.symbole))
        with self._verrou:
            try:
                barres = self._telechargeur(symboles)
                if not barres:
                    raise RuntimeError("Yahoo n'a renvoyé aucune donnée.")
                self._magasin.poser_direct(barres)
                self._moteur.invalider()
                self.derniere_maj = datetime.now(timezone.utc)
                self.erreur = None
                self.nb_symboles = len(barres)
                return True
            except Exception as exc:                             # réseau, quota, format : jamais bloquant
                self.erreur = f"{type(exc).__name__}: {str(exc)[:200]}"
                journal.warning("Flux Direct indisponible : %s", self.erreur)
                return False

    def etat(self) -> dict:
        age = (datetime.now(timezone.utc) - self.derniere_maj).total_seconds() if self.derniere_maj else None
        return {"derniere_maj": self.derniere_maj.isoformat(timespec="seconds") if self.derniere_maj else None,
                "age_secondes": round(age) if age is not None else None, "erreur": self.erreur,
                "nb_symboles": self.nb_symboles, "demo": self.demo, "utilisateurs_en_direct": len(self._utilisateurs)}

    # ------------------------------------------------------------------ utilisateurs en direct
    def inscrire(self, utilisateur_id: int) -> None:
        self._utilisateurs.add(utilisateur_id)
        self._demarrer_fil()

    def retirer(self, utilisateur_id: int) -> None:
        self._utilisateurs.discard(utilisateur_id)

    def _demarrer_fil(self) -> None:
        if self._fil is not None and self._fil.is_alive():
            return

        def boucle():
            while True:
                time.sleep(INTERVALLE_S)
                if self._utilisateurs:                           # personne en Direct : on ne sollicite pas Yahoo
                    self.rafraichir()

        self._fil = threading.Thread(target=boucle, name="flux-direct", daemon=True)
        self._fil.start()
