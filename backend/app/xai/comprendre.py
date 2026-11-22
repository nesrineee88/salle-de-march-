"""Comprendre la question : des règles lisibles, sans modèle de langage et sans internet. Fonctions pures."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFD", texte.lower().replace("’", "'").replace("œ", "oe"))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def _a(motif: str, q: str) -> bool:
    return re.search(motif, q) is not None


# clé : (mots reconnus, définition). Le plus précis d'abord.
GLOSSAIRE: dict[str, tuple[str, str]] = {
    "stop_suiveur": (r"stop[ -]suiveur|trailing", "Un stop suiveur remonte avec le prix et ne redescend jamais. Il vend quand le prix recule du pourcentage choisi depuis son plus haut."),
    "stop": (r"stop([ -]loss)?", "Un stop vend quand le seuil est atteint. Après un saut de prix, le prix obtenu peut être nettement plus bas que le seuil."),
    "take_profit": (r"take[ -]profit|prise de profit", "Un take-profit vend quand le gain visé est atteint. Il fixe une sortie, il ne garantit pas que le prix y arrive."),
    "limite": (r"(ordre|cours) (a cours )?limites?|ordre limite", "Un ordre limite fixe votre prix maximum d’achat ou minimum de vente. Il peut ne jamais être exécuté."),
    "sharpe": (r"sharpe", "Le ratio de Sharpe rapporte le gain au risque pris : rendement au-delà du taux sans risque, divisé par la volatilité."),
    "sortino": (r"sortino", "Le ratio de Sortino ressemble au Sharpe, mais ne compte comme risque que les baisses."),
    "beta": (r"beta", "Le bêta mesure de combien le portefeuille bouge en moyenne quand l’indice bouge de 1 %."),
    "cvar": (r"cvar|expected shortfall", "La CVaR est la perte moyenne des jours pires que la VaR : elle regarde ce qui se passe quand ça va vraiment mal."),
    "var": (r"var|value at risk", "La VaR 95 % à 1 jour est la perte qui n’a été dépassée qu’un jour sur vingt dans le passé observé. Ce n’est pas une perte maximale."),
    "volatilite": (r"volatilite", "La volatilité mesure l’agitation des prix : l’écart-type des rendements, ramené à l’année. Elle ne dit pas le sens du mouvement."),
    "drawdown": (r"drawdown|pire baisse", "Le drawdown est la baisse depuis le plus haut atteint. Une perte de 50 % demande un gain de 100 % pour revenir à zéro."),
    "diversification": (r"diversification|correlation", "Diversifier, c’est détenir des actifs qui ne baissent pas ensemble. En pleine crise les corrélations montent et la protection diminue."),
    "rsi": (r"rsi", "Le RSI compare les hausses et les baisses récentes, de 0 à 100. Au-dessus de 70 on parle de surachat, sous 30 de survente. Cela n’annonce pas un retournement."),
    "macd": (r"macd", "Le MACD est l’écart entre une moyenne rapide et une moyenne lente. Il montre l’accélération d’une tendance, avec retard."),
    "bollinger": (r"bollinger", "Les bandes de Bollinger entourent la moyenne de deux écarts-types. Elles s’élargissent quand la volatilité monte."),
    "carnet": (r"carnet", "Le carnet d’ordres montre les prix et les quantités proposés à l’achat et à la vente. Ici il est simulé."),
    "spread": (r"spread|ecart achat|ecart acheteur", "Le spread est l’écart entre le prix d’achat et le prix de vente. C’est un coût payé à chaque aller-retour."),
    "total_return": (r"total return|rendement total", "Le rendement total compte les variations de prix, les gains réalisés et les frais. Le S&P 500 Total Return y ajoute les dividendes réinvestis."),
    "vix": (r"vix", "Le VIX est la volatilité attendue du S&P 500 sur 30 jours, lue dans les prix des options. Il monte quand le marché a peur."),
    "cet1": (r"cet ?1|fonds propres", "Le CET1 est le capital le plus solide d’une banque, divisé par ses actifs pondérés par le risque. Le minimum réglementaire est de 4,5 %, avant coussins."),
    "mourabaha": (r"m(o)?urabaha", "En mourabaha, la banque achète le bien puis le revend au client avec une marge connue, payable à terme. Elle porte le bien un moment."),
    "salam": (r"salam", "En salam, la banque paie d’avance une marchandise livrée plus tard. Elle porte le risque de prix et de non-livraison."),
    "istisna": (r"istisna('a)?", "En istisna, la banque finance un bien à fabriquer, livré à terme. Elle porte le risque que le fabricant ne livre pas."),
    "franchise": (r"franchise", "La franchise est la part du sinistre qui reste à votre charge avant toute indemnité."),
    "chain_ladder": (r"chain[ -]?ladder|provision(nement|s)?", "Chain Ladder projette le coût final des sinistres passés à partir de leur rythme de règlement observé."),
    "z_score": (r"score z|z[ -]score|altman", "Le score Z d’Altman combine cinq ratios comptables pour repérer une entreprise proche de la défaillance."),
    "xai": (r"xai|ia explicable", "Une IA explicable montre pourquoi elle répond : la méthode, les données, la part de chaque variable et la limite du résultat."),
}

ALIAS = {
    "GOOGL": r"google|alphabet", "META": r"meta|facebook", "DIS": r"disney", "JPM": r"jp ?morgan", "BAC": r"bank of america",
    "GS": r"goldman", "XOM": r"exxon", "CVX": r"chevron", "JNJ": r"johnson", "PFE": r"pfizer", "UNH": r"unitedhealth",
    "PG": r"procter", "KO": r"coca([ -]?cola)?", "WMT": r"walmart", "CAT": r"caterpillar", "BA": r"boeing", "NEE": r"nextera",
    "NVDA": r"nvidia", "BTC-USD": r"bitcoins?|btc", "ETH-USD": r"ethereum|ether|eth", "SOL-USD": r"solana",
    "XRP-USD": r"xrp", "BNB-USD": r"bnb", "ADA-USD": r"cardano", "DOGE-USD": r"dogecoin|doge", "LTC-USD": r"litecoin",
    "CL=F": r"wti|petrole(?! brent)", "BZ=F": r"brent", "NG=F": r"gaz( naturel)?",
    "GC=F": r"l'or|d'or|gold|sur or|mon or", "SI=F": r"argent metal|silver", "PL=F": r"platine", "HG=F": r"cuivre",
    "ZW=F": r"le ble|du ble|ble", "ZS=F": r"soja", "KC=F": r"le cafe|du cafe|cafe",
}


def trouver_actif(question: str, actifs) -> str | None:
    """Symbole négociable cité. Un symbole qui est aussi un mot français (DIS, CAT, BA) ne compte qu'en majuscules."""
    q = normaliser(question)
    brut = set(re.findall(r"[A-Za-z0-9=-]+", question))
    minus = {m.lower() for m in brut}
    for a in actifs:
        if not a.tradable:
            continue
        if a.symbole in brut or (len(a.symbole) >= 4 and a.symbole.lower() in minus):
            return a.symbole
    for a in actifs:
        if not a.tradable:
            continue
        motifs = [ALIAS[a.symbole]] if a.symbole in ALIAS else []
        nom = normaliser(a.nom)
        if len(nom) >= 5 and nom != "argent":           # « or », « blé », « maïs », « argent » passent par les alias
            motifs.append(re.escape(nom))
            premier = nom.split()[0]
            if a.classe == "action" and len(premier) >= 5:
                motifs.append(re.escape(premier))
        if a.symbole == "ZC=F" and _a(r"(?i)maïs|\bcorn\b", question):          # « mais » n'est pas du maïs
            return a.symbole
        if any(_a(rf"(?<![a-z0-9])(?:{m})(?![a-z0-9])", q) for m in motifs):
            return a.symbole
    return None


def trouver_terme(q: str) -> str | None:
    return next((cle for cle, (motif, _) in GLOSSAIRE.items() if _a(rf"(?<![a-z0-9])(?:{motif})(?![a-z0-9])", q)), None)


@dataclass(frozen=True)
class Lecture:
    intention: str
    symbole: str | None = None
    terme: str | None = None
    choc: float | None = None
    classe: str | None = None


def comprendre(question: str, actifs, symbole_page: str | None = None) -> Lecture:
    actifs = list(actifs)
    q = normaliser(question)
    symbole = trouver_actif(question, actifs)
    cite_page = _a(r"\b(cet|cette) (actif|action|crypto|valeur|matiere)\b", q)
    if symbole is None and cite_page and any(a.symbole == symbole_page and a.tradable for a in actifs):
        symbole = symbole_page
    terme = trouver_terme(q)
    perso = _a(r"\b(mon|ma|mes|je|ai-je|suis-je)\b|\bj'", q)
    definition = _a(r"c'est quoi|qu'est[ -]ce qu|definition|defini[rst]|que signifie|veut dire|que veut|explique[rz]?([ -]moi)? (le|la|les|l'|un|une)\b|^comment (marche|fonctionne) (le|la|l'|un|une)", q)

    pourcent = re.search(r"(\d{1,3}(?:[.,]\d+)?) ?(%|pourcent|pour cent)", q)
    mouvement = _a(r"baiss|chut|perd|krach|crash|choc|plonge|descend|recul|monte|hauss|gagne|grimpe|augment", q)
    if pourcent and mouvement and _a(r"\bsi\b|\bs'(il|ils|elle)|choc|scenario|impact|effet", q):
        valeur = min(100.0, float(pourcent.group(1).replace(",", "."))) / 100
        hausse = _a(r"monte|hauss|gagne|grimpe|augment", q) and not _a(r"baiss|chut|krach|crash|plonge|descend|recul", q)
        classe = None
        if symbole is None:
            classe = ("crypto" if _a(r"crypto", q) else "matiere" if _a(r"matieres?\b", q) else "action" if _a(r"\bactions?\b", q) else None)
        return Lecture("choc", symbole=symbole, choc=valeur if hausse else -valeur, classe=classe)

    if _a(r"\bmodele\b|\bsignal ia\b|\bl'ia (dit|pense|prevoit|voit)", q) and symbole:
        return Lecture("modele", symbole=symbole)
    futur = _a(r"\bdemain\b|predi|previ|prevoi|prevu|futur|la semaine prochaine|le mois prochain|prochaine seance|l'annee prochaine", q) or _a(
        r"\b(va|vont|vas|vais|va-t-il|va-t-elle|vont-ils|vais-je)( (encore|se|me|il|elle|je|t-il|bientot))* (monter|baisser|grimper|chuter|perdre|gagner|rebondir|remonter|descendre|exploser|crasher|s'effondrer)", q)
    if futur and not definition:
        return Lecture("prediction", symbole=symbole)
    if _a(r"dois[ -]je (acheter|vendre|investir|garder)|faut[ -]il (acheter|vendre|investir)|(quoi|que|qu'est-ce que je dois) acheter|quelle? (action|crypto|actif) (acheter|choisir)|conseill|meilleure? (action|actif|crypto)|ou investir", q):
        return Lecture("conseil", symbole=symbole)
    if definition and terme and not perso:
        return Lecture("definition", terme=terme)
    if _a(r"qui es[ -]tu|es[ -]tu (une ia|un robot|chatgpt)|chatgpt|quel modele utilise|comment (tu )?(reponds|fonctionnes)", q):
        return Lecture("identite")
    if _a(r"\bcomment (je )?(puis-je |faire pour )?(acheter|vendre|passer|placer|poser|annuler)", q):
        return Lecture("ordre")
    if _a(r"assur|actuari|\bprimes?\b|sinistre|indemn|franchise|proteg|protection|option de vente|\bputs?\b", q):
        return Lecture("assurance")
    if _a(r"banque(s)? |banques?$|stress|islamique|conventionnel|cet ?1|m(o)?urabaha", q) and symbole is None:
        return Lecture("stress")
    if not _a(r"risque", q) and _a(r"\bjeu\b|salle obscure|\bfilm\b|ma note|cette note|montage|\bjury\b|seance mystere|bobine", q):
        return Lecture("jeu")
    if _a(r"indices?\b|benchmark|reference|s ?& ?p|sp ?500|nasdaq|dow jones|msci|battre|bat le marche|mieux que|meilleur que|contre le marche", q):
        return Lecture("indice")
    if symbole:
        return Lecture("actif", symbole=symbole)
    if _a(r"sentiment|fondamenta|\bper\b|benefice", q):
        return Lecture("analyses")
    if _a(r"risque|\bvar\b|cvar|volatil|drawdown|concentr|danger|puis-je perdre|pourrais-je perdre|perte max|diversifi", q):
        return Lecture("risque")
    if _a(r"quelle date|quel jour|quand sommes|on est quand|quelle annee|changer (la |de )?date|revenir en arriere|temps simule", q):
        return Lecture("temps")
    if _a(r"\bsources?\b|\bdonnees\b|yahoo|temps reel|\bdirect\b|vrais? (prix|cours)|fictif", q):
        return Lecture("sources")
    if _a(r"rendement|performance|perd|perte|gagn|gains?\b|resultat|pnl|p&l|plus[ -]value|moins[ -]value|pire position|pourquoi.*(baisse|monte|rouge|vert)|frais", q):
        return Lecture("resultat")
    if _a(r"liquidite|cash|disponible|solde|portefeuille|positions?\b|combien (ai-je|j'ai|me reste)|valeur totale|repartition", q):
        return Lecture("portefeuille")
    if _a(r"apprendre|formation|lecons?\b|quiz|debut(er|ant)|commencer", q):
        return Lecture("formation")
    if _a(r"passer un ordre|\bacheter\b|\bvendre\b|\bordres?\b", q):
        return Lecture("ordre")
    if terme:
        return Lecture("definition", terme=terme)
    if _a(r"^(bonjour|bonsoir|salut|hello|coucou|salam|hi)\b|\baide\b|que (sais|peux)[ -]tu|\bmodules?\b|plateforme", q):
        return Lecture("accueil")
    return Lecture("inconnu")
