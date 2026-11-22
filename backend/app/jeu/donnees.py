"""Séries des films : fichiers figés, lus sans internet, contrôlés avant d'être servis.

Un film dont un contrôle échoue est indisponible : il n'est jamais joué sur des données douteuses.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from .catalogue import FILMS, Film

DOSSIER = Path(__file__).parent / "donnees"
JOURS_AVANT = 100                  # historique avant le film, pour la peur « chute et volatilité »
SEUIL_ABERRANT = 0.60              # variation d'une séance jamais vue sur ces actifs
TROU_MAX = 5                       # jours calendaires entre deux séances


def empreinte(chemin: Path) -> str:
    """SHA-256 indépendant des fins de ligne : git peut les convertir d'une machine à l'autre."""
    return hashlib.sha256(chemin.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def lire_brut(film_id: str, dossier: Path = DOSSIER) -> dict[str, dict[date, tuple[float, float]]]:
    """clé -> jour -> (ouverture, clôture)."""
    series: dict[str, dict[date, tuple[float, float]]] = {}
    with (dossier / f"{film_id}.csv").open(encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            series.setdefault(ligne["cle"], {})[date.fromisoformat(ligne["date"])] = (float(ligne["open"]), float(ligne["close"]))
    return series


def controler(film: Film, series: dict[str, dict[date, tuple[float, float]]]) -> list[str]:
    """Quatre contrôles : trous, valeurs aberrantes, dates communes, événements au bon jour. Liste vide = tout est bon."""
    cles = [a.cle for a in film.actifs] + ([film.peur[1]] if film.peur[0] == "vix" else [])
    absentes = [c for c in cles if not series.get(c)]
    if absentes:
        return [f"séries absentes : {', '.join(absentes)}"]
    defauts = []
    jours = sorted(j for j in series[film.calendrier] if film.debut <= j <= film.fin)
    if len(jours) < 60:
        return [f"{len(jours)} séances seulement"]

    # 1. trous
    if (jours[0] - film.debut).days > TROU_MAX or (film.fin - jours[-1]).days > TROU_MAX:
        defauts.append("le film n'est pas couvert du début à la fin")
    for a, b in zip(jours, jours[1:]):
        if (b - a).days > TROU_MAX:
            defauts.append(f"trou de {(b - a).days} jours après le {a}")

    # 2. dates communes
    for cle in cles:
        manque = [j for j in jours if j not in series[cle]]
        if manque:
            defauts.append(f"{cle} : {len(manque)} séance(s) sans cours, dont le {manque[0]}")
    if defauts:
        return defauts

    # 3. valeurs aberrantes, et ouvertures recopiées (un ordre y serait exécuté à la clôture)
    for cle in cles:
        valeurs = [series[cle][j] for j in jours]
        if any(not (math.isfinite(x) and x > 0) for paire in valeurs for x in paire):
            defauts.append(f"{cle} : prix nul, négatif ou illisible")
            continue
        if cle not in {a.cle for a in film.actifs}:
            continue
        for j, (avant, (ouv, clo)) in zip(jours[1:], zip(valeurs, valeurs[1:])):
            if max(abs(ouv / avant[1] - 1), abs(clo / avant[1] - 1)) > SEUIL_ABERRANT:
                defauts.append(f"{cle} : variation de plus de {SEUIL_ABERRANT:.0%} le {j}")
        if sum(o == c for o, c in valeurs) > 0.2 * len(valeurs):
            defauts.append(f"{cle} : ouvertures recopiées sur la clôture")

    # 4. événements au bon jour
    for t in film.temoins:
        if t.jour not in jours or jours.index(t.jour) == 0:
            defauts.append(f"témoin absent : {t.cle} le {t.jour}")
            continue
        r = series[t.cle][t.jour][1] / series[t.cle][jours[jours.index(t.jour) - 1]][1] - 1
        if (t.variation < 0 and r > t.variation) or (t.variation > 0 and r < t.variation):
            defauts.append(f"événement mal calé : {t.cle} le {t.jour} ({r:+.1%})")
    for j in film.arrets:
        if j not in jours[1:-1]:
            defauts.append(f"arrêt sur image hors séance : {j}")
    return defauts


@dataclass(frozen=True)
class Bobine:
    """Un film prêt à projeter. Prix en base 100 à la première clôture : le niveau réel ne trahit pas la séance mystère."""
    film: Film
    jours: tuple[date, ...]
    ouvertures: dict[str, tuple[float, ...]]
    clotures: dict[str, tuple[float, ...]]
    peur: tuple[float, ...]            # 0 à 100
    peur_mesure: tuple[float, ...]     # ce qui la produit : VIX, ou chute depuis le plus haut de 30 jours
    scenes: tuple[tuple[int, str], ...]
    arrets: tuple[int, int, int]

    @property
    def dernier(self) -> int:
        return len(self.jours) - 1


def _borner(x: float, bas: float = 0.0, haut: float = 1.0) -> float:
    return min(haut, max(bas, x))


def _peur(film: Film, series, jours: list[date]) -> tuple[list[float], list[float]]:
    """Chaque valeur ne dépend que des séances déjà passées."""
    sorte, cle = film.peur
    if sorte == "vix":
        vix = [series[cle][j][1] for j in jours]
        return [100 * _borner((v - 12) / (70 - 12)) for v in vix], vix
    tous = sorted(series[cle])
    rang = {j: i for i, j in enumerate(tous)}
    clo = [series[cle][j][1] for j in tous]
    notes, chutes = [], []
    for j in jours:
        i = rang[j]
        chute = 1 - clo[i] / max(clo[max(0, i - 30):i + 1])
        r = [clo[k] / clo[k - 1] - 1 for k in range(max(1, i - 19), i + 1)]
        vol = 0.0
        if len(r) > 1:
            m = sum(r) / len(r)
            vol = math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(365)
        notes.append(100 * (0.7 * _borner(chute / 0.30) + 0.3 * _borner((vol - 0.35) / 0.65)))
        chutes.append(chute)
    return notes, chutes


def monter_bobine(film: Film, series) -> Bobine:
    jours = sorted(j for j in series[film.calendrier] if film.debut <= j <= film.fin)
    ouv, clo = {}, {}
    for a in film.actifs:
        base = series[a.cle][jours[0]][1]
        ouv[a.cle] = tuple(100 * series[a.cle][j][0] / base for j in jours)
        clo[a.cle] = tuple(100 * series[a.cle][j][1] / base for j in jours)

    def seance(jour: date) -> int:
        return next((i for i, j in enumerate(jours) if j >= jour), len(jours) - 1)

    notes, mesures = _peur(film, series, jours)
    return Bobine(film, tuple(jours), ouv, clo, tuple(notes), tuple(mesures),
                  tuple((seance(j), texte) for j, texte in film.scenes), tuple(seance(j) for j in film.arrets))


@dataclass(frozen=True)
class Cinematheque:
    bobines: dict[str, Bobine]
    defauts: dict[str, list[str]]


def charger(dossier: Path = DOSSIER) -> Cinematheque:
    bobines, defauts = {}, {}
    try:
        manifeste = json.loads((dossier / "SOURCES.json").read_text(encoding="utf-8"))["films"]
    except (OSError, ValueError, KeyError):
        manifeste = {}
    for fid, film in FILMS.items():
        try:
            if manifeste.get(fid, {}).get("sha256") != empreinte(dossier / f"{fid}.csv"):
                defauts[fid] = ["fichier différent de celui qui a été contrôlé"]
                continue
            series = lire_brut(fid, dossier)
            pb = controler(film, series)
            if pb:
                defauts[fid] = pb
            else:
                bobines[fid] = monter_bobine(film, series)
        except (OSError, ValueError, KeyError) as exc:
            defauts[fid] = [f"données illisibles ({type(exc).__name__})"]
    return Cinematheque(bobines, defauts)


@lru_cache
def cinematheque() -> Cinematheque:
    return charger()


def debut_telechargement(film: Film) -> date:
    return film.debut - timedelta(days=JOURS_AVANT)
