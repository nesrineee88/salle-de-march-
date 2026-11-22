"""Collecte vérifiable des rapports Pilier 3 des banques.

    python -m pipeline.banques            toutes les banques
    python -m pipeline.banques aljazira   une seule, pour une démonstration

Pour chaque banque : lire robots.txt, télécharger le PDF, lire la page citée, retrouver chaque chiffre du CSV.
Le CSV n'est jamais modifié par ce script. Aucune information personnelle n'est envoyée.
"""
from __future__ import annotations

import csv
import hashlib
import re
import shutil
import subprocess
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlsplit

RACINE = Path(__file__).resolve().parents[2]
TABLE = RACINE / "data" / "externes" / "banques_reelles.csv"
BRUTS = RACINE / "data" / "raw" / "banques"
AGENT = "simulateur-pedagogique/1.0"
PAUSE = 2.0
CHAMPS = (("page_km1", ("cet1_capital", "actifs_ponderes")),
          ("page_cr1", ("prets_defaut", "prets_sains", "provisions", "prets_nets")))


def telecharger(url: str, sortie: Path, delai: int = 70) -> int:
    """Code HTTP. Le certificat est toujours vérifié."""
    r = subprocess.run(
        ["curl", "-sSL", "--proto", "=https", "--proto-redir", "=https", "--max-time", str(delai), "--max-filesize", "40000000",
         "-A", AGENT, "-o", str(sortie), "-w", "%{http_code}", url],
        capture_output=True, text=True)
    return int(r.stdout) if r.returncode == 0 and r.stdout.isdigit() else 0


def autorisation(url: str) -> tuple[bool, float]:
    """(autorisé, pause demandée). Un robots.txt illisible vaut refus."""
    u = urlsplit(url)
    fichier = BRUTS / f"robots-{u.netloc}.txt"
    fichier.unlink(missing_ok=True)
    code = telecharger(f"{u.scheme}://{u.netloc}/robots.txt", fichier, 15)
    if code == 404:
        return True, PAUSE
    if code != 200 or not fichier.exists():
        return False, PAUSE
    texte = fichier.read_text(encoding="utf-8", errors="replace")
    regles = urllib.robotparser.RobotFileParser()
    regles.parse([] if "<html" in texte.lower() else texte.splitlines())       # une page HTML n'est pas un robots.txt
    return regles.can_fetch(AGENT, url), max(PAUSE, float(regles.crawl_delay(AGENT) or 0))


def lecteur_pdf() -> str | None:
    git = Path("C:/Program Files/Git/mingw64/bin/pdftotext.exe")
    return shutil.which("pdftotext") or (str(git) if git.exists() else None)


def nombres_de_la_page(pdf: Path, page: int, lecteur: str) -> list[float]:
    trouves: list[float] = []
    for option in ("-layout", "-raw"):
        r = subprocess.run([lecteur, option, "-f", str(page), "-l", str(page), str(pdf), "-"], capture_output=True, timeout=60)
        texte = r.stdout.decode("latin-1")
        trouves += [float(n.replace(",", "")) for n in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", texte)]
    return trouves


def verifier(ligne: dict) -> bool:
    print(f"\n{ligne['nom']}\n  source : {ligne['source_url']}", flush=True)
    permis, pause = autorisation(ligne["source_url"])
    if not permis:
        print("  REFUSÉ ou illisible : robots.txt. Rien n'est téléchargé.")
        return False
    print(f"  robots.txt : autorisé, pause de {pause:.0f} s", flush=True)
    time.sleep(pause)
    neuf, garde = BRUTS / f"{ligne['cle']}.part", BRUTS / f"{ligne['cle']}.pdf"
    neuf.unlink(missing_ok=True)
    code = telecharger(ligne["source_url"], neuf)
    if code == 200 and neuf.exists() and neuf.read_bytes()[:4] == b"%PDF":
        neuf.replace(garde)
        print(f"  téléchargé : {garde.stat().st_size // 1024} Ko")
    elif garde.exists():
        print("  téléchargement impossible : COPIE LOCALE utilisée, pas une collecte en direct")
    else:
        print("  téléchargement impossible : NON VÉRIFIÉ")
        return False
    empreinte = hashlib.sha256(garde.read_bytes()).hexdigest()
    print("  empreinte : " + ("identique au CSV" if empreinte == ligne["sha256"] else "DIFFÉRENTE, document à relire"))
    lecteur = lecteur_pdf()
    if lecteur is None:
        print("  pdftotext absent : chiffres NON VÉRIFIÉS")
        return False
    bon = True
    for colonne_page, champs in CHAMPS:
        page = int(ligne[colonne_page])
        lus = nombres_de_la_page(garde, page, lecteur)
        for champ in champs:
            attendu = float(ligne[champ])
            present = any(abs(x - attendu) <= 1 for x in lus)            # à mille riyals près
            bon = bon and present
            print(f"  {'✓' if present else '✕'} page {page:>2}  {champ:<16} {attendu:>15,.0f}")
    return bon


def main(choix: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    BRUTS.mkdir(parents=True, exist_ok=True)
    with TABLE.open(encoding="utf-8", newline="") as f:
        lignes = [x for x in csv.DictReader(f) if not choix or x["cle"] in choix]
    if not lignes:
        print("Aucune banque avec cette clé.")
        return 2
    reussies = sum(verifier(x) for x in lignes)
    print(f"\n{reussies} banque(s) sur {len(lignes)} : chiffres retrouvés dans le document.")
    return 0 if reussies == len(lignes) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
