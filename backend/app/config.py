"""Chemins et paramètres. Tout peut être surchargé par variable d'environnement."""
import os
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("SDM_DATA_DIR", RACINE / "data"))
RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
UNIVERS_YAML = DATA_DIR / "univers.yaml"

# Facteur de vitesse par défaut de l'horloge : 168 = « 1 semaine simulée = 1 heure réelle ».
FACTEUR_DEFAUT = float(os.environ.get("SDM_FACTEUR_DEFAUT", "168"))
NB_TICKS_PAR_BARRE = int(os.environ.get("SDM_NB_TICKS", "96"))

# --- Utilisateurs et sécurité ---------------------------------------------------------------
ENVIRONNEMENT = os.environ.get("SDM_ENV", "dev")                  # "production" durcit les contrôles
URL_BASE = os.environ.get("SDM_DATABASE_URL", f"sqlite:///{DATA_DIR / 'utilisateurs.db'}")
# En production : PostgreSQL, p. ex. postgresql+psycopg://utilisateur:motdepasse@localhost:5432/simulateur
JWT_SECRET = os.environ.get("SDM_JWT_SECRET")                     # obligatoire en production
ACCES_DUREE_MIN = int(os.environ.get("SDM_ACCES_DUREE_MIN", "15"))
REFRESH_DUREE_JOURS = int(os.environ.get("SDM_REFRESH_DUREE_JOURS", "7"))
MAX_ECHECS_CONNEXION = int(os.environ.get("SDM_MAX_ECHECS", "5"))
VERROU_DUREE_MIN = int(os.environ.get("SDM_VERROU_DUREE_MIN", "15"))
LIMITE_REQUETES_AUTH = int(os.environ.get("SDM_LIMITE_AUTH", "30"))   # par IP, par fenêtre de 5 minutes
CAPITAL_INITIAL_DEFAUT = float(os.environ.get("SDM_CAPITAL_INITIAL", "100000"))

# Présent quand les données du dossier clean/ sont des données de DÉMONSTRATION générées au hasard.
MARQUEUR_SYNTHETIQUE = CLEAN_DIR / "DONNEES_SYNTHETIQUES.txt"

# Mode Direct (bêta) : flux de prix récents depuis Yahoo Finance. SDM_DIRECT=0 pour le désactiver.
DIRECT_ACTIF = os.environ.get("SDM_DIRECT", "1") != "0"
DIRECT_DEMO = os.environ.get("SDM_DIRECT_DEMO", "0") == "1"      # flux inventé, pour tester sans Internet (jamais de vrais cours)

# --- Connexion avec Google / GitHub (facultative) ------------------------------------------------
# Un fournisseur n'apparaît dans l'interface que si son identifiant ET son secret sont définis.
# URL_FRONT : adresse du site vue par le navigateur (le front relaie /api vers le backend).
URL_FRONT = os.environ.get("SDM_URL_FRONT", "http://localhost:3000").rstrip("/")
GOOGLE_CLIENT_ID = os.environ.get("SDM_GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("SDM_GOOGLE_CLIENT_SECRET")
GITHUB_CLIENT_ID = os.environ.get("SDM_GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get("SDM_GITHUB_CLIENT_SECRET")
