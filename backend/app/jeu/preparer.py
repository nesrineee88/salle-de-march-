"""Fabrique les fichiers du jeu. À ne lancer que pour les refaire (demande internet) :

    python -m app.jeu.preparer [--force]

Le jeu lui-même ne télécharge jamais rien.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timedelta, timezone

from .catalogue import FILMS
from .donnees import DOSSIER, controler, debut_telechargement, empreinte

VIX = "^VIX"


def telecharger(symbole: str, debut, fin) -> dict:
    import yfinance as yf                                   # import tardif : seulement ici

    df = yf.download(symbole, start=debut.isoformat(), end=(fin + timedelta(days=1)).isoformat(),
                     auto_adjust=True, progress=False)
    if not len(df):
        raise RuntimeError(f"{symbole} : réponse vide")
    if getattr(df.columns, "nlevels", 1) > 1:
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "Close"]].dropna()
    return {j.date(): (float(o), float(c)) for j, (o, c) in zip(df.index, df.itertuples(index=False, name=None))}


def preparer(force: bool = False) -> int:
    DOSSIER.mkdir(exist_ok=True)
    chemin_sources = DOSSIER / "SOURCES.json"
    sources = json.loads(chemin_sources.read_text(encoding="utf-8")) if chemin_sources.exists() else {"films": {}}
    code = 0
    for fid, film in FILMS.items():
        chemin = DOSSIER / f"{fid}.csv"
        if chemin.exists() and not force:
            print(f"{fid} : déjà figé")
            continue
        symboles = {a.cle: a.symbole for a in film.actifs}
        if film.peur[0] == "vix":
            symboles[film.peur[1]] = VIX
        series = {cle: telecharger(s, debut_telechargement(film), film.fin) for cle, s in symboles.items()}
        defauts = controler(film, series)
        if defauts:
            print(f"{fid} : REFUSÉ, {'; '.join(defauts)}")
            code = 1
            continue
        with chemin.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["date", "cle", "open", "close"])
            for cle, serie in series.items():
                for jour in sorted(serie):
                    w.writerow([jour.isoformat(), cle, f"{serie[jour][0]:.8g}", f"{serie[jour][1]:.8g}"])
        sources["films"][fid] = {
            "source": "Yahoo Finance via yfinance, cours ajustés des dividendes", "symboles": symboles,
            "periode": [film.debut.isoformat(), film.fin.isoformat()],
            "telecharge_le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sha256": empreinte(chemin),
        }
        print(f"{fid} : contrôlé et figé")
    chemin_sources.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(preparer("--force" in sys.argv[1:]))
