"""Sentiment d'un texte financier par lexique (français et anglais).

C'est volontairement simple et **explicable** : on compte des mots positifs et négatifs (les plus forts comptent double), une négation
juste avant un mot inverse son sens. Un tel lexique ne comprend ni l'ironie ni le contexte : il se trompe sur les phrases
subtiles. Sa précision doit être mesurée (voir `python -m pipeline sentiment-evaluer`), jamais supposée.
Score : (positifs − négatifs) / (positifs + négatifs + 1), entre −1 et +1."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

SEUIL = 0.15            # au-delà : positif ; en deçà de −0,15 : négatif ; entre les deux : neutre

# poids 2 = mot fort. Les mots sont donnés sans accent, en minuscules.
POSITIFS = {
    "bondit": 2, "bondissent": 2, "grimpe": 1, "grimpent": 1, "s'envole": 2, "solides": 1, "robustes": 1, "records": 2,
    "hausse": 1, "hausses": 1, "monte": 1, "montent": 1, "progresse": 1, "progression": 1, "rebond": 1, "rebondit": 1, "rebondissent": 1,
    "reprise": 1, "gain": 1, "gains": 1, "profit": 1, "profits": 1, "benefice": 1, "benefices": 1, "croissance": 1, "record": 2,
    "bond": 2, "envol": 2, "flambee": 2, "optimisme": 1, "optimiste": 1, "confiance": 1, "solide": 1, "robuste": 1, "amelioration": 1,
    "accord": 1, "succes": 1, "efficace": 1, "soutien": 1, "relance": 1, "depasse": 1, "surperforme": 2, "dividende": 1,
    "rise": 1, "rises": 1, "rose": 1, "rally": 2, "rallies": 2, "surge": 2, "surges": 2, "soar": 2, "soars": 2, "jump": 1, "jumps": 1,
    "gain": 1, "gains": 1, "profit": 1, "growth": 1, "strong": 1, "beat": 1, "beats": 1, "upgrade": 1, "upgrades": 1, "recovery": 1,
    "recover": 1, "improve": 1, "improves": 1, "improved": 1, "optimism": 1, "optimistic": 1, "agreement": 1, "deal": 1, "boost": 1,
    "approval": 1, "approved": 1, "outperform": 2, "bullish": 2, "efficacy": 1, "positive": 1, "increase": 1, "increased": 1,
}
NEGATIFS = {
    "baisse": 1, "baisses": 1, "recule": 1, "reculent": 1, "chute": 2, "chutent": 2, "plonge": 2, "plongent": 2, "effondrement": 2,
    "s'effondre": 2, "krach": 2, "crash": 2, "panique": 2, "peur": 1, "crainte": 1, "craintes": 1, "inquietude": 1, "inquietudes": 1,
    "perte": 1, "pertes": 1, "deficit": 1, "faillite": 2, "defaut": 2, "crise": 2, "recession": 2, "inflation": 1, "guerre": 2,
    "invasion": 2, "sanction": 1, "sanctions": 1, "interdit": 1, "interdiction": 1, "tension": 1, "tensions": 1, "menace": 1,
    "incertitude": 1, "incertitudes": 1, "ralentissement": 1, "degrade": 1, "degradation": 1, "retrograde": 1, "avertissement": 1,
    "fraude": 2, "scandale": 2, "suspend": 1, "suspendu": 1, "negatif": 1, "negatifs": 1, "volatilite": 1, "tombe": 1,
    "fall": 1, "falls": 1, "fell": 1, "drop": 1, "drops": 1, "dropped": 1, "plunge": 2, "plunges": 2, "plummet": 2, "tumble": 2,
    "tumbles": 2, "slump": 2, "crash": 2, "crisis": 2, "loss": 1, "losses": 1, "weak": 1, "miss": 1, "misses": 1, "downgrade": 1,
    "downgrades": 1, "fear": 1, "fears": 1, "panic": 2, "bankruptcy": 2, "collapse": 2, "collapses": 2, "default": 2, "war": 2,
    "invasion": 2, "sanctions": 1, "ban": 1, "bans": 1, "recession": 2, "bearish": 2, "uncertainty": 1, "decline": 1, "declines": 1,
    "decrease": 1, "decreased": 1, "fraud": 2, "scandal": 2, "halt": 1, "halted": 1, "warning": 1, "cut": 1, "cuts": 1,
}
NEGATIONS = {"ne", "pas", "jamais", "sans", "aucun", "aucune", "non", "not", "no", "never", "without", "n't"}
FENETRE_NEGATION = 3

_MOT = re.compile(r"[a-z]+(?:['’][a-z]+)?|n't")


def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in sans_accents if unicodedata.category(c) != "Mn").replace("’", "'")


@dataclass(frozen=True)
class Sentiment:
    score: float
    etiquette: str                 # positif | negatif | neutre
    mots_positifs: tuple[str, ...]
    mots_negatifs: tuple[str, ...]

    def en_dict(self) -> dict:
        return {"score": round(self.score, 3), "etiquette": self.etiquette,
                "mots_positifs": list(self.mots_positifs), "mots_negatifs": list(self.mots_negatifs)}


def analyser(texte: str) -> Sentiment:
    mots = _MOT.findall(_normaliser(texte or ""))
    pos = neg = 0.0
    trouves_pos: list[str] = []
    trouves_neg: list[str] = []
    for i, mot in enumerate(mots):
        racine = mot[:-1] if mot.endswith("s") and len(mot) > 4 else mot          # pluriels : « craintes » -> « crainte »
        poids_p = POSITIFS.get(mot, 0) or POSITIFS.get(racine, 0)
        poids_n = NEGATIFS.get(mot, 0) or NEGATIFS.get(racine, 0)
        if not (poids_p or poids_n):
            continue
        nie = any(m in NEGATIONS or m.startswith("n'") for m in mots[max(0, i - FENETRE_NEGATION):i])
        if poids_p:
            if nie: neg += poids_p; trouves_neg.append(f"pas {mot}")
            else: pos += poids_p; trouves_pos.append(mot)
        if poids_n:
            if nie: pos += poids_n; trouves_pos.append(f"pas {mot}")
            else: neg += poids_n; trouves_neg.append(mot)
    score = (pos - neg) / (pos + neg + 1.0)
    etiquette = "positif" if score > SEUIL else "negatif" if score < -SEUIL else "neutre"
    return Sentiment(score, etiquette, tuple(trouves_pos), tuple(trouves_neg))
