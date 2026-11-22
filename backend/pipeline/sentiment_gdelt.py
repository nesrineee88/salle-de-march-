"""Ton quotidien de la presse par actif, depuis le GDELT Project (API DOC 2.0, mode « timelinetone »).

    python -m pipeline.sentiment_gdelt            les actifs pas encore collectés (reprend là où il s'est arrêté)
    python -m pipeline.sentiment_gdelt TSLA BTC-USD   ces actifs, même déjà collectés

GDELT lit la presse mondiale. « Average Tone » est le ton moyen des articles du jour qui contiennent la requête :
au-dessus de 0 plutôt positif, en dessous plutôt négatif. Conditions : usage et redistribution libres, citation obligatoire
(https://www.gdeltproject.org/about.html, lu le 22/11/2026). GDELT demande au plus une requête toutes les 5 secondes.
L'application lit seulement le fichier produit : elle fonctionne sans internet.
"""
from __future__ import annotations

import csv
import io
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

RACINE = Path(__file__).resolve().parents[2]
SORTIE = RACINE / "data" / "externes" / "sentiment_gdelt.csv"
AGENT = "simulateur-pedagogique/1.0"
PAUSE = 15.0
ATTENTE_REFUS = 60.0
DEBUT, FIN = "20170101000000", "20261030235959"

# requête GDELT par actif : des noms sans ambiguïté, entre guillemets
REQUETES = {
    "AAPL": '("Apple Inc" OR "Apple shares" OR "Apple stock")', "MSFT": '"Microsoft"', "NVDA": '"Nvidia"',
    "GOOGL": '("Alphabet Inc" OR "Google")', "META": '("Meta Platforms" OR "Facebook")', "DIS": '"Disney"',
    "AMZN": '"Amazon.com"', "TSLA": '"Tesla"', "JPM": '"JPMorgan"', "BAC": '"Bank of America"', "GS": '"Goldman Sachs"',
    "XOM": '("Exxon Mobil" OR "ExxonMobil")', "CVX": '"Chevron"', "JNJ": '"Johnson & Johnson"', "PFE": '"Pfizer"',
    "UNH": '"UnitedHealth"', "PG": '"Procter & Gamble"', "KO": '"Coca-Cola"', "WMT": '"Walmart"', "CAT": '"Caterpillar"',
    "BA": '"Boeing"', "NEE": '"NextEra"',
    "BTC-USD": '"Bitcoin"', "ETH-USD": '"Ethereum"', "BNB-USD": '"Binance Coin"', "XRP-USD": '"Ripple XRP"', "ADA-USD": '"Cardano"',
    "SOL-USD": '"Solana"', "DOGE-USD": '"Dogecoin"', "LTC-USD": '"Litecoin"',
    "CL=F": '"crude oil"', "BZ=F": '"Brent crude"', "NG=F": '"natural gas prices"', "GC=F": '"gold prices"', "SI=F": '"silver prices"',
    "PL=F": '"platinum prices"', "HG=F": '"copper prices"', "ZW=F": '"wheat prices"', "ZC=F": '"corn prices"',
    "ZS=F": '"soybean prices"', "KC=F": '"coffee prices"',
}


def interroger(requete: str) -> tuple[int, str]:
    url = ("https://api.gdeltproject.org/api/v2/doc/doc?query=" + quote(f"{requete} sourcelang:english")
           + f"&mode=timelinetone&startdatetime={DEBUT}&enddatetime={FIN}&format=csv")
    r = subprocess.run(["curl", "-sSL", "--proto", "=https", "--max-time", "90", "-A", AGENT, "-w", "\n%{http_code}", url],
                       capture_output=True, timeout=120)
    texte = r.stdout.decode("utf-8-sig", "replace")
    corps, _, code = texte.rpartition("\n")
    return (int(code) if code.isdigit() else 0), corps


def lire(corps: str) -> list[tuple[str, float]]:
    lignes = list(csv.reader(io.StringIO(corps)))
    if not lignes or lignes[0][:3] != ["Date", "Series", "Value"]:
        raise ValueError(corps.strip()[:160] or "réponse vide")
    return [(d[:10], float(v)) for d, s, v in lignes[1:] if s == "Average Tone"]


def main(choix: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    existant: dict[str, list] = {}
    if SORTIE.exists():
        with SORTIE.open(encoding="utf-8", newline="") as f:
            for x in csv.DictReader(f):
                existant.setdefault(x["symbole"], []).append(x)
    cibles = choix or [x for x in REQUETES if x not in existant]
    erreurs = 0

    def ecrire() -> None:
        SORTIE.parent.mkdir(parents=True, exist_ok=True)
        temporaire = SORTIE.with_suffix(".tmp")
        with temporaire.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, ["symbole", "date", "ton", "requete", "collecte"], lineterminator="\n")
            w.writeheader()
            for cle in sorted(existant):
                w.writerows(existant[cle])
        temporaire.replace(SORTIE)

    print(f"{len(cibles)} actif(s) à collecter.", flush=True)
    for n, symbole in enumerate(cibles):
        if n:
            time.sleep(PAUSE)
        requete = REQUETES.get(symbole)
        if requete is None:
            print(f"{symbole} : pas de requête définie")
            erreurs += 1
            continue
        code, corps = interroger(requete)
        for _ in range(2):                               # trop rapide : on attend, puis on réessaie
            if code != 429:
                break
            time.sleep(ATTENTE_REFUS)
            code, corps = interroger(requete)
        try:
            if code != 200:
                raise ValueError(f"HTTP {code}")
            jours = lire(corps)
        except ValueError as exc:
            print(f"{symbole} : ÉCHEC ({exc}), anciennes valeurs gardées")
            erreurs += 1
            continue
        collecte = datetime.now().strftime("%Y-%m-%d")
        existant[symbole] = [{"symbole": symbole, "date": d, "ton": f"{v:.4f}", "requete": requete, "collecte": collecte}
                             for d, v in jours]
        ecrire()                                         # enregistré tout de suite : une coupure ne perd rien
        print(f"{symbole} : {len(jours)} jours, du {jours[0][0] if jours else '-'} au {jours[-1][0] if jours else '-'}", flush=True)
    print(f"Écrit : {SORTIE.name}, {sum(len(v) for v in existant.values())} lignes, {erreurs} échec(s).")
    return 1 if erreurs else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
