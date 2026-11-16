# Journal de l'assistant

À relire au début de chaque session, puis vérifier avec `git status`, `git log --oneline -8` et `pytest -q` (depuis backend/).

## Référence de départ (16/11/2026)

- Branche de départ : `feature/portefeuille-visuel` (dernier commit 3e8c3bb).
- Tests backend : **365 réussis, 2 échecs préexistants, 20 ignorés**.
  - Échecs : `test_credit::test_nettoyage_des_codes_speciaux_et_manquants` (KeyError: 0) et
    `test_demo::test_instantane_signale_les_donnees_synthetiques` (dépend de data/clean/DONNEES_SYNTHETIQUES.txt).
  - Les 20 ignorés : tous « could not import 'sklearn' » (vérifié avec `pytest -rs`). scipy, statsmodels, arch, shap, lime, playwright : absents.
- Instance de vérification : port 8010, `SDM_DATABASE_URL` vers `scratchpad/audit.db`, `SDM_DIRECT=0` (aucun appel Yahoo).
  Ne jamais appeler `/api/v1/actifs/{s}/profil` (appelle Wikipédia).
- Ces deux fichiers (journal et fiches) restent NON SUIVIS : plusieurs branches parallèles qui créeraient le même fichier
  provoqueraient des conflits à la fusion. À committer une fois les branches fusionnées (décision de l'utilisatrice).

## Phase A : audit de conformité (avant travaux)

Preuve « exécution » = appel réel à l'instance 8010 (script scratchpad/audit_api.py), « test » = test pytest existant.

| Section | Exigence | Statut | Preuve |
|---|---|---|---|
| S2 | Compte, connexion | COMPLET | exécution : inscription 201, connexion 200 ; tests test_auth.py ; backend/app/utilisateurs/routes.py:93-104 |
| S2 | Espace perso, historique | COMPLET | /moi, /moi/export, /executions 200 ; frontend/src/components/PageCompte.tsx |
| S2 | Personnalisation | PARTIEL | thème, apparence, mode Apprenant/Trader (Contexte.tsx:60) ; pas de disposition d'écran personnalisable |
| S3 | Donut, répartition secteur/classe | COMPLET | GraphiquesPortefeuille.tsx:14 ; /portefeuille/analyse `repartition_detail` (exécution) |
| S3 | Histogrammes de performance | COMPLET | GraphiquesPortefeuille.tsx:99 `PerformancesPositions` |
| S3 | Courbe de valeur | COMPLET | /portefeuille/historique (exécution) ; Courbe.tsx |
| S3 | P&L réalisé et latent | COMPLET | /portefeuille : pnl_realise, pnl_latent (exécution) |
| S3 | Exposition géographique | ABSENT | aucun pays dans data/univers.yaml (actifs surtout américains : à signaler, pas à inventer) |
| S3 | Concentration HHI, alertes secteur | COMPLET | risque/analyse.py:71 ; tests test_risque.py |
| S3 | Corrélations | COMPLET | risque/analyse.py:205 ; Correlations.tsx |
| S3 | Pistes de diversification | COMPLET | risque/analyse.py:120 |
| S3 | Choc sectoriel | COMPLET | analyse.py:155, /portefeuille/simuler-choc 200 |
| S3 | CRUD : ajouter, consulter | COMPLET | ordres 201, /portefeuille 200 |
| S3 | CRUD : modifier les paramètres | PARTIEL | seulement via les règles SL/TP (routes_regles.py:54) ; pas de note/objectif par position |
| S3 | CRUD : clôturer | PARTIEL | bouton « Clôturer » (PagePortefeuille.tsx:131) = vente au marché ; position fermée disparaît de la liste |
| S3 | Historique des positions clôturées | PARTIEL | /portefeuille/trades = une ligne par exécution partielle (exécution : 1 vente MSFT = plusieurs lignes) ; pas d'historique agrégé par position |
| S4 | SL/TP seuil, surveillance, déclenchement, historique, MAJ portefeuille | COMPLET | exécution : take-profit AAPL +20 % déclenché le 2021-04-20, statut « declenchee », vente dans /trades ; tests test_regles.py |
| S5 | Volatilité historique, Sharpe, Sortino | COMPLET (calcul) / PARTIEL (pédagogie) | indicateurs.py:38 ; demande ≥ 10 points de courbe (exécution : null avec 3 points) |
| S5 | VaR, CVaR historiques | COMPLET | indicateurs.py:64 ; exécution : var, cvar, var_montant |
| S5 | Drawdown max | COMPLET | indicateurs.py:28 |
| S5 | Écart-type des rendements | ABSENT (affiché) | calculé implicitement dans la volatilité, jamais exposé |
| S5 | Bêta | ABSENT | aucune occurrence backend ; `^GSPC` disponible (routes_portefeuille.py:16) |
| S5 | Covariance | ABSENT | seule la corrélation est exposée |
| S5 | Exposition sectorielle, concentration | COMPLET | concentration_detail.secteurs |
| S5 | Formule + interprétation + visuel pour chaque indicateur | PARTIEL | phrases d'aide en mode Apprenant, aucune formule affichée (grep « formule » : 0) |
| S5 | RSI distingué des mesures de risque | PARTIEL | RSI dans le graphique, aucune distinction explicite |
| S6 | Actualités datées, filtre par actif | COMPLET | /actualites?symbole= ; PageActualites.tsx:49 |
| S6 | Filtre par secteur, date, catégorie (économie, entreprises, géopolitique, banques centrales) | ABSENT | ActualiteDb sans colonne catégorie (scenarios/modeles.py:30) → changement de schéma à demander |
| S7 | Chandeliers | COMPLET | Graphique.tsx (lightweight-charts) |
| S7 | Dates, heures, minutes ; unités 1 min…1 jour | ABSENT | historique journalier seulement (timeVisible: false) ; ticks synthétiques (96/jour) non agrégés |
| S7 | MM, RSI, MACD, Bollinger | COMPLET | analyse/indicateurs.py ; tests test_indicateurs.py |
| S7 | Volumes | ABSENT (affichage) | volume renvoyé par /historique mais non tracé |
| S7 | Tendances, supports/résistances (manuel + auto), cassures, Fibonacci | ABSENT | — |
| S8 | Actif, période, stratégie, frais, Buy and Hold, pas de look-ahead | COMPLET | backtest.py (D26) ; exécution POST /backtest 200 ; test_backtest.py |
| S8 | Risques de la stratégie | COMPLET | `metriques` (backtest.py:163) |
| S8 | Régression linéaire, Monte-Carlo | ABSENT | — |
| S8 | ARIMA, GARCH | ABSENT | statsmodels / arch non installés |
| S9 | Bid/Ask, exécution partielle, annulation | COMPLET | /carnet 200, DELETE /ordres 200 ; carnet.py |
| S9 | Priorité prix-temps, file d'attente, modification d'ordre, matching entre traders | ABSENT | carnet SYNTHÉTIQUE recalculé à partir du prix (carnet.py:1-10) ; pas de modification d'ordre |
| S9 | Champs : identifiant, trader, actif, type, quantité, prix limite, date/heure, statut | COMPLET | ordre_en_dict (salle.py) |
| S10 | Chatbot consultant | ABSENT | aucun composant |
| S11 | Prédiction (sens), anomalies (MAD), régimes | PARTIEL | ia/analyses.py ; page réservée trader/formateur/admin ; sklearn absent → non exécutable ici (NON VÉRIFIÉ) |
| S11 | Isolation Forest, LOF, One-Class SVM | ABSENT | anomalies par score robuste uniquement |
| S11 | Sentiment Naive Bayes | ABSENT | lexique de mots (scenarios/sentiment.py:63) |
| S12 | Stress test banques conventionnelles/islamiques | PARTIEL | chocs matières premières, panel SYNTHÉTIQUE (stress/modele.py:200) ; pas de scénarios macro (chômage, change, inflation, taux), pas de données tunisiennes |
| S12 | Z-Score bancaire | ABSENT | credit/zscore.py = Z d'Altman (entreprises), pas le Z-score bancaire (ROA + CP/A) / σ(ROA) |
| S12 | PD | NON VÉRIFIÉ | credit/pd_modele.py ; /credit/pd/modele → 503 (sklearn absent) |
| S13 | Importance par permutation | PARTIEL / NON VÉRIFIÉ | stress/ia.py:94 (sklearn requis) |
| S13 | SHAP, LIME, PDP | ABSENT | — |
| S14 | Fréquence Poisson, sévérité Gamma, prime | COMPLET | /actuariat/modele 200 (source « synthetique », étiquetée) ; tarification.py |
| S14 | Provisions (Chain Ladder) | COMPLET | /actuariat/provision/exemple 200 ; tarification.py:185 |
| S14 | Contrats, déclaration de sinistre, scénarios par utilisateur | ABSENT | — |
| S15 | Cours, quiz, progression, ligue | COMPLET | /formation/lecons, /ligue 200 ; test_formation.py |
| S15 | Défis, scénarios de crise | PARTIEL | DefiMars2020.tsx, JeuPiege.tsx (frontend seulement, pas de suivi serveur) |
| S15 | Vidéos, PDF | ABSENT | — |
| S16 | Valeur, performance, gains/pertes, évolution des marchés, positions | COMPLET | TableauDeBord.tsx |
| S16 | Vue simple / vue pro | PARTIEL | mode Apprenant affiche des aides (Indicateur.tsx) ; même contenu sinon |
| S16 | Niveau de risque, signaux, alertes SL/TP, actualités, activité récente, répartition | ABSENT | TableauDeBord.tsx n'en contient aucun |

### Donner le rôle trader ou administrateur à un compte de développement (sans modifier le code)

Depuis `backend/`, serveur de dev arrêté ou non (SQLite accepte l'écriture) :

    .\.venv\Scripts\python.exe -m app.utilisateurs.creer_admin votre.email@exemple.com "Votre nom"

Si l'e-mail existe déjà, le compte est promu administrateur (le mot de passe demandé au clavier est alors ignoré,
`creer_admin.py:21-25`). Reconnectez-vous ensuite : le rôle est dans le jeton d'accès. Un administrateur peut ensuite
donner le rôle `trader` à d'autres comptes depuis la page Administration (`PATCH /api/v1/admin/utilisateurs/{id}`).

## Avancement

(mis à jour après chaque étape)

### P1 — Tableau de bord (FAIT)
- Branche `feature/tableau-de-bord`, commit 50f8649. Tests : 375 réussis / 2 échecs préexistants / 20 ignorés.
- Vérifié sur 8010 : GET /tableau-de-bord (niveau, alertes : stop-loss NVDA à 3,0 % → proche). tsc OK.
- Note : `frontend/tsconfig.tsbuildinfo` (artefact de tsc) non suivi, laissé en place.

### P2 — Mesures de risque (FAIT)
- Branche `feature/risque-indicateurs`, commit voir git log. Tests : 373 réussis / 2 préexistants / 20 ignorés.
- Vérifié sur 8010 : /portefeuille/analyse → beta, covariances, distribution (vol = σ√252 vérifiée). tsc OK.
- Conflit prévisible à la fusion avec P1 dans `routes_portefeuille.py` (fonction `analyse` modifiée des deux côtés).

### P3 — Historique des positions (FAIT)
- Branche `feature/positions-historique`. Tests : 370 réussis / 2 préexistants / 20 ignorés.
- Vérifié sur 8010 : AAPL clôturée par take_profit présente dans l'historique ; MSFT réalisé 8 753,02 vérifié. tsc OK.
- PROCHAINE ÉTAPE : P4 (analyse technique). En attente de décisions : schéma actualités (P5), cœur du carnet (P6), statsmodels/arch (P7).

### Portefeuille visuel renforcé (FAIT, à la demande de l'utilisatrice)
- Branche `feature/portefeuille-ux` (depuis feature/portefeuille-visuel), commit 654500e. Frontend seul ; tsc OK ; page compilée (HTTP 200).
- Calculs purs vérifiés avec Node : treemap = exemple de Bruls et al., cascade = valeur actuelle exacte, drawdown 25 %.
- Le dossier de travail est sur cette branche (les serveurs de l'utilisatrice l'affichent).
- Conflits prévisibles à la fusion avec P2/P3 : PagePortefeuille.tsx et fin de globals.css (ajouts au même endroit).

### P4 — Analyse technique (FAIT)
- Branche `feature/analyse-technique`, commit a328b52. Tests : 377 réussis / 2 préexistants / 20 ignorés. tsc OK, page /actions compilée.
- Vérifié sur 8010 : /bougies pour AAPL et BTC-USD en 1min, 5min, 15min, 1h, 1j (300 bougies, 40-70 ms, jamais après l'instant simulé).
- Tracés manuels en localStorage (confort par navigateur, non partagé).
- Le dossier de travail est sur cette branche.

### Intégration et cartes (FAIT)
- `integration/demo` = feature/portefeuille-visuel + P1 + P2 + P3 + docs + feature/portefeuille-cartes (commit f6bd475).
  Conflits résolus en gardant les deux côtés (routes_portefeuille.py : `_analyser_bac` de P1 + indice de référence de P2).
- Tests : 389 réussis / 2 préexistants / 20 ignorés ; tsc OK.
- Poussé sur GitHub (demande explicite) : integration/demo, feature/analyse-technique, feature/portefeuille-ux. main non touchée.
- Non fusionnés dans integration/demo : P4 (feature/analyse-technique) et feature/portefeuille-ux (recoupe les cartes).
- Corrections après retour visuel : « i » en double devant les infobulles (classe `info` déjà prise, renommée `info-carte`),
  unité USD lisible (12 px minimum). Vérifié sur capture : 0 + 414,10 − 2,79 = 411,31 = résultat total ; +0,41 %.
- Tout le travail poussé sur GitHub à la demande de l'utilisatrice (toutes les branches sauf main).
- PROCHAINE ÉTAPE proposée : fusionner P4 dans integration/demo, puis « prochaine ouverture » quand le marché est fermé.
