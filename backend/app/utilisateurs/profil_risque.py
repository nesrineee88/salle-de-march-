"""Questionnaire de profil de risque (pédagogique : ce n'est pas un conseil en investissement).

Le résultat alimente le stress test personnel (Sprint 5) : la perte maximale tolérée déclarée est
comparée à la perte simulée du portefeuille réel du trader.
"""
from __future__ import annotations

QUESTIONS = [
    {"id": "q1", "texte": "Quel est votre horizon de placement habituel ?",
     "choix": ["Moins d'un an", "1 à 3 ans", "3 à 10 ans", "Plus de 10 ans"]},
    {"id": "q2", "texte": "Votre portefeuille perd 15 % en un mois. Que faites-vous ?",
     "choix": ["Je vends tout", "Je vends une partie", "Je ne fais rien", "J'achète davantage"]},
    {"id": "q3", "texte": "Quelle expérience avez-vous des marchés financiers ?",
     "choix": ["Aucune", "Quelques notions", "Je suis déjà investi", "Je trade régulièrement"]},
    {"id": "q4", "texte": "Quelle part de vos économies seriez-vous prêt à exposer au risque ?",
     "choix": ["Moins de 10 %", "10 à 25 %", "25 à 50 %", "Plus de 50 %"]},
    {"id": "q5", "texte": "Qu'est-ce qui vous attire le plus ?",
     "choix": ["Protéger mon capital", "Un revenu régulier", "Une croissance modérée", "Une forte croissance"]},
    {"id": "q6", "texte": "Quelle perte maximale sur votre portefeuille pourriez-vous accepter ?",
     "choix": ["5 %", "10 %", "20 %", "35 %"]},
]
PERTE_MAX_PAR_REPONSE = {1: 5.0, 2: 10.0, 3: 20.0, 4: 35.0}
CATEGORIES = [(9, "prudent"), (14, "équilibré"), (19, "dynamique"), (24, "audacieux")]


class ReponsesInvalides(ValueError):
    pass


def evaluer_profil(reponses: dict[str, int]) -> dict:
    attendues = {q["id"] for q in QUESTIONS}
    if set(reponses) != attendues:
        raise ReponsesInvalides("Il faut répondre aux 6 questions (q1 à q6), ni plus ni moins.")
    for qid, v in reponses.items():
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 4:
            raise ReponsesInvalides(f"Réponse invalide pour {qid} : un entier de 1 à 4 est attendu.")
    score = sum(reponses.values())
    categorie = next(nom for plafond, nom in CATEGORIES if score <= plafond)
    return {
        "reponses": dict(reponses),
        "score": score,
        "categorie": categorie,
        "perte_max_toleree_pct": PERTE_MAX_PAR_REPONSE[reponses["q6"]],
    }
