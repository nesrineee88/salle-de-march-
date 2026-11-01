# Simulateur de salle de marché

Projet Informatique Finance, ESPRIT, 2026-2027. Nouvelle base de code (interface refaite de zéro).

## État

| Module | État |
|---|---|
| M0 Données : catalogue, pipeline, ticks, horloge, API de cotations | Fait (sur données synthétiques ; téléchargement réel à lancer sur une machine avec réseau) |
| M1 Trading : ordres marché / limite / stop, carnet simulé, portefeuille | Fait (moteur + API, en mémoire) |
| Utilisateurs : inscription, connexion, rôles, audit, profil de risque, bac à sable par utilisateur | Fait (API + interface) |
| Base de données : comptes, sessions, audit, ordres, positions, exécutions, horloge ; migrations Alembic | Fait, testé sur SQLite et PostgreSQL 16 |
| Interface : tableau de bord, une page par marché (actions, cryptomonnaies, matières premières), portefeuille complet (risque, répartition, corrélations, trades), compte (profil de risque, appareils, mot de passe, export), administration | Fait (v2, testée dans un navigateur ; voir `docs/DESIGN.md`) |
| Risque du portefeuille : VaR, CVaR, volatilité, drawdown, Sharpe, Sortino, concentration, diversification, profil comparé au risque réel | Fait (conventions en D19) |
| Analyse technique : SMA, EMA, Bollinger, RSI, MACD, ATR sur le graphique, sans fuite du futur | Fait (conventions en D22) |
| Thèmes sombre et clair | Fait (D23) |
| Règles automatiques (stop-loss en %, prise de profit partielle, stop suiveur, achat complémentaire) et vérification du risque avant achat | Fait (D25) ; **nécessite `alembic upgrade head` (migration 0003)** |
| Le reste | Voir `docs/BACKLOG.md` |

## Lancer

```
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pytest                                                    # plus de 390 tests, sans réseau (SQLite)

pip install -r requirements-ia.txt                        # IA, risque de crédit, stress tests, actuariat (scikit-learn, scipy)

pip install -r requirements-data.txt
python -m pipeline tout                                   # données réelles (réseau nécessaire)
python -m pipeline comparer KC=F                          # bougies corrigées d'un actif : brut contre propre
python -m app.utilisateurs.creer_admin admin@exemple.com "Nom"   # premier administrateur (mot de passe demandé)
export SDM_JWT_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"   # obligatoire si SDM_ENV=production
uvicorn app.main:app --reload                             # API sur http://127.0.0.1:8000/docs
```

Sans données, l'API répond 503 avec le message qui indique quoi lancer. Presque toutes les routes exigent
une connexion (`POST /api/v1/auth/connexion`, puis l'en-tête `Authorization: Bearer ...`). En développement
la base est un fichier SQLite ; en production, définir `SDM_DATABASE_URL` vers PostgreSQL.

**Mise à jour depuis une version précédente.** Si le serveur refuse de démarrer en disant que la base de développement
« date d'une version précédente », arrêtez-le et supprimez `data/utilisateurs.db` (ce sont vos comptes de test), puis
recréez l'administrateur. Avec PostgreSQL, lancez `alembic upgrade head`.

## Sous Windows (PowerShell)

```
cd salle-de-marche\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
pytest
python -m pipeline demo          # OU : pip install -r requirements-data.txt puis python -m pipeline tout (vrais prix)
python -m app.utilisateurs.creer_admin admin@exemple.com "Nom"
uvicorn app.main:app --reload
```

Dans un second terminal, l'interface :

```
cd salle-de-marche\frontend
npm install
npm run dev
```

Ouvrir http://localhost:3000. L'interface appelle l'API sur le port 8000 (autre adresse : variable `API_URL`).
`python -m pipeline demo` génère des données **au hasard** (bandeau d'avertissement dans l'interface) pour voir l'écran sans réseau.

Pour tester l'API seule, ouvrir http://127.0.0.1:8000/docs : `POST /api/v1/auth/inscription`, `POST /api/v1/auth/connexion`,
copier `access_token`, cliquer sur **Authorize** et le coller. Essayer ensuite `POST /api/v1/horloge/aller-a`
(par exemple `2020-03-09T17:00:00`), `GET /api/v1/cotations/AAPL`, `POST /api/v1/ordres`, `GET /api/v1/portefeuille`.

## PostgreSQL (recommandé pour la démonstration devant le jury)

```
copy .env.example .env            # puis choisir un mot de passe
docker compose up -d              # base PostgreSQL 16
cd backend
pip install -r requirements-postgres.txt
$env:SDM_DATABASE_URL = "postgresql+psycopg://simulateur:VOTRE_MOT_DE_PASSE@127.0.0.1:5432/simulateur"
alembic upgrade head              # crée les tables (migrations 0001 et 0002 ; à relancer après chaque mise à jour du projet)
python -m app.utilisateurs.creer_admin admin@exemple.com "Nom"
uvicorn app.main:app
```

Sans `SDM_DATABASE_URL`, l'API utilise un fichier SQLite dans `data/` (suffisant pour développer).
Avec `SDM_ENV=production`, définir aussi `SDM_JWT_SECRET` ; le schéma n'est alors géré que par Alembic.
Les ordres, positions et l'horloge de chaque utilisateur sont enregistrés : un redémarrage du serveur ne les efface plus.
Pour lancer les tests sur PostgreSQL : `$env:SDM_TEST_POSTGRES = "postgresql+psycopg://..."` puis `pytest` (efface les tables de cette base !).

## Organisation

```
data/univers.yaml     43 actifs, fenêtre 2018 à octobre 2026, sessions
data/raw, data/clean  instantané figé et données nettoyées (CSV non versionnés)
backend/app/marche/   catalogue, stockage, ticks, horloge, moteur de cotation
backend/app/trading/  ordres, carnet synthétique, exécution, portefeuille
frontend/             interface Next.js (src/components, src/lib, src/app/globals.css)
backend/app/utilisateurs/  comptes, sécurité (Argon2id, JWT), rôles, audit, profil de risque
backend/app/analyse/  indicateurs techniques, backtesting
backend/app/scenarios/ crises injectées, actualités datées, sentiment
backend/app/credit/   score Z d'Altman, probabilité de défaut
backend/app/stress/   stress tests de banques conventionnelles et islamiques, remplaçant d'IA
backend/app/actuariat/ prime d'assurance, Chain Ladder
backend/app/ia/       prédiction, anomalies, régimes, optimiseur, agent
backend/app/formation/ leçons, quiz, ligue, vue du formateur
backend/app/direct/   mode Direct (bêta)
backend/pipeline/     téléchargement, nettoyage, rapport de qualité
backend/tests/        tests (données synthétiques uniquement)
docs/                 décisions, sources, backlog (CSV importable dans Jira)
tools/                générateur du backlog
```

Avant toute mise en ligne : voir la liste des limites dans `docs/DECISIONS.md` (HTTPS, confirmation d'e-mail, double authentification, migrations).


## Jeux de données facultatifs (dossier `data/externes/`)

| Fichier | Sert à | Sans lui |
|---|---|---|
| `cs-training.csv` (Give Me Some Credit, Kaggle) | probabilité de défaut | échantillon synthétique, signalé partout |
| `freMTPL2freq.csv` et `freMTPL2sev.csv` (assurance auto) | tarification | échantillon synthétique, signalé partout |

Ensuite, dans l'administration, onglet « Données et IA » : bouton « Ré-entraîner ».

## Mode Direct (bêta)

Bouton « ◉ Direct (bêta) » dans la barre du temps : l'horloge suit l'heure réelle et les prix des derniers jours viennent de Yahoo Finance (cours souvent différés).
`SDM_DIRECT=0` le désactive ; `SDM_DIRECT_DEMO=1` le remplace par un flux **inventé**, signalé, pour tester sans Internet.
Voir `docs/DECISIONS.md`, D29.
