# Plan de fin de projet (échéance : dimanche 1er novembre 2026, matin)

Journal de travail tenu à jour pendant la fin de projet. Les statuts sont ceux du code livré, pas des intentions.

## Cahier des charges : couverture visée
| Bloc du cahier | Module | État |
|---|---|---|
| 3.1 Interface, tableau de bord, positions, performances, indicateurs | Interface v2 (pages, portefeuille, risque) | Fait |
| 3.2 Trading, exécution, historique, risque avant ordre, stop-loss, take-profit, exposition, diversification | Moteur, règles automatiques, alertes avant achat | Fait |
| 3.2 Analyse technique | Indicateurs sur le graphique | Fait |
| 3.2 Analyse fondamentale | Score Z d'Altman (2 versions), probabilité de défaut avec contributions exactes | Fait (entreprises : saisie manuelle et exemples fictifs ; chargement automatique des bilans Yahoo à faire) |
| 3.2 Backtesting, tests et comparaison de stratégies | Page Stratégies | Fait (6 stratégies, comparaison, moitiés de période) |
| 3.3 Formation, quiz, exercices, scénarios, concours, progression | Page Formation : 8 leçons, 24 questions corrigées côté serveur, ligue (date commune possible), vue du formateur, leçons activables | Fait (contenu rédigé par l'assistant : à relire) |
| 3.4.1 Prédiction, tendances, anomalies, recommandations | Page IA : prédiction en marche avant contre références, anomalies robustes, régimes (mélange gaussien), optimiseur (variance minimale, parité de risque) | Fait |
| 3.4.2 Agent intelligent de trading | Q-learning tabulaire jugé hors échantillon | Fait (fragile par nature, dit tel quel) |
| 3.4.3 Analyse des sentiments | Fil d'actualités, sentiment, impact | Fait (lexique ; FinBERT et FNSPID à faire) |
| 3.5 AI Stress Testing bancaire (conventionnelle / islamique) | Page Stress tests : modèle structurel, 12 banques synthétiques, chocs mesurés sur les vraies séries, test inversé, remplaçant d'IA | Fait (paramètres à valider avec l'encadrant) |
| 3.6 XAI | Contributions exactes (logistique, ventilation par canal), importance par permutation, attribution par perturbation | Fait |
| 3.7 Actuariat | Prime (Poisson × Gamma), marge, probabilité de sinistre, Chain Ladder | Fait (jeu freMTPL2 à fournir ; synthétique sinon) |
| 4 Sécurité | Argon2id, JWT, rôles, audit, verrouillage | Fait (voir limites) |
| 5 Administration | Utilisateurs, audit, crises, actualités, statistiques, performances, modèles IA, paramètres (lecture seule) | Fait |
| Hors cahier | Fenêtre jusqu'au 30 octobre 2026 ; mode Direct (bêta) | Fait côté code ; téléchargement réel et flux Yahoo à vérifier sur un poste connecté |

## Règles de ce plan
- Aucun résultat chiffré d'IA n'est présenté comme performant sans évaluation hors échantillon et comparaison à une méthode simple.
- Toute donnée fictive est étiquetée comme telle dans l'interface.
- Ce qui n'a pas pu être testé (réseau réel, vrais jeux de données) est écrit dans « Limites connues ».

## Ordre de travail
1. Backtesting et comparaison de stratégies
2. Crises, actualités, sentiment, impact
3. Analyse fondamentale et score de crédit
4. Formation, ligue, mode formateur
5. IA : prévision, anomalies, régimes, agent, optimiseur, XAI
6. Stress tests bancaires
7. Actuariat
8. Administration, relevé imprimable, documentation, guide de démonstration
