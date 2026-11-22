"""Comprendre la question : des règles lisibles, sans modèle de langage et sans internet. Fonctions pures.

Étapes : normaliser (minuscules, accents, abréviations d'élève, mots anglais courants), corriger les fautes de frappe sur un
vocabulaire connu (difflib, seuil prudent), trouver les actifs et les banques cités, puis appliquer des règles dans un ordre fixe.
Une question courte sans intention claire reprend l'intention et l'actif de la question précédente, envoyés par le client :
le serveur ne garde aucun état.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

# ------------------------------------------------------------------ normalisation
ABREVIATIONS = {
    r"c ?koi|c ?quoi|ces? quoi|cest quoi|c'est koi|kesako|whats?|what is": "c'est quoi",
    r"kesk|keske|kes ke|qu'?est ?ce ?que?": "qu'est-ce que",
    r"pk|pq|pourquoa|pourqoi|prq|why": "pourquoi",
    r"koi": "quoi", r"cmt|cmnt|how": "comment", r"cb|cbn|combi1": "combien",
    r"mn": "mon", r"tt": "tout", r"jai|j ai": "j'ai", r"chui|jsuis|jsui": "je suis", r"jpeux|jpe": "je peux",
    r"stp|svp|plz|please|merci": "", r"auj|ajd|aujd|today": "aujourd'hui", r"bcp": "beaucoup", r"qd": "quand",
    r"risk|risks|risky|risqe|risk?ue": "risque", r"portfolio|wallet|portefeuil|portefeuile|portfeuille": "portefeuille",
    r"stocks?": "actions", r"banks?": "banque", r"news": "actualites", r"explain": "explique", r"vs|versus": "et",
    r"rendemant|rendemen|rendment|return": "rendement", r"perf": "performance", r"dash ?board": "tableau de bord",
    r"insurance": "assurance", r"lesson|lessons": "lecon", r"quizz": "quiz",
}
_ABREV = [(re.compile(rf"(?<![a-z0-9']){m}(?![a-z0-9'])"), v) for m, v in ABREVIATIONS.items()]

VOCABULAIRE = {
    "risque", "portefeuille", "rendement", "resultat", "liquidites", "volatilite", "diversification", "concentration", "banque",
    "banques", "assurance", "prime", "franchise", "formation", "lecon", "explique", "expliquer", "pourquoi", "combien", "definition",
    "drawdown", "bollinger", "fibonacci", "sharpe", "sortino", "mourabaha", "istisna", "actualites", "presse", "sentiment", "tableau",
    "compare", "comparer", "strategie", "strategies", "indice", "performance", "position", "positions", "ordres", "regles", "stress",
    "fragile", "capital", "perdu", "gagne", "valeur", "marche", "crypto", "action", "actions", "matieres", "quoi", "commencer",
    "debuter", "protection", "proteger", "fragilite", "solide", "simulation", "scenario", "pire", "defaut", "defauts", "vasicek",
    "dividende", "dividendes", "spread", "slippage", "support", "resistance", "moyenne", "mobile", "tendance", "backtest", "analyse",
    "fondamentale", "technique", "seance", "graphique", "conseil", "prediction", "volatil", "correlation", "beta", "garantie",
}


def sans_accents(texte: str) -> str:
    """Minuscules sans accents, sans rien remplacer : pour les noms propres (« Bank of America » reste lui-même)."""
    t = unicodedata.normalize("NFD", texte.lower().replace("’", "'").replace("œ", "oe"))
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


# mots justes qui ressemblent à un mot du vocabulaire : jamais corrigés (« solde » n'est pas « solide »)
MOTS_COURANTS = {"solde", "perdre", "vendre", "acheter", "limite", "ordre", "monde", "chose", "faire", "toute", "toutes", "pourrais",
                 "depuis", "entre", "quelle", "quelles", "combat", "actif", "actifs", "actuel", "vente", "ventes", "porte", "presque"}


def normaliser(texte: str) -> str:
    t = sans_accents(texte)
    t = re.sub(r"(?<!\d)[.,](?!\d)|[?!;]+", " ", t)                # garde « 12,5 »
    t = re.sub(r"\s+", " ", t).strip()
    for motif, remplacement in _ABREV:
        t = motif.sub(remplacement, t)
    return re.sub(r"\s+", " ", t).strip()


def corriger(q: str, proteges: set[str] = frozenset()) -> str:
    """Corrige un mot de 5 lettres ou plus quand il ressemble beaucoup à un mot du vocabulaire (seuil 0,84)."""
    sortie = []
    for mot in q.split(" "):
        singulier_pluriel = mot.rstrip("s") in VOCABULAIRE or f"{mot}s" in VOCABULAIRE      # « ordre », « marches » sont déjà justes
        if len(mot) >= 5 and mot not in VOCABULAIRE and mot not in MOTS_COURANTS and mot not in proteges and mot.isalpha() and not singulier_pluriel:
            proche = difflib.get_close_matches(mot, VOCABULAIRE, n=1, cutoff=0.84)
            mot = proche[0] if proche else mot
        sortie.append(mot)
    return " ".join(sortie)


def _a(motif: str, q: str) -> bool:
    return re.search(motif, q) is not None


# ------------------------------------------------------------------ glossaire
# clé : (mots reconnus, définition, page où le voir). Le plus précis d'abord. Rédigé par l'équipe, à vérifier.
GLOSSAIRE: dict[str, tuple[str, str, str]] = {
    "stop_suiveur": (r"stop[ -]suiveur|trailing", "Un stop suiveur remonte avec le prix et ne redescend jamais. Il vend quand le prix recule du pourcentage choisi depuis son plus haut.", "/portefeuille"),
    "stop": (r"stop[ -]loss|ordre stop|\bstop\b", "Un stop vend quand le seuil est atteint. Après un saut de prix, le prix obtenu peut être nettement plus bas que le seuil.", "/marche"),
    "take_profit": (r"take[ -]profit|prise de profit", "Un take-profit vend quand le gain visé est atteint. Il fixe une sortie, il ne garantit pas que le prix y arrive.", "/portefeuille"),
    "achat_complementaire": (r"achat complementaire|renforcer|pyramid", "L’achat complémentaire rachète automatiquement une part de la position quand elle gagne le pourcentage choisi.", "/portefeuille"),
    "limite": (r"(ordre|cours) (a cours )?limites?|ordre limite", "Un ordre limite fixe votre prix maximum d’achat ou minimum de vente. Il peut ne jamais être exécuté.", "/marche"),
    "ordre_marche": (r"ordre au marche|au marche", "Un ordre au marché s’exécute tout de suite au meilleur prix disponible : l’exécution est sûre, pas le prix.", "/marche"),
    "prix_revient": (r"prix (de revient|moyen)|pru", "Le prix de revient moyen est le prix payé en moyenne pour une position, frais compris. Le gain latent se mesure contre lui.", "/portefeuille"),
    "plus_value": (r"plus[ -]value|moins[ -]value|latent|realise", "Une plus-value latente est un gain sur le papier, tant que vous n’avez pas vendu. Elle devient réalisée à la vente.", "/portefeuille"),
    "frais": (r"frais|courtage|points? de base|bps", "Les frais sont payés à chaque ordre exécuté, en points de base : 10 points de base valent 0,10 % du montant.", "/marche"),
    "liquidites": (r"liquidites|cash", "Les liquidités sont l’argent non investi. Elles ne bougent pas avec le marché et amortissent les baisses.", "/portefeuille"),
    "dividende": (r"dividendes?", "Un dividende est une part du bénéfice versée aux actionnaires. Le S&P 500 Total Return le réinvestit dans l’indice.", "/"),
    "total_return": (r"total return|rendement total|total rendement", "Le rendement total vaut valeur actuelle ÷ capital initial − 1. Il compte les prix, les gains réalisés et les frais.", "/"),
    "indice": (r"\bindice\b|benchmark|s ?& ?p ?500|sp ?500", "Un indice résume un marché. Le S&P 500 suit 500 grandes entreprises américaines. Vous comparer à lui aux mêmes dates dit si vous faites mieux que « acheter tout le marché ».", "/"),
    "sharpe": (r"sharpe", "Le ratio de Sharpe rapporte le gain au risque pris : rendement au-delà du taux sans risque, divisé par la volatilité. Exemple : 8 % de rendement, 2 % sans risque, 12 % de volatilité donnent 0,5.", "/strategies"),
    "sortino": (r"sortino", "Le ratio de Sortino ressemble au Sharpe, mais ne compte comme risque que les baisses.", "/strategies"),
    "beta": (r"\bbeta\b", "Le bêta mesure de combien le portefeuille bouge en moyenne quand l’indice bouge de 1 %. Un bêta de 1,5 amplifie les mouvements de moitié.", "/portefeuille"),
    "cvar": (r"cvar|expected shortfall", "La CVaR est la perte moyenne des jours pires que la VaR : elle regarde ce qui se passe quand ça va vraiment mal.", "/portefeuille"),
    "var": (r"\bvar\b|value at risk", "La VaR 95 % à 1 jour est la perte qui n’a été dépassée qu’un jour sur vingt dans le passé observé. Ce n’est pas une perte maximale.", "/portefeuille"),
    "volatilite": (r"volatilite", "La volatilité mesure l’agitation des prix : l’écart-type des rendements, ramené à l’année. Elle ne dit pas le sens du mouvement.", "/portefeuille"),
    "drawdown": (r"drawdown|pire baisse", "Le drawdown est la baisse depuis le plus haut atteint. Une perte de 50 % demande un gain de 100 % pour revenir à zéro.", "/portefeuille"),
    "hhi": (r"\bhhi\b|herfindahl", "L’indice HHI additionne le carré du poids de chaque position. 1 veut dire tout sur une position ; plus il est bas, plus le portefeuille est réparti.", "/portefeuille"),
    "concentration": (r"concentration", "La concentration mesure le poids de la plus grosse position. Au-delà d’un quart du portefeuille, une seule mauvaise nouvelle pèse lourd.", "/portefeuille"),
    "diversification": (r"diversification|correlation", "Diversifier, c’est détenir des actifs qui ne baissent pas ensemble. En pleine crise les corrélations montent et la protection diminue.", "/portefeuille"),
    "rsi": (r"\brsi\b", "Le RSI compare les hausses et les baisses récentes, de 0 à 100. Au-dessus de 70 on parle de surachat, sous 30 de survente. Cela n’annonce pas un retournement.", "/strategies"),
    "macd": (r"macd", "Le MACD est l’écart entre une moyenne rapide et une moyenne lente. Il montre l’accélération d’une tendance, avec retard.", "/strategies"),
    "bollinger": (r"bollinger", "Les bandes de Bollinger entourent la moyenne de deux écarts-types. Elles s’élargissent quand la volatilité monte.", "/strategies"),
    "moyenne_mobile": (r"moyenne mobile|moyennes mobiles|\bmm ?\d+|sma|ema", "Une moyenne mobile est la moyenne des derniers cours, recalculée chaque jour. Le prix au-dessus de sa moyenne de 50 séances signale une tendance haussière passée.", "/strategies"),
    "support": (r"\bsupports?\b", "Un support est un niveau où le prix a souvent arrêté de baisser. Ce n’est pas un plancher garanti.", "/strategies"),
    "resistance": (r"resistances?", "Une résistance est un niveau où le prix a souvent arrêté de monter. Elle peut céder.", "/strategies"),
    "fibonacci": (r"fibonacci|retracement", "Les niveaux de Fibonacci (23,6 %, 38,2 %, 61,8 %) découpent un mouvement passé pour repérer des zones de retour possibles. C’est une convention, pas une loi.", "/strategies"),
    "gap": (r"\bgaps?\b|saut de prix", "Un gap est un saut entre la clôture de la veille et l’ouverture. Un stop peut alors être exécuté bien plus bas que son seuil.", "/marche"),
    "bougie": (r"bougies?|chandeliers?", "Une bougie résume une séance : ouverture, plus haut, plus bas, clôture. Pleine quand le prix baisse, creuse quand il monte, selon la convention.", "/marche"),
    "tendance": (r"tendance", "Une tendance est la direction dominante des prix sur une période. Elle se lit après coup et peut s’inverser.", "/strategies"),
    "backtest": (r"backtest|back[ -]test", "Un backtest rejoue une stratégie sur le passé pour voir ce qu’elle aurait donné. Il ne garantit rien pour la suite.", "/strategies"),
    "surajustement": (r"surajust[a-z]*|overfit[a-z]*|sur[ -]apprentissage", "Le surajustement, c’est régler une stratégie si bien sur le passé qu’elle colle au bruit. Elle échoue ensuite sur des données nouvelles.", "/strategies"),
    "carnet": (r"carnet", "Le carnet d’ordres montre les prix et les quantités proposés à l’achat et à la vente. Ici il est simulé.", "/marche"),
    "spread": (r"spread|ecart achat|ecart acheteur", "Le spread est l’écart entre le prix d’achat et le prix de vente. C’est un coût payé à chaque aller-retour.", "/marche"),
    "slippage": (r"slippage|glissement", "Le slippage est l’écart entre le prix attendu et le prix obtenu, par exemple quand la quantité dépasse ce que propose le carnet.", "/marche"),
    "vix": (r"\bvix\b", "Le VIX est la volatilité attendue du S&P 500 sur 30 jours, lue dans les prix des options. Il monte quand le marché a peur.", "/jeu"),
    "put": (r"\bput\b|option de vente", "Un put est une option de vente : le droit de vendre à un prix fixé. Il protège d’une baisse, contre une prime payée d’avance.", "/actuariat"),
    "black_scholes": (r"black[ -]?scholes", "Black-Scholes donne le prix théorique d’une option à partir du prix, du prix d’exercice, de la durée, du taux et de la volatilité.", "/actuariat"),
    "prime_pure": (r"prime pure", "La prime pure est le coût moyen attendu des sinistres : fréquence × coût moyen. L’assureur y ajoute une marge et des frais.", "/actuariat"),
    "franchise": (r"franchise", "La franchise est la part du sinistre qui reste à votre charge avant toute indemnité.", "/actuariat"),
    "chain_ladder": (r"chain[ -]?ladder|provisionnement", "Chain Ladder projette le coût final des sinistres passés à partir de leur rythme de règlement observé.", "/actuariat"),
    "cet1": (r"cet ?1|fonds propres", "Le CET1 est le capital le plus solide d’une banque, divisé par ses actifs pondérés par le risque. Minimum : 4,5 % ; 7 % avec le coussin de conservation.", "/stress"),
    "rwa": (r"\brwa\b|actifs ponderes", "Les actifs pondérés (RWA) comptent chaque actif selon son risque : un prêt risqué pèse plus qu’une liquidité. Ils sont le dénominateur du ratio CET1.", "/stress"),
    "pd": (r"\bpd\b|probabilite de defaut", "La PD est la probabilité qu’un emprunteur ne rembourse pas dans l’année. Ici, le taux de prêts en défaut publié en sert d’approximation.", "/stress"),
    "lgd": (r"\blgd\b|perte en cas de defaut", "La LGD est la part perdue quand un prêt fait défaut, après récupération des garanties. 45 % veut dire que la banque récupère 55 %.", "/stress"),
    "vasicek": (r"vasicek", "Le modèle de Vasicek, celui de la formule de Bâle, transforme la PD habituelle en PD d’une année très mauvaise, au quantile choisi.", "/stress"),
    "quantile": (r"quantile", "Un quantile de 99 % désigne une situation plus grave que 99 cas sur 100. En stress test, c’est l’intensité de la crise.", "/stress"),
    "pire_cas": (r"pire cas|stress inverse|test inverse", "Le pire cas est un calcul à l’envers : la hausse des défauts qui ferait tomber la banque au minimum de 4,5 % de CET1.", "/stress"),
    "coussin": (r"coussin", "Le coussin de conservation ajoute 2,5 points au minimum de 4,5 % de CET1, soit 7 %. En dessous, la banque doit freiner ses distributions.", "/stress"),
    "mourabaha": (r"m(o)?urabaha", "En mourabaha, la banque achète le bien puis le revend au client avec une marge connue, payable à terme. Elle porte le bien un moment.", "/stress"),
    "salam": (r"\bsalam\b", "En salam, la banque paie d’avance une marchandise livrée plus tard. Elle porte le risque de prix et de non-livraison.", "/stress"),
    "istisna": (r"istisna('a)?", "En istisna, la banque finance un bien à fabriquer, livré à terme. Elle porte le risque que le fabricant ne livre pas.", "/stress"),
    "sukuk": (r"sukuk", "Un sukuk est un certificat conforme à la charia, adossé à des actifs réels. Il verse une part des revenus de ces actifs au lieu d’un intérêt.", "/stress"),
    "psia": (r"psia|comptes? d'investissement", "Les PSIA sont des comptes d’investissement de banque islamique : le déposant partage les profits et, en principe, les pertes.", "/stress"),
    "dcr": (r"risque commercial deplace|\bdcr\b", "Le risque commercial déplacé : la banque islamique rogne sa part de profit pour mieux payer les déposants et éviter qu’ils partent.", "/stress"),
    "z_score": (r"score z|z[ -]?score|altman", "Le score Z d’Altman combine cinq ratios comptables pour repérer une entreprise proche de la défaillance. Sain au-dessus de 2,99, détresse sous 1,81.", "/credit"),
    "gdelt": (r"gdelt", "GDELT est une base publique qui recense les articles de presse du monde entier et leur ton. Elle peut servir à mesurer le sentiment.", "/actualites"),
    "ton": (r"\bton\b|tonalite|sentiment", "Le ton d’une actualité compte les mots positifs et négatifs : (positifs − négatifs) ÷ (positifs + négatifs + 1). Au-delà de 0,15 il est positif.", "/actualites"),
    "regression_logistique": (r"regression logistique|logistique", "La régression logistique transforme une somme pondérée de variables en probabilité entre 0 et 1. Chaque variable a une contribution lisible.", "/ia"),
    "q_learning": (r"q[ -]?learning|renforcement", "Le Q-learning apprend par essais et erreurs quelle action rapporte le plus dans chaque situation. Ici, sur 9 situations seulement.", "/ia"),
    "regime": (r"regimes? de marche|melange gaussien", "Un régime de marché regroupe des périodes qui se ressemblent par le rendement et la volatilité. Le nom est donné après coup.", "/ia"),
    "parite_risque": (r"parite de risque|variance minimale", "La parité de risque répartit le portefeuille pour que chaque actif apporte la même part de risque. La variance minimale cherche le portefeuille le moins agité.", "/ia"),
    "xai": (r"\bxai\b|ia explicable", "Une IA explicable montre pourquoi elle répond : la méthode, les données, la part de chaque variable et la limite du résultat.", "/xai"),
}

ALIAS = {
    "GOOGL": r"google|alphabet", "META": r"meta|facebook", "DIS": r"disney", "JPM": r"jp ?morgan", "BAC": r"bank of america",
    "GS": r"goldman", "XOM": r"exxon", "CVX": r"chevron", "JNJ": r"johnson", "PFE": r"pfizer", "UNH": r"unitedhealth",
    "PG": r"procter", "KO": r"coca([ -]?cola)?", "WMT": r"walmart", "CAT": r"caterpillar", "BA": r"boeing", "NEE": r"nextera",
    "NVDA": r"nvidia", "BTC-USD": r"bitcoins?|btc", "ETH-USD": r"ethereum|ether|eth", "SOL-USD": r"solana",
    "XRP-USD": r"xrp", "BNB-USD": r"bnb", "ADA-USD": r"cardano", "DOGE-USD": r"dogecoin|doge", "LTC-USD": r"litecoin",
    "CL=F": r"wti|petrole(?! brent)", "BZ=F": r"brent", "NG=F": r"gaz( naturel)?",
    "GC=F": r"l'or|d'or|gold|sur or|mon or|\bor et\b|et l'or", "SI=F": r"argent metal|silver", "PL=F": r"platine", "HG=F": r"cuivre",
    "ZW=F": r"le ble|du ble|ble", "ZS=F": r"soja", "KC=F": r"le cafe|du cafe|cafe",
}

# Banques réelles du stress test : nom reconnu -> clé du CSV
BANQUES = {
    "alrajhi": r"al ?rajhi|rajhi", "alinma": r"alinma|al ?inma", "albilad": r"al ?bilad|bilad", "aljazira": r"al ?jazira|jazira",
    "snb": r"\bsnb\b|saudi national|al ?ahli|\bahli\b", "riyad": r"riyad", "sab": r"\bsab\b|saudi awwal|awwal",
    "bsf": r"\bbsf\b|fransi", "saib": r"\bsaib\b",
}


def _motifs_actif(a) -> list[str]:
    motifs = [ALIAS[a.symbole]] if a.symbole in ALIAS else []
    nom = sans_accents(a.nom)
    if len(nom) >= 5 and nom != "argent":           # « or », « blé », « maïs », « argent » passent par les alias
        motifs.append(re.escape(nom))
        premier = nom.split()[0]
        if a.classe == "action" and len(premier) >= 5:
            motifs.append(re.escape(premier))
    return motifs


def trouver_actifs(question: str, actifs) -> list[str]:
    """Symboles négociables cités, dans l'ordre où ils apparaissent. Un symbole qui est aussi un mot français (DIS, CAT, BA) ne compte qu'en majuscules."""
    q = sans_accents(question)
    trouves: dict[str, int] = {}
    for m in re.finditer(r"[A-Za-z0-9=-]+", question):
        mot = m.group(0)
        for a in actifs:
            if a.tradable and (a.symbole == mot or (len(a.symbole) >= 4 and a.symbole.lower() == mot.lower())):
                trouves.setdefault(a.symbole, m.start() / max(1, len(question)))
    for a in actifs:
        if not a.tradable or a.symbole in trouves:
            continue
        if a.symbole == "ZC=F":
            m = re.search(r"(?i)maïs|\bcorn\b", question)                   # « mais » n'est pas du maïs
            if m:
                trouves[a.symbole] = m.start() / max(1, len(question))
            continue
        for motif in _motifs_actif(a):
            m = re.search(rf"(?<![a-z0-9])(?:{motif})(?![a-z0-9])", q)
            if m:
                trouves[a.symbole] = m.start() / max(1, len(q))
                break
    return [s for s, _ in sorted(trouves.items(), key=lambda x: x[1])]


def trouver_actif(question: str, actifs) -> str | None:
    t = trouver_actifs(question, actifs)
    return t[0] if t else None


def trouver_banque(q: str) -> str | None:
    return next((cle for cle, motif in BANQUES.items() if _a(rf"(?<![a-z0-9])(?:{motif})(?![a-z0-9])", q)), None)


def trouver_terme(q: str) -> str | None:
    return next((cle for cle, (motif, _, _) in GLOSSAIRE.items() if _a(rf"(?<![a-z0-9])(?:{motif})(?![a-z0-9])", q)), None)


@dataclass(frozen=True)
class Lecture:
    intention: str
    symbole: str | None = None
    terme: str | None = None
    choc: float | None = None
    classe: str | None = None
    symbole2: str | None = None
    banque: str | None = None
    page: str | None = None
    suite: bool = False                 # la question reprend le contexte de la précédente


# intentions dont la suite « et pour X ? » garde le sens en changeant d'actif
SUITE_ACTIF = {"actif", "prediction", "modele", "actualites", "conseil"}
SUITE_ACTIF_DEFAUT = "actif"


def comprendre(question: str, actifs, symbole_page: str | None = None, contexte: dict | None = None, page: str | None = None) -> Lecture:
    actifs = list(actifs)
    brut = normaliser(question)
    noms = {w for a in actifs for w in sans_accents(a.nom).split()}
    q = corriger(brut, noms)
    lu = _regles(question, q, actifs, symbole_page, page)
    return _suite(lu, q, actifs, contexte)


def _suite(lu: Lecture, q: str, actifs, contexte: dict | None) -> Lecture:
    """Une question courte qui s'appuie sur la précédente (« et pour Bitcoin ? », « pourquoi ? »)."""
    if not contexte or not contexte.get("intention"):
        return lu
    avant, sym_avant = contexte["intention"], contexte.get("symbole")
    courte = len(q.split()) <= 6
    enchaine = _a(r"^(et|ok et|alors|du coup|mais)\b|^pourquoi$|^(et )?pourquoi( ca| donc)?$|^comment ca$|^(et )?(lui|elle|celle-ci|celui-ci)$", q)
    if not (courte and (enchaine or lu.intention in ("inconnu", "accueil"))):
        return lu
    if _a(r"\ben (19|20)\d\d\b", q):
        return Lecture("temps", suite=True)
    if lu.intention in ("actif", "comparer") and lu.symbole and avant in SUITE_ACTIF:
        return Lecture(avant, symbole=lu.symbole, suite=True)
    if lu.intention in ("inconnu", "accueil"):
        return Lecture(avant, symbole=sym_avant, symbole2=contexte.get("symbole2"), banque=contexte.get("banque"), suite=True)
    return lu


def _regles(question: str, q: str, actifs, symbole_page: str | None, page: str | None) -> Lecture:
    trouves = trouver_actifs(question, actifs) or trouver_actifs(q, actifs)
    symbole = trouves[0] if trouves else None
    cite_page = _a(r"\b(cet|cette) (actif|action|crypto|valeur|matiere)\b", q)
    if symbole is None and cite_page and any(a.symbole == symbole_page and a.tradable for a in actifs):
        symbole = symbole_page
    terme = trouver_terme(q)
    banque = trouver_banque(q)
    perso = _a(r"\b(mon|ma|mes|je|ai-je|suis-je)\b|\bj'", q)
    definition = _a(r"c'est quoi|qu'est-ce que?|definition|defini[rst]|que signifie|veut dire|que veut|ca veut dire|explique[rz]?([ -]moi)? (le|la|les|l'|un|une|ce que)\b|^comment (marche|fonctionne) (le|la|l'|un|une)", q)

    if _a(r"(explique|decris|resume|montre)[a-z]*( ?-?moi)? (cette|la) page|que (montre|dit|fait) (cette|la) page|a quoi sert (cette|la) page|cette page|ou suis-je|je suis ou|je fais quoi ici|que faire ici", q):
        return Lecture("page", symbole=symbole_page, page=page or "")

    pourcent = re.search(r"(\d{1,3}(?:[.,]\d+)?) ?(%|pourcent|pour cent)", q)
    mouvement = _a(r"baiss|chut|perd|krach|crash|choc|plonge|descend|recul|monte|hauss|gagne|grimpe|augment", q)
    if pourcent and mouvement and _a(r"\bsi\b|\bs'(il|ils|elle)|choc|scenario|impact|effet|krach|crash", q):
        valeur = min(100.0, float(pourcent.group(1).replace(",", "."))) / 100
        hausse = _a(r"monte|hauss|gagne|grimpe|augment", q) and not _a(r"baiss|chut|krach|crash|plonge|descend|recul", q)
        classe = None
        if symbole is None:
            classe = ("crypto" if _a(r"crypto", q) else "matiere" if _a(r"matieres?\b", q) else "action" if _a(r"\bactions?\b", q) else None)
        return Lecture("choc", symbole=symbole, choc=valeur if hausse else -valeur, classe=classe)

    if _a(r"\bmodele\b|\bsignal ia\b|\bl'ia (dit|pense|prevoit|voit)", q) and symbole:
        return Lecture("modele", symbole=symbole)
    futur = _a(r"\bdemain\b|predi|previ|prevoi|prevu|futur|la semaine prochaine|le mois prochain|prochaine seance|l'annee prochaine", q) or _a(
        r"\b(va|vont|vas|vais|va-t-il|va-t-elle|vont-ils|vais-je)( (encore|se|me|il|elle|je|t-il|bientot))* (monter|baisser|grimper|chuter|perdre|gagner|rebondir|remonter|descendre|exploser|crasher|s'effondrer|faire faillite)", q)
    if futur and not definition:
        return Lecture("prediction", symbole=symbole)
    if _a(r"dois[ -]je (acheter|vendre|investir|garder)|faut[ -]il (acheter|vendre|investir)|(quoi|que|qu'est-ce que je dois) acheter|quelle? (action|crypto|actif) (acheter|choisir)|conseill|meilleure? (action|actif|crypto|placement)|ou investir|je (vends|achete) ou pas|tu (acheterais|vendrais)", q):
        return Lecture("conseil", symbole=symbole)
    if len(trouves) >= 2 and _a(r"compar|\bet\b|\bou\b|difference|mieux|plus (risque|volatil|solide)|face a", q):
        return Lecture("comparer", symbole=trouves[0], symbole2=trouves[1])
    if terme == "z_score" or _a(r"\bcredit\b|faillite d'une entreprise|risque de faillite", q):
        return Lecture("credit", terme=terme)
    if definition and terme and not perso:
        return Lecture("definition", terme=terme)
    if _a(r"qui es[ -]tu|t'es qui|es[ -]tu (une ia|un robot|chatgpt|humain)|chatgpt|gpt|quel modele utilise|comment (tu )?(reponds|fonctionnes|marches)|tu es (une ia|un robot)", q):
        return Lecture("identite")
    if _a(r"\bcomment (je )?(puis-je |peut-on |on |faire pour |je peux )?(acheter|vendre|passer|placer|poser|annuler|mettre)", q):
        return Lecture("ordre")
    if _a(r"\blecons?\b|\bquiz\b|\bformation\b", q):
        return Lecture("formation", terme=terme)
    if _a(r"(vente|vendu|vendue) .*plus bas|mes ordres|ordres? en attente|ordres? ouverts?|mes regles|regles? (automatiques?|actives?)|(mon|le) stop .*(vendu|declench|execute|plus bas)|stop a vendu|pourquoi .*(vendu|execute) (plus bas|moins cher|a perte)|declenche", q):
        return Lecture("ordres", symbole=symbole)
    if _a(r"assur|actuari|\bprimes?\b|sinistre|indemn|franchise|proteger|protection|couvrir mon", q):
        return Lecture("assurance")
    if banque or (_a(r"banques?\b|stress|islamique|conventionnel|cet ?1|m(o)?urabaha|fragile|capital a reconstituer|vasicek", q) and symbole is None):
        return Lecture("stress", banque=banque)
    if not _a(r"risque", q) and _a(r"\bjeu\b|salle obscure|\bfilm\b|ma note|cette note|montage|\bjury\b|seance mystere|bobine|autre choix|si j'avais (tenu|vendu|achete|choisi)", q):
        return Lecture("jeu")
    if _a(r"presse|actualites?|nouvelles|journaux|medias|on dit quoi|que dit[- ]on|\bton\b|sentiment|rumeur", q):
        return Lecture("actualites", symbole=symbole)
    if _a(r"tableau de bord|\bresume\b|resume[rz]?|\bbilan\b|du jour|aujourd'hui|cette seance|ma journee|vue d'ensemble", q) and not symbole:
        return Lecture("dashboard")
    if _a(r"indices?\b|benchmark|reference|s ?& ?p|sp ?500|nasdaq|dow jones|msci|battre|bats? le marche|mieux que|meilleur que|contre le marche", q):
        return Lecture("indice")
    if symbole:
        return Lecture("actif", symbole=symbole)
    if _a(r"fondamenta|\bper\b|benefice|bilan comptable", q):
        return Lecture("analyses")
    if _a(r"risque|\bvar\b|cvar|volatil|drawdown|pire baisse|concentr|danger|puis-je perdre|pourrais-je perdre|peux perdre|perdre au pire|perte max|diversifi|hhi|trop expose", q):
        return Lecture("risque")
    if _a(r"quelle date|quel jour|quand sommes|on est quand|on est le|quelle annee|changer (la |de )?date|revenir en arriere|reculer|retour en arriere|temps simule|\bdirect\b.*(pourquoi|ordre)|horloge", q):
        return Lecture("temps")
    if _a(r"\bsources?\b|\bdonnees\b|yahoo|temps reel|\bdirect\b|vrais? (prix|cours)|fictif|d'ou vien", q):
        return Lecture("sources")
    if _a(r"rendement|performance|perd|perte|gagn|gains?\b|resultat|pnl|p&l|plus[ -]value|moins[ -]value|pire position|pourquoi.*(baisse|monte|rouge|vert)", q):
        return Lecture("resultat")
    if _a(r"liquidite|cash|disponible|solde|portefeuille|positions?\b|combien (ai-je|j'ai|me reste|il me reste)|valeur totale|repartition|pese le plus|plus grosse", q):
        return Lecture("portefeuille")
    if _a(r"apprendre|formation|lecons?\b|quiz|debut(er|ant)|commencer|par ou|par quoi", q):
        return Lecture("formation", terme=terme)
    if _a(r"passer un ordre|\bacheter\b|\bvendre\b|\bordres?\b|achete|vends", q):
        return Lecture("ordre")
    if terme:
        return Lecture("definition", terme=terme)
    if _a(r"^(bonjour|bonsoir|salut|hello|coucou|salam|hi|yo|hey)\b|\baide\b|que (sais|peux)[ -]tu|tu sers a quoi|\bmodules?\b|plateforme", q):
        return Lecture("accueil")
    return Lecture("inconnu")
