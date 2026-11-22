"""Lecture contrôlée de `data/externes/banques_reelles.csv` (banques RÉELLES, chiffres des rapports Pilier 3).

L'application ne télécharge rien : elle lit seulement ce fichier, produit par `python -m pipeline.banques`.
Toute ligne invalide arrête le chargement avec un message qui nomme la ligne et la colonne fautives.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

CHEMIN = Path(__file__).resolve().parents[3] / "data" / "externes" / "banques_reelles.csv"
COLONNES = ("cle", "nom", "type", "pays", "annee", "date_arrete", "devise", "unite", "cet1_capital", "actifs_ponderes", "cet1_ratio",
            "ratio_type", "prets_defaut", "prets_sains", "provisions", "prets_nets", "page_km1", "page_cr1", "source_url",
            "date_collecte", "sha256", "statut", "estime")
NUMERIQUES = ("cet1_capital", "actifs_ponderes", "cet1_ratio", "prets_defaut", "prets_sains", "provisions", "prets_nets")
STATUTS = ("a_relire", "relu")
TOLERANCE_RATIO = 0.00011        # le ratio publié est arrondi à 0,01 %
TOLERANCE_BILAN = 2              # milliers : défaut + sains − provisions − nets


class ErreurDonneesBanques(ValueError):
    pass


@dataclass(frozen=True)
class BanqueReelle:
    cle: str
    nom: str
    type: str
    pays: str
    annee: int
    date_arrete: str
    devise: str
    unite: str
    cet1_capital: float
    actifs_ponderes: float
    cet1_ratio: float
    ratio_type: str
    prets_defaut: float
    prets_sains: float
    provisions: float
    prets_nets: float
    page_km1: int
    page_cr1: int
    source_url: str
    date_collecte: str
    sha256: str
    statut: str
    estime: str

    @property
    def prets_bruts(self) -> float:
        return self.prets_defaut + self.prets_sains

    @property
    def pd_depart(self) -> float:
        """Taux de prêts en défaut (un stock), utilisé comme APPROXIMATION de la PD à un an."""
        return self.prets_defaut / self.prets_bruts

    @property
    def couverture(self) -> float:
        """Provisions / prêts en défaut."""
        return self.provisions / self.prets_defaut if self.prets_defaut else 0.0

    def en_dict(self) -> dict:
        return asdict(self) | {"prets_bruts": self.prets_bruts, "pd_depart": self.pd_depart, "couverture": self.couverture,
                               "synthetique": False}


def _ligne(n: int, d: dict) -> BanqueReelle:
    def faute(colonne: str, message: str):
        raise ErreurDonneesBanques(f"banques_reelles.csv, ligne {n}, colonne « {colonne} » : {message}")

    for c in COLONNES:
        if (d.get(c) or "").strip() == "":
            faute(c, "valeur vide")
    v: dict = {c: d[c].strip() for c in COLONNES}
    for c in NUMERIQUES:
        try:
            v[c] = float(v[c])
        except ValueError:
            faute(c, f"« {v[c]} » n'est pas un nombre")
        if v[c] < 0:
            faute(c, "valeur négative")
    for c in ("annee", "page_km1", "page_cr1"):
        try:
            v[c] = int(v[c])
        except ValueError:
            faute(c, f"« {v[c]} » n'est pas un entier")
    if v["type"] not in ("conventionnelle", "islamique"):
        faute("type", "attendu « conventionnelle » ou « islamique »")
    if v["ratio_type"] != "CET1":
        faute("ratio_type", "seul le CET1 est accepté (les seuils 4,5 % et 7 % ne valent que pour lui)")
    if v["statut"] not in STATUTS:
        faute("statut", f"attendu {' ou '.join(STATUTS)}")
    if v["unite"] not in ("milliers", "millions", "milliards"):
        faute("unite", "attendu milliers, millions ou milliards")
    if not v["source_url"].startswith("https://"):
        faute("source_url", "une adresse https est obligatoire")
    if not 0 < v["cet1_ratio"] < 0.40:
        faute("cet1_ratio", "hors de ]0 ; 0,40[ : un ratio s'écrit en fraction")
    if v["actifs_ponderes"] <= 0 or v["prets_defaut"] + v["prets_sains"] <= 0:
        faute("actifs_ponderes", "actifs pondérés ou prêts nuls")
    if abs(v["cet1_capital"] / v["actifs_ponderes"] - v["cet1_ratio"]) >= TOLERANCE_RATIO:
        faute("cet1_ratio", f"CET1 / actifs pondérés = {v['cet1_capital'] / v['actifs_ponderes']:.5f}, différent du ratio publié")
    ecart = v["prets_defaut"] + v["prets_sains"] - v["provisions"] - v["prets_nets"]
    if abs(ecart) > TOLERANCE_BILAN:
        faute("prets_nets", f"défaut + sains − provisions − nets = {ecart:,.0f} au lieu de 0")
    return BanqueReelle(**v)


def charger(chemin: Path | None = None) -> list[BanqueReelle]:
    """Toutes les banques du CSV. FileNotFoundError si le fichier manque, ErreurDonneesBanques s'il est mal formé."""
    chemin = chemin or CHEMIN
    with Path(chemin).open(encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader(f)
        manquantes = [c for c in COLONNES if c not in (lecteur.fieldnames or [])]
        if manquantes:
            raise ErreurDonneesBanques(f"banques_reelles.csv : colonnes absentes : {', '.join(manquantes)}")
        banques = [_ligne(n, d) for n, d in enumerate(lecteur, start=2)]
    cles = [b.cle for b in banques]
    doublons = sorted({c for c in cles if cles.count(c) > 1})
    if doublons:
        raise ErreurDonneesBanques(f"banques_reelles.csv : clé en double : {', '.join(doublons)}")
    if not banques:
        raise ErreurDonneesBanques("banques_reelles.csv : aucune banque")
    return banques


def resume(banques: list[BanqueReelle]) -> dict:
    """Ce qu'affiche le badge : date d'arrêté, pays, nombre de banques."""
    dates = sorted({b.date_arrete for b in banques})
    pays = sorted({b.pays for b in banques})
    return {"nb": len(banques), "dates_arrete": dates, "pays": pays, "devises": sorted({b.devise for b in banques}),
            "nb_par_type": {t: sum(b.type == t for b in banques) for t in ("islamique", "conventionnelle")},
            "nb_relues": sum(b.statut == "relu" for b in banques)}
