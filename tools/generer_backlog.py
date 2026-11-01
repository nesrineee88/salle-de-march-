"""Génère docs/BACKLOG.md et docs/backlog_jira.csv à partir d'une seule liste (source de vérité).

    python tools/generer_backlog.py

Niveaux : N = noyau noté (obligatoire) ; A = atout distinctif ; B = bonus si le temps le permet.
Sprints : cadence de 2 semaines du guide d'équipe. Aucune date n'est fixée : en attente de la date de rendu.
Import Jira : Espace > Paramètres > Import > CSV ; faire correspondre les colonnes à l'import
(Type de ticket, Résumé, Description, Priorité, Étiquettes, Epic). Laisser « Assigné » vide (décision d'équipe).
"""
import csv
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]

EPICS = {
    "EP-01": ("Authentification et sécurité", "N"),
    "EP-02": ("Données de marché", "N"),
    "EP-03": ("Trading et portefeuille virtuel", "N"),
    "EP-04": ("Gestion du risque", "N"),
    "EP-05": ("Analyse technique, fondamentale et backtesting", "N"),
    "EP-06": ("IA : prédiction et anomalies", "N"),
    "EP-07": ("IA : analyse des sentiments et actualités", "A"),
    "EP-08": ("IA : agent intelligent de trading", "A"),
    "EP-09": ("AI Stress Testing bancaire", "N"),
    "EP-10": ("Explainable AI (XAI)", "N"),
    "EP-11": ("Module actuariat", "A"),
    "EP-12": ("Formation et gamification", "N"),
    "EP-13": ("Administration et crises", "N"),
    "EP-14": ("Interface, UX et design", "N"),
    "EP-15": ("DevOps, qualité et documentation", "N"),
    "EP-16": ("Gestion des utilisateurs", "N"),
    "EP-17": ("Carnet d'ordres et exécution", "N"),
    "EP-18": ("Replay et scénarios historiques", "A"),
    "EP-19": ("Coaching et profil comportemental", "A"),
}

# (epic, niveau, sprint, résumé, description, statut)
S = [
    # ---- Sprint 0 : cadrage
    ("EP-14", "N", 0, "Maquettes de l'écran principal en mode Apprenant / Trader / Admin", "En tant qu'équipe, je veux 2 à 3 maquettes validées par le PO afin de figer la direction UX avant de coder.", "Remplacé par l'interface codée (docs/DESIGN.md) : à faire valider par le PO"),
    ("EP-15", "N", 0, "Dépôt Git, branches, CI et conventions", "En tant qu'équipe, je veux un workflow Git avec PR relues afin de livrer proprement.", "À faire"),
    ("EP-15", "N", 0, "Conteneuriser avec Docker Compose (PostgreSQL, API)", "En tant que développeur, je veux un environnement identique pour tous afin d'éviter les « ça marche chez moi ».", "Partiel : docker-compose.yml pour PostgreSQL écrit (non lancé ici, pas de Docker) ; conteneur de l'API à faire"),
    ("EP-15", "N", 0, "Migrations de base de données (Alembic)", "En tant que développeur, je veux faire évoluer la base sans perdre de données.", "Fait (migration initiale testée sur SQLite et PostgreSQL 16)"),
    ("EP-02", "N", 0, "Choisir et figer les sources de données (décisions D2 à D9)", "En tant qu'équipe, je veux des sources documentées afin de justifier nos choix devant le jury.", "Fait (docs/DECISIONS.md)"),
    # ---- Sprint 1 : fondations
    ("EP-02", "N", 1, "Catalogue des actifs (43 actifs, 4 classes)", "En tant que système, je veux un catalogue unique afin que tous les modules parlent des mêmes actifs.", "Fait (code)"),
    ("EP-02", "N", 1, "Télécharger et figer un instantané des prix avec manifest SHA-256", "En tant qu'équipe, je veux le même jeu de données chez tous afin de reproduire les résultats.", "Fait (code, à lancer sur une machine avec accès réseau)"),
    ("EP-02", "N", 1, "Nettoyer les données et produire un rapport de qualité", "En tant qu'analyste, je veux un rapport des corrections afin de ne rien cacher.", "Fait (code)"),
    ("EP-02", "N", 1, "Stocker les séries temporelles dans PostgreSQL / TimescaleDB", "En tant que système, je veux des requêtes rapides par intervalle afin de servir graphiques et backtests.", "À faire (les prix sont lus depuis des fichiers CSV chargés en mémoire ; à migrer avec la couche « scénario » de l'admin)"),
    ("EP-02", "N", 1, "Horloge de replay (facteur réglable, pause, aller à une date)", "En tant que trader, je veux contrôler la vitesse du temps afin de rejouer le marché (1 semaine = 1 heure).", "Fait (API + interface avec frise et repères)"),
    ("EP-02", "A", 8, "Mode Direct (bêta) : prix de marché récents à l'heure réelle, en plus du rejeu historique", "En tant que trader, je veux voir le marché d'aujourd'hui afin de m'entraîner en conditions réelles.", "Partiel : code et tests faits avec un faux flux ; l'appel réel à Yahoo Finance n'a jamais été exécuté depuis l'environnement de développement (réseau bloqué), à essayer sur un poste connecté"),
    ("EP-02", "N", 1, "Ticks intraday synthétiques cohérents avec les bougies, sans fuite du futur", "En tant que trader, je veux un prix qui bouge en direct afin que stops et ordres limites aient un sens.", "Fait (code)"),
    ("EP-01", "N", 1, "Inscription, connexion, JWT, hachage Argon2", "En tant qu'utilisateur, je veux un compte sécurisé afin de protéger mon portefeuille.", "Fait (API + interface)"),
    ("EP-16", "N", 1, "Rôles et permissions (Apprenant, Trader, Formateur, Admin)", "En tant qu'admin, je veux des droits par rôle afin de maîtriser les accès.", "Fait (API)"),
    ("EP-14", "N", 1, "Design system et coque de l'application (navigation, thème, trilingue FR/EN/AR)", "En tant qu'utilisateur, je veux une interface cohérente et accessible afin d'utiliser l'outil sans effort.", "Fait (thèmes sombre et clair, validé par l'utilisateur ; anglais et arabe à faire)"),
    # ---- Sprint 2 : trading de base
    ("EP-03", "N", 2, "Capital virtuel, ordres au marché, positions et historique", "En tant que trader, je veux acheter et vendre afin de constituer un portefeuille.", "Fait (moteur + API + interface + base de données)"),
    ("EP-03", "N", 2, "Enregistrer ordres, positions, exécutions et horloge en base", "En tant que trader, je veux retrouver mon portefeuille après un redémarrage afin de ne rien perdre.", "Fait (testé sur SQLite et PostgreSQL 16, redémarrage réel vérifié)"),
    ("EP-17", "N", 2, "Carnet d'ordres simulé (liquidité par bots, priorité prix puis temps)", "En tant que trader, je veux voir où mon ordre se place afin de comprendre la liquidité.", "Fait en v1 (liquidité synthétique ; bots à venir)"),
    ("EP-17", "N", 2, "Ordres limite, stop, annulation, exécution partielle", "En tant que trader, je veux choisir le type d'ordre afin de maîtriser mon prix d'entrée.", "Fait (moteur + API)"),
    ("EP-17", "N", 2, "Frais, spread, slippage et impact de marché", "En tant que trader, je veux un coût d'exécution réaliste afin d'éviter les illusions de gain.", "Fait (moteur)"),
    ("EP-14", "N", 2, "Pages séparées : tableau de bord, un marché par page, portefeuille, compte, administration", "En tant que trader, je veux une navigation claire afin de trouver chaque outil sans chercher.", "Fait (interface testée dans un navigateur ; un seul portefeuille pour les trois marchés, décision D20)"),
    ("EP-03", "N", 2, "Page Portefeuille : valeur au fil du temps contre le S&P 500, répartition, trades clôturés, profil de risque comparé au risque réel", "En tant que trader, je veux voir mon portefeuille en entier afin de juger mes choix.", "Fait (historique de valeur enregistré en base, migration 0002)"),
    ("EP-01", "N", 2, "Gérer ses appareils connectés, changer de mot de passe, se déconnecter partout", "En tant qu'utilisateur, je veux contrôler l'accès à mon compte afin de le protéger.", "Fait (API + interface)"),
    ("EP-14", "N", 2, "Écran Marchés : liste des actifs, graphique en bougies, panneau d'ordre", "En tant que trader, je veux une vue de marché claire afin de décider vite.", "Fait (une page par marché : actions, cryptomonnaies, matières premières ; liste, bougies, ordre, carnet)"),
    ("EP-05", "N", 2, "Indicateurs techniques : SMA, EMA, RSI, MACD, Bollinger, ATR", "En tant que trader, je veux des indicateurs afin d'analyser les tendances.", "Fait (SMA 20 et 50, EMA 20, Bollinger, RSI, MACD sur le graphique, ATR dans l'en-tête ; aide en mode Apprenant ; conventions D22)"),
    # ---- Sprint 3 : risque et analyse
    ("EP-04", "N", 3, "Stop-loss et take-profit (fixe, suiveur, ATR, par paliers, OCO / bracket)", "En tant que trader, je veux des sorties automatiques afin de limiter mes pertes et sécuriser mes gains.", "Partiel : stop-loss en %, prise de profit partielle, stop suiveur, achat complémentaire et annulation croisée (OCO) faits (D25) ; stops par ATR et par paliers, et bracket à la pose de l'ordre, à faire"),
    ("EP-04", "N", 3, "Disjoncteur de portefeuille et délai avant rachat après un stop", "En tant que trader, je veux un garde-fou global afin d'éviter l'emballement.", "À faire"),
    ("EP-04", "N", 3, "Feu tricolore de risque avant chaque ordre", "En tant que trader, je veux voir l'impact d'un ordre sur mon risque afin de décider en connaissance de cause.", "À faire"),
    ("EP-04", "N", 3, "Indicateurs : VaR, CVaR, volatilité, drawdown, Sharpe, corrélations, concentration", "En tant que trader, je veux mesurer mon risque afin de le piloter.", "Fait (page Portefeuille : VaR et CVaR historiques, volatilité, drawdown, Sharpe, Sortino, corrélations, concentration, diversification ; conventions D19)"),
    ("EP-04", "N", 3, "Vérification du risque avant un achat (concentration, perte possible comparée au profil, liquidités, volatilité)", "En tant que trader, je veux être prévenu avant d'acheter afin de ne pas prendre un risque que je n'avais pas vu.", "Fait (alertes non bloquantes dans le ticket d'ordre ; seuils pédagogiques, D25)"),
    ("EP-03", "N", 3, "Levier, marge et appel de marge", "En tant que trader, je veux comprendre le levier afin d'en mesurer le danger.", "À faire"),
    ("EP-04", "A", 3, "Optimiseur de portefeuille (Markowitz, risk parity) et alerte de fausse diversification", "En tant que trader, je veux comparer mon portefeuille à un portefeuille idéal afin de mieux diversifier.", "Partiel : variance minimale et parité de risque avec contribution au risque (page IA, D33) ; alerte de fausse diversification à faire"),
    ("EP-05", "N", 3, "Backtesting et comparaison de stratégies (momentum, croisement de moyennes, mean reversion, pairs trading)", "En tant que trader, je veux tester une idée sur l'historique afin de la juger.", "Partiel : achat-conservation, croisement de moyennes, RSI, MACD, Bollinger, momentum, comparés sur la période et sur chaque moitié (page Stratégies, décision D26) ; pairs trading à faire"),
    ("EP-05", "A", 3, "Laboratoire de stratégies sans code avec test hors échantillon (alerte de surapprentissage)", "En tant que débutant, je veux construire une règle simple afin de la tester sans coder.", "À faire"),
    ("EP-05", "A", 3, "Courbe à terme des matières premières (contango, backwardation) et saisonnalité", "En tant que trader, je veux lire la structure des futures afin de comprendre les matières premières.", "À faire"),
    # ---- Sprint 4 : IA marchés
    ("EP-06", "N", 4, "Pipeline de variables et modèles de base (ARIMA, GARCH, Random Forest, XGBoost)", "En tant qu'analyste, je veux des prédictions de référence afin de comparer des modèles.", "Partiel : régression logistique et arbres boostés en marche avant contre références naïves (D33) ; ARIMA, GARCH, XGBoost à faire"),
    ("EP-06", "N", 4, "Modèles LSTM / GRU et comparaison RMSE / MAE (suivi MLflow)", "En tant qu'analyste, je veux comparer les approches afin de choisir la meilleure.", "À faire"),
    ("EP-06", "N", 4, "Détection d'anomalies (Isolation Forest, autoencodeur) et alertes", "En tant que trader, je veux être alerté des mouvements anormaux afin de réagir.", "Partiel : anomalies par score robuste (médiane, MAD) avec explication (page IA, D33) ; Isolation Forest et autoencodeur à faire"),
    ("EP-06", "A", 4, "Détection de régime de marché (haussier, baissier, forte volatilité)", "En tant que trader, je veux connaître le régime courant afin d'adapter ma stratégie.", "Fait (mélange gaussien à 3 régimes, page IA, D33)"),
    # ---- Sprint 5 : stress testing
    ("EP-09", "N", 5, "Données bancaires : EBA (conventionnelles) et IFSB + synthétiques étiquetées (islamiques)", "En tant qu'analyste, je veux des données de banques afin de simuler des chocs.", "À faire (accord du PO sur les données islamiques)"),
    ("EP-09", "N", 5, "Générateur de scénarios (taux, krach, récession, défauts, chocs combinés)", "En tant qu'analyste, je veux définir des chocs afin de tester la résilience.", "Partiel : six modèles de crises sur les matières premières et les actions (D27) et chocs historiques mesurés (D31) ; taux et défauts à faire"),
    ("EP-09", "N", 5, "Modèles ML / DL de pertes, NPL, CET1, liquidité ; score de résilience", "En tant qu'analyste, je veux estimer l'impact afin de comparer les banques.", "Partiel : modèle structurel et remplaçant statistique du CET1 (D31) ; pertes sur prêts non performants et liquidité à faire"),
    ("EP-09", "N", 5, "Comparaison conventionnelles / islamiques (Mourabaha, Salam, Istisna)", "En tant qu'analyste, je veux comparer les deux modèles afin d'en tirer des enseignements.", "Fait côté code (D31) : mourabaha, salam, istisna, exposition directe, risque commercial déplacé ; banques synthétiques, paramètres à valider"),
    ("EP-09", "A", 5, "Stress test personnel et stress test inversé par trader", "En tant que trader, je veux savoir quelle crise me ferait perdre 20 ou 30 % afin d'ajuster mon risque.", "Partiel : stress test inversé d'une banque (D31) ; stress test du portefeuille personnel à faire"),
    # ---- Sprint 6 : XAI et sentiment
    ("EP-10", "N", 6, "Importance globale et explications locales (SHAP, LIME), waterfall, summary plot", "En tant qu'utilisateur, je veux savoir pourquoi le modèle prédit ceci afin de lui faire confiance.", "Partiel : permutation, contributions exactes et attribution par perturbation (D31, D33) ; SHAP et LIME non installés"),
    ("EP-10", "N", 6, "Expliquer le stress test : pourquoi cette banque est plus vulnérable", "En tant qu'analyste, je veux des explications comparatives afin de justifier les résultats.", "Fait (ventilation des pertes par canal et attribution du remplaçant, page Stress tests)"),
    ("EP-07", "A", 6, "Fil d'actualités daté (FNSPID) et score de sentiment FinBERT par actif", "En tant que trader, je veux lire l'actualité du jour simulé afin de décider.", "Partiel : fil daté (17 repères historiques de mémoire, actualités fictives étiquetées), sentiment par lexique FR/EN explicable, filtre par actif (décision D27) ; import FNSPID et FinBERT à faire"),
    ("EP-07", "A", 6, "Impact des actualités mesuré sur l'historique (étude d'événements)", "En tant que trader, je veux connaître la réaction moyenne du prix afin de ne pas me fier à une impression.", "Partiel : mouvement du jour de parution et sur 5 séances, concordance ton/marché avec avertissement d'échantillon (décision D27) ; étude d'événements complète à faire"),
    ("EP-04", "A", 6, "Analyse fondamentale : Altman Z-score et probabilité de défaut", "En tant que trader, je veux évaluer la santé d'une entreprise afin de mieux choisir.", "Fait (D30) ; bilans automatiques depuis Yahoo à faire"),
    # ---- Sprint 7 : agent, actuariat, formation
    ("EP-08", "A", 7, "Environnement Gym et agent RL (PPO / DQN) avec journal de décisions", "En tant que trader, je veux un agent comparable à mon jeu afin d'apprendre de lui.", "Partiel : Q-learning tabulaire jugé hors échantillon (D33) ; Gym, PPO et DQN à faire"),
    ("EP-11", "A", 7, "Prime, marge de prime, probabilité de sinistre (freMTPL2)", "En tant qu'actuaire, je veux des modèles de tarification afin d'estimer la rentabilité.", "Fait (D32) ; jeu freMTPL2 à fournir (synthétique sinon)"),
    ("EP-11", "A", 7, "Provisionnement : Chain Ladder sur triangle RAA", "En tant qu'actuaire, je veux estimer les sinistres à payer afin de provisionner.", "Fait (D32) ; triangle RAA à fournir, sinon triangle synthétique"),
    ("EP-11", "B", 7, "Assurance indicielle sur matières premières (lien salle de marché / actuariat)", "En tant qu'agriculteur fictif, je veux me couvrir contre une baisse du blé afin de stabiliser mon revenu.", "À faire"),
    ("EP-12", "N", 7, "Formation 2.0 : modules, exercices avec graphiques, quiz, progression", "En tant qu'apprenant, je veux m'exercer sur de vrais graphiques afin de progresser.", "Fait (D34) : 8 leçons, quiz corrigés côté serveur, exercices liés aux pages, progression"),
    ("EP-18", "A", 7, "Machine à remonter le temps : crises réelles rejouées en aveugle avec actualités", "En tant qu'apprenant, je veux vivre le COVID de 2020 ou le WTI négatif afin d'apprendre de l'histoire.", "À faire"),
    ("EP-19", "A", 7, "Profil comportemental et post-mortem de chaque trade", "En tant que trader, je veux comprendre mes biais afin de mieux décider.", "À faire"),
    ("EP-12", "A", 7, "Ligue classée au score ajusté du risque (Sharpe, drawdown)", "En tant que participant, je veux un classement équitable afin de ne pas récompenser le hasard.", "Fait (D34) : rendement divisé par la pire baisse, date commune possible"),
    # ---- Sprint 8 : finalisation
    ("EP-13", "N", 8, "Administration : comptes, données, contenus, scénarios, modèles IA, statistiques globales", "En tant qu'admin, je veux superviser la plateforme afin de la piloter.", "Partiel : utilisateurs, rôles et audit faits (API + interface) ; données, contenus, scénarios, modèles IA à faire"),
    ("EP-13", "N", 8, "Injecteur de crises (curseurs, corrélations, titres simulés étiquetés)", "En tant qu'admin, je veux déclencher une crise afin de tester les traders.", "Fait : choc à l'ouverture avec récupération, périmètre (tous, classe, secteur, actifs), six modèles, actualité fictive liée, activation et suppression, audit (décision D27) ; corrélations réglables à faire"),
    ("EP-16", "N", 8, "Groupes et classes, import CSV d'étudiants, mode formateur", "En tant que formateur, je veux suivre ma promotion afin d'évaluer ses progrès.", "Partiel : vue du formateur (progression et portefeuilles) ; groupes multiples et import CSV à faire"),
    ("EP-01", "N", 8, "Double authentification, journal d'audit, chiffrement des données sensibles", "En tant que responsable sécurité, je veux tracer les actions sensibles afin de répondre au cahier des charges.", "Partiel : audit, verrouillage et limitation de débit faits ; double authentification et chiffrement à faire"),
    ("EP-16", "N", 8, "Questionnaire de profil de risque à l'inscription, export et suppression des données", "En tant qu'utilisateur, je veux maîtriser mes données afin de protéger ma vie privée.", "Partiel : questionnaire, export des données, gestion des appareils et changement de mot de passe faits (API + interface) ; suppression du compte à faire"),
    ("EP-03", "B", 8, "Relevé PDF mensuel de performance", "En tant que trader, je veux un relevé afin de suivre mes résultats.", "À faire"),
    ("EP-15", "N", 8, "Tests, documentation, Swagger, démonstration et soutenance", "En tant qu'équipe, je veux un projet démontrable afin de réussir la soutenance.", "Partiel : plus de 390 tests, README, DECISIONS, Swagger (/docs) ; guide de démonstration dans docs/GUIDE_DEMO.md ; soutenance à préparer"),
]

PRIORITE = {"N": "Haute", "A": "Moyenne", "B": "Basse"}
NIVEAU = {"N": "Noyau", "A": "Atout", "B": "Bonus"}


def main() -> None:
    docs = RACINE / "docs"
    docs.mkdir(exist_ok=True)

    with (docs / "backlog_jira.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Type de ticket", "Résumé", "Description", "Priorité", "Étiquettes", "Epic", "Sprint", "Statut"])
        for code, (nom, niveau) in EPICS.items():
            w.writerow(["Epic", nom, f"Niveau : {NIVEAU[niveau]}", PRIORITE[niveau], NIVEAU[niveau], nom, "", ""])
        for epic, n, sprint, resume, desc, statut in S:
            w.writerow(["Récit", resume, desc, PRIORITE[n], NIVEAU[n], EPICS[epic][0], f"Sprint {sprint}", statut])

    noms = {0: "Cadrage", 1: "Fondations", 2: "Trading de base", 3: "Risque et analyse", 4: "IA marchés",
            5: "Stress testing", 6: "XAI et sentiment", 7: "Agent, actuariat, formation", 8: "Administration et finalisation"}
    out = ["# Backlog", "",
           "Généré par `tools/generer_backlog.py` (ne pas éditer à la main). Niveaux : **Noyau** (noté, obligatoire), "
           "**Atout** (distinctif), **Bonus** (si le temps le permet). Aucune date fixée : en attente de la date de rendu.", ""]
    for s in range(9):
        out += [f"## Sprint {s} : {noms[s]}", "", "| Niveau | Epic | Récit | Statut |", "|---|---|---|---|"]
        for epic, n, sprint, resume, _d, statut in S:
            if sprint == s:
                out.append(f"| {NIVEAU[n]} | {EPICS[epic][0]} | {resume} | {statut} |")
        out.append("")
    total = {k: sum(1 for x in S if x[1] == k) for k in "NAB"}
    out += ["## Bilan", "", f"{len(S)} récits : {total['N']} noyau, {total['A']} atouts, {total['B']} bonus, dans {len(EPICS)} epics."]
    (docs / "BACKLOG.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(S)} récits, {len(EPICS)} epics -> docs/BACKLOG.md et docs/backlog_jira.csv")


if __name__ == "__main__":
    main()
