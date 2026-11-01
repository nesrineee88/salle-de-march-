# Backlog

Généré par `tools/generer_backlog.py` (ne pas éditer à la main). Niveaux : **Noyau** (noté, obligatoire), **Atout** (distinctif), **Bonus** (si le temps le permet). Aucune date fixée : en attente de la date de rendu.

## Sprint 0 : Cadrage

| Niveau | Epic | Récit | Statut |
|---|---|---|---|
| Noyau | Interface, UX et design | Maquettes de l'écran principal en mode Apprenant / Trader / Admin | Remplacé par l'interface codée (docs/DESIGN.md) : à faire valider par le PO |
| Noyau | DevOps, qualité et documentation | Dépôt Git, branches, CI et conventions | À faire |
| Noyau | DevOps, qualité et documentation | Conteneuriser avec Docker Compose (PostgreSQL, API) | Partiel : docker-compose.yml pour PostgreSQL écrit (non lancé ici, pas de Docker) ; conteneur de l'API à faire |
| Noyau | DevOps, qualité et documentation | Migrations de base de données (Alembic) | Fait (migration initiale testée sur SQLite et PostgreSQL 16) |
| Noyau | Données de marché | Choisir et figer les sources de données (décisions D2 à D9) | Fait (docs/DECISIONS.md) |

## Sprint 1 : Fondations

| Niveau | Epic | Récit | Statut |
|---|---|---|---|
| Noyau | Données de marché | Catalogue des actifs (43 actifs, 4 classes) | Fait (code) |
| Noyau | Données de marché | Télécharger et figer un instantané des prix avec manifest SHA-256 | Fait (code, à lancer sur une machine avec accès réseau) |
| Noyau | Données de marché | Nettoyer les données et produire un rapport de qualité | Fait (code) |
| Noyau | Données de marché | Stocker les séries temporelles dans PostgreSQL / TimescaleDB | À faire (les prix sont lus depuis des fichiers CSV chargés en mémoire ; à migrer avec la couche « scénario » de l'admin) |
| Noyau | Données de marché | Horloge de replay (facteur réglable, pause, aller à une date) | Fait (API + interface avec frise et repères) |
| Noyau | Données de marché | Ticks intraday synthétiques cohérents avec les bougies, sans fuite du futur | Fait (code) |
| Noyau | Authentification et sécurité | Inscription, connexion, JWT, hachage Argon2 | Fait (API + interface) |
| Noyau | Gestion des utilisateurs | Rôles et permissions (Apprenant, Trader, Formateur, Admin) | Fait (API) |
| Noyau | Interface, UX et design | Design system et coque de l'application (navigation, thème, trilingue FR/EN/AR) | Fait (thèmes sombre et clair, validé par l'utilisateur ; anglais et arabe à faire) |

## Sprint 2 : Trading de base

| Niveau | Epic | Récit | Statut |
|---|---|---|---|
| Noyau | Trading et portefeuille virtuel | Capital virtuel, ordres au marché, positions et historique | Fait (moteur + API + interface + base de données) |
| Noyau | Trading et portefeuille virtuel | Enregistrer ordres, positions, exécutions et horloge en base | Fait (testé sur SQLite et PostgreSQL 16, redémarrage réel vérifié) |
| Noyau | Carnet d'ordres et exécution | Carnet d'ordres simulé (liquidité par bots, priorité prix puis temps) | Fait en v1 (liquidité synthétique ; bots à venir) |
| Noyau | Carnet d'ordres et exécution | Ordres limite, stop, annulation, exécution partielle | Fait (moteur + API) |
| Noyau | Carnet d'ordres et exécution | Frais, spread, slippage et impact de marché | Fait (moteur) |
| Noyau | Interface, UX et design | Pages séparées : tableau de bord, un marché par page, portefeuille, compte, administration | Fait (interface testée dans un navigateur ; un seul portefeuille pour les trois marchés, décision D20) |
| Noyau | Trading et portefeuille virtuel | Page Portefeuille : valeur au fil du temps contre le S&P 500, répartition, trades clôturés, profil de risque comparé au risque réel | Fait (historique de valeur enregistré en base, migration 0002) |
| Noyau | Authentification et sécurité | Gérer ses appareils connectés, changer de mot de passe, se déconnecter partout | Fait (API + interface) |
| Noyau | Interface, UX et design | Écran Marchés : liste des actifs, graphique en bougies, panneau d'ordre | Fait (une page par marché : actions, cryptomonnaies, matières premières ; liste, bougies, ordre, carnet) |
| Noyau | Analyse technique, fondamentale et backtesting | Indicateurs techniques : SMA, EMA, RSI, MACD, Bollinger, ATR | Fait (SMA 20 et 50, EMA 20, Bollinger, RSI, MACD sur le graphique, ATR dans l'en-tête ; aide en mode Apprenant ; conventions D22) |

## Sprint 3 : Risque et analyse

| Niveau | Epic | Récit | Statut |
|---|---|---|---|
| Noyau | Gestion du risque | Stop-loss et take-profit (fixe, suiveur, ATR, par paliers, OCO / bracket) | Partiel : stop-loss en %, prise de profit partielle, stop suiveur, achat complémentaire et annulation croisée (OCO) faits (D25) ; stops par ATR et par paliers, et bracket à la pose de l'ordre, à faire |
| Noyau | Gestion du risque | Disjoncteur de portefeuille et délai avant rachat après un stop | À faire |
| Noyau | Gestion du risque | Feu tricolore de risque avant chaque ordre | À faire |
| Noyau | Gestion du risque | Indicateurs : VaR, CVaR, volatilité, drawdown, Sharpe, corrélations, concentration | Fait (page Portefeuille : VaR et CVaR historiques, volatilité, drawdown, Sharpe, Sortino, corrélations, concentration, diversification ; conventions D19) |
| Noyau | Gestion du risque | Vérification du risque avant un achat (concentration, perte possible comparée au profil, liquidités, volatilité) | Fait (alertes non bloquantes dans le ticket d'ordre ; seuils pédagogiques, D25) |
| Noyau | Trading et portefeuille virtuel | Levier, marge et appel de marge | À faire |
| Atout | Gestion du risque | Optimiseur de portefeuille (Markowitz, risk parity) et alerte de fausse diversification | Partiel : variance minimale et parité de risque avec contribution au risque (page IA, D33) ; alerte de fausse diversification à faire |
| Noyau | Analyse technique, fondamentale et backtesting | Backtesting et comparaison de stratégies (momentum, croisement de moyennes, mean reversion, pairs trading) | Partiel : achat-conservation, croisement de moyennes, RSI, MACD, Bollinger, momentum, comparés sur la période et sur chaque moitié (page Stratégies, décision D26) ; pairs trading à faire |
| Atout | Analyse technique, fondamentale et backtesting | Laboratoire de stratégies sans code avec test hors échantillon (alerte de surapprentissage) | À faire |
| Atout | Analyse technique, fondamentale et backtesting | Courbe à terme des matières premières (contango, backwardation) et saisonnalité | À faire |

## Sprint 4 : IA marchés

| Niveau | Epic | Récit | Statut |
|---|---|---|---|
| Noyau | IA : prédiction et anomalies | Pipeline de variables et modèles de base (ARIMA, GARCH, Random Forest, XGBoost) | Partiel : régression logistique et arbres boostés en marche avant contre références naïves (D33) ; ARIMA, GARCH, XGBoost à faire |
| Noyau | IA : prédiction et anomalies | Modèles LSTM / GRU et comparaison RMSE / MAE (suivi MLflow) | À faire |
| Noyau | IA : prédiction et anomalies | Détection d'anomalies (Isolation Forest, autoencodeur) et alertes | Partiel : anomalies par score robuste (médiane, MAD) avec explication (page IA, D33) ; Isolation Forest et autoencodeur à faire |
| Atout | IA : prédiction et anomalies | Détection de régime de marché (haussier, baissier, forte volatilité) | Fait (mélange gaussien à 3 régimes, page IA, D33) |

## Sprint 5 : Stress testing

| Niveau | Epic | Récit | Statut |
|---|---|---|---|
| Noyau | AI Stress Testing bancaire | Données bancaires : EBA (conventionnelles) et IFSB + synthétiques étiquetées (islamiques) | À faire (accord du PO sur les données islamiques) |
| Noyau | AI Stress Testing bancaire | Générateur de scénarios (taux, krach, récession, défauts, chocs combinés) | Partiel : six modèles de crises sur les matières premières et les actions (D27) et chocs historiques mesurés (D31) ; taux et défauts à faire |
| Noyau | AI Stress Testing bancaire | Modèles ML / DL de pertes, NPL, CET1, liquidité ; score de résilience | Partiel : modèle structurel et remplaçant statistique du CET1 (D31) ; pertes sur prêts non performants et liquidité à faire |
| Noyau | AI Stress Testing bancaire | Comparaison conventionnelles / islamiques (Mourabaha, Salam, Istisna) | Fait côté code (D31) : mourabaha, salam, istisna, exposition directe, risque commercial déplacé ; banques synthétiques, paramètres à valider |
| Atout | AI Stress Testing bancaire | Stress test personnel et stress test inversé par trader | Partiel : stress test inversé d'une banque (D31) ; stress test du portefeuille personnel à faire |

## Sprint 6 : XAI et sentiment

| Niveau | Epic | Récit | Statut |
|---|---|---|---|
| Noyau | Explainable AI (XAI) | Importance globale et explications locales (SHAP, LIME), waterfall, summary plot | Partiel : permutation, contributions exactes et attribution par perturbation (D31, D33) ; SHAP et LIME non installés |
| Noyau | Explainable AI (XAI) | Expliquer le stress test : pourquoi cette banque est plus vulnérable | Fait (ventilation des pertes par canal et attribution du remplaçant, page Stress tests) |
| Atout | IA : analyse des sentiments et actualités | Fil d'actualités daté (FNSPID) et score de sentiment FinBERT par actif | Partiel : fil daté (17 repères historiques de mémoire, actualités fictives étiquetées), sentiment par lexique FR/EN explicable, filtre par actif (décision D27) ; import FNSPID et FinBERT à faire |
| Atout | IA : analyse des sentiments et actualités | Impact des actualités mesuré sur l'historique (étude d'événements) | Partiel : mouvement du jour de parution et sur 5 séances, concordance ton/marché avec avertissement d'échantillon (décision D27) ; étude d'événements complète à faire |
| Atout | Gestion du risque | Analyse fondamentale : Altman Z-score et probabilité de défaut | Fait (D30) ; bilans automatiques depuis Yahoo à faire |

## Sprint 7 : Agent, actuariat, formation

| Niveau | Epic | Récit | Statut |
|---|---|---|---|
| Atout | IA : agent intelligent de trading | Environnement Gym et agent RL (PPO / DQN) avec journal de décisions | Partiel : Q-learning tabulaire jugé hors échantillon (D33) ; Gym, PPO et DQN à faire |
| Atout | Module actuariat | Prime, marge de prime, probabilité de sinistre (freMTPL2) | Fait (D32) ; jeu freMTPL2 à fournir (synthétique sinon) |
| Atout | Module actuariat | Provisionnement : Chain Ladder sur triangle RAA | Fait (D32) ; triangle RAA à fournir, sinon triangle synthétique |
| Bonus | Module actuariat | Assurance indicielle sur matières premières (lien salle de marché / actuariat) | À faire |
| Noyau | Formation et gamification | Formation 2.0 : modules, exercices avec graphiques, quiz, progression | Fait (D34) : 8 leçons, quiz corrigés côté serveur, exercices liés aux pages, progression |
| Atout | Replay et scénarios historiques | Machine à remonter le temps : crises réelles rejouées en aveugle avec actualités | À faire |
| Atout | Coaching et profil comportemental | Profil comportemental et post-mortem de chaque trade | À faire |
| Atout | Formation et gamification | Ligue classée au score ajusté du risque (Sharpe, drawdown) | Fait (D34) : rendement divisé par la pire baisse, date commune possible |

## Sprint 8 : Administration et finalisation

| Niveau | Epic | Récit | Statut |
|---|---|---|---|
| Atout | Données de marché | Mode Direct (bêta) : prix de marché récents à l'heure réelle, en plus du rejeu historique | Partiel : code et tests faits avec un faux flux ; l'appel réel à Yahoo Finance n'a jamais été exécuté depuis l'environnement de développement (réseau bloqué), à essayer sur un poste connecté |
| Noyau | Administration et crises | Administration : comptes, données, contenus, scénarios, modèles IA, statistiques globales | Partiel : utilisateurs, rôles et audit faits (API + interface) ; données, contenus, scénarios, modèles IA à faire |
| Noyau | Administration et crises | Injecteur de crises (curseurs, corrélations, titres simulés étiquetés) | Fait : choc à l'ouverture avec récupération, périmètre (tous, classe, secteur, actifs), six modèles, actualité fictive liée, activation et suppression, audit (décision D27) ; corrélations réglables à faire |
| Noyau | Gestion des utilisateurs | Groupes et classes, import CSV d'étudiants, mode formateur | Partiel : vue du formateur (progression et portefeuilles) ; groupes multiples et import CSV à faire |
| Noyau | Authentification et sécurité | Double authentification, journal d'audit, chiffrement des données sensibles | Partiel : audit, verrouillage et limitation de débit faits ; double authentification et chiffrement à faire |
| Noyau | Gestion des utilisateurs | Questionnaire de profil de risque à l'inscription, export et suppression des données | Partiel : questionnaire, export des données, gestion des appareils et changement de mot de passe faits (API + interface) ; suppression du compte à faire |
| Bonus | Trading et portefeuille virtuel | Relevé PDF mensuel de performance | À faire |
| Noyau | DevOps, qualité et documentation | Tests, documentation, Swagger, démonstration et soutenance | Partiel : plus de 390 tests, README, DECISIONS, Swagger (/docs) ; guide de démonstration dans docs/GUIDE_DEMO.md ; soutenance à préparer |

## Bilan

64 récits : 47 noyau, 15 atouts, 2 bonus, dans 19 epics.
