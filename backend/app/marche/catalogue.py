"""Catalogue des actifs, lu depuis data/univers.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from pathlib import Path

import yaml

CLASSES = {"action", "crypto", "matiere", "indice"}
CALENDRIERS = {"semaine", "continu"}


class CatalogueInvalide(ValueError):
    pass


@dataclass(frozen=True)
class Actif:
    symbole: str
    nom: str
    classe: str
    secteur: str
    calendrier: str                       # "semaine" (lun-ven) ou "continu" (7j/7)
    devise: str = "USD"
    negatif_ok: bool = False              # certains prix peuvent légitimement être négatifs (WTI, avril 2020)
    tradable: bool = True
    session_utc: tuple[time, time] | None = None   # None = toute la journée

    @property
    def fichier(self) -> str:
        """Nom de fichier sûr : « CL=F » -> « CL_F.csv », « ^GSPC » -> « idx_GSPC.csv »."""
        s = self.symbole.replace("^", "idx_").replace("=", "_")
        return f"{s}.csv"


@dataclass(frozen=True)
class Univers:
    debut: date
    fin: date
    historique_prealable_jours: int
    actifs: dict[str, Actif]

    def __iter__(self):
        return iter(self.actifs.values())

    def __getitem__(self, symbole: str) -> Actif:
        return self.actifs[symbole]

    def __contains__(self, symbole: str) -> bool:
        return symbole in self.actifs


def _heure(texte: str) -> time:
    h, m = texte.split(":")
    return time(int(h), int(m))


def _date(valeur) -> date:
    return valeur if isinstance(valeur, date) else date.fromisoformat(str(valeur))


def charger_univers(chemin: str | Path) -> Univers:
    brut = yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))
    fenetre = brut["fenetre"]
    debut, fin = _date(fenetre["debut"]), _date(fenetre["fin"])
    if debut >= fin:
        raise CatalogueInvalide("fenetre.debut doit précéder fenetre.fin")
    sessions = {
        classe: (_heure(h[0]), _heure(h[1]))
        for classe, h in (brut.get("sessions_utc") or {}).items()
    }
    actifs: dict[str, Actif] = {}
    for entree in brut["actifs"]:
        symbole = str(entree["symbole"])
        if symbole in actifs:
            raise CatalogueInvalide(f"symbole en double : {symbole}")
        if entree["classe"] not in CLASSES:
            raise CatalogueInvalide(f"{symbole} : classe inconnue « {entree['classe']} »")
        if entree["calendrier"] not in CALENDRIERS:
            raise CatalogueInvalide(f"{symbole} : calendrier inconnu « {entree['calendrier']} »")
        actifs[symbole] = Actif(
            symbole=symbole,
            nom=entree["nom"],
            classe=entree["classe"],
            secteur=entree["secteur"],
            calendrier=entree["calendrier"],
            devise=entree.get("devise", "USD"),
            negatif_ok=bool(entree.get("negatif_ok", False)),
            tradable=bool(entree.get("tradable", True)),
            session_utc=sessions.get(entree["classe"]),
        )
    return Univers(
        debut=debut,
        fin=fin,
        historique_prealable_jours=int(fenetre.get("historique_prealable_jours", 0)),
        actifs=actifs,
    )
