# Guide de démonstration (15 minutes)

Avant la démonstration : lancer `python -m pipeline tout` (vrais prix jusqu'au 30 octobre 2026), `pip install -r requirements-ia.txt`, créer un administrateur (`python -m app.utilisateurs.creer_admin`), puis créer un compte apprenant et un compte trader (l'administrateur change les rôles dans « Administration > Utilisateurs »). Si possible, placer les jeux Kaggle dans `data/externes/` et ré-entraîner (« Administration > Données et IA »).

## Parcours conseillé
1. **Connexion et profil de risque** (compte apprenant). Répondre au questionnaire : la tolérance à la perte est fixée.
2. **Premier ordre** (Marchés > Actions). Acheter une action, poser un stop-loss à −30 % et une prise de profit à +50 % (panneau « Règles »). Montrer l'alerte avant achat si la position est trop concentrée.
3. **Faire avancer le temps** (« Lancer », vitesse « 1 semaine = 1 heure »), ou cliquer un repère de la frise (Covid, mars 2020). Montrer la courbe de valeur, la VaR, le drawdown dans « Portefeuille ».
4. **Matières premières** : ouvrir le WTI à la date du 20 avril 2020 (prix négatif, décision D7).
5. **Backtesting** (Analyse > Stratégies) : comparer croisement de moyennes, RSI et MACD au bon vieil achat-conservation ; montrer les deux moitiés et l'avertissement de comparaison multiple.
6. **Crise injectée** (compte admin, Administration > Crises) : modèle « Choc pétrolier » à une date future du joueur ; le joueur voit le choc, l'actualité fictive et ses règles automatiques se déclencher.
7. **Actualités et sentiment** : fil daté, ton du texte, mouvement des cours ensuite ; l'étude « le ton prédit-il le marché ? » avec son avertissement d'échantillon.
8. **Risque de crédit** : exemple « zone grise », puis la PD avec ses contributions.
9. **Stress tests bancaires** (point fort sur les matières premières) : choc pétrolier et agricole ; comparer les 12 banques conventionnelles et islamiques ; détailler une banque islamique (mourabaha en stock, salam non couvert, risque commercial déplacé) ; test inversé ; comparaison des trois modèles et explication locale.
10. **IA** (compte trader) : prédiction en marche avant (dire clairement quand « dans le bruit »), régimes, agent hors échantillon, optimiseur.
11. **Actuariat** : prime d'un conducteur de 22 ans contre 55 ans ; provisions par Chain Ladder.
12. **Formation** : une leçon, un quiz corrigé ; la ligue (avec date commune) ; la vue « Ma classe » (compte formateur).
13. **Administration** : statistiques, performances, modèles enregistrés, journal d'audit.
14. **Direct (bêta)** si le réseau le permet (sinon `SDM_DIRECT_DEMO=1`, en le disant).

## Ce qu'il faut dire franchement
- Ticks et carnet d'ordres **simulés** ; heures de séance approximatives.
- Banques, bilans, emprunteurs, assurés, triangle : **synthétiques** tant que les jeux Kaggle ne sont pas chargés ; l'interface le signale.
- Paramètres des stress tests **pédagogiques**, à valider avec l'encadrant.
- Le sentiment par lexique est simple, sa précision n'est pas mesurée ; les repères historiques sont de mémoire.
- La prédiction du sens de la séance ne bat en général pas le hasard : c'est le résultat attendu, pas un échec.
- Le mode Direct est une bêta jamais éprouvée sur le vrai flux Yahoo depuis l'environnement de développement.
- Pas encore : confirmation d'e-mail, double authentification, HTTPS (voir « Limites connues » de `docs/DECISIONS.md`).
