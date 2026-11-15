"""Fiche descriptive d'un actif : texte de Wikipédia, avec sa source et sa date de lecture.

Rien n'est inventé : si Wikipédia ne répond pas (hors ligne, page absente), la description reste vide et la
fiche n'affiche que les données du catalogue (nom, classe, secteur, devise, période disponible).
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

_CACHE: dict[str, tuple[float, dict | None]] = {}
_DUREE_CACHE = 24 * 3600
_UA = {"User-Agent": "SalleDeMarche/1.0 (projet pédagogique ESPRIT)"}

# Titres de pages quand le nom du catalogue ne suffit pas à trouver la bonne page.
_TITRES = {"GC=F": "Or", "SI=F": "Argent (métal)", "CL=F": "Pétrole brut", "BZ=F": "Brent", "NG=F": "Gaz naturel",
           "HG=F": "Cuivre", "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "^GSPC": "S&P 500", "^IXIC": "Nasdaq Composite",
           "^DJI": "Dow Jones Industrial Average"}


def _requete(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=4) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def description_wikipedia(symbole: str, nom: str) -> dict | None:
    """Résumé de la page Wikipédia (français puis anglais). None si introuvable."""
    mis = _CACHE.get(symbole)
    if mis and time.time() - mis[0] < _DUREE_CACHE:
        return mis[1]
    titre = _TITRES.get(symbole, re.sub(r"\s+(Inc\.?|Corp\.?|Corporation|Company|Co\.)$", "", nom).strip())
    resultat = None
    for langue in ("fr", "en"):
        d = _requete(f"https://{langue}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(titre.replace(' ', '_'))}")
        if d and d.get("type") == "standard" and d.get("extract"):
            resultat = {"texte": d["extract"], "source": f"Wikipédia ({langue})",
                        "url": d.get("content_urls", {}).get("desktop", {}).get("page"),
                        "lu_le": time.strftime("%Y-%m-%d")}
            break
    if resultat or not mis:                      # un échec n'est mémorisé que brièvement (pas 24 h)
        _CACHE[symbole] = (time.time() if resultat else time.time() - _DUREE_CACHE + 600, resultat)
    return resultat
