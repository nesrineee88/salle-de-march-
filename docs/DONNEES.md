# Sources de données

Statut : **vérifié** = fiche publique lue ; **non testé** = jamais téléchargé depuis l'environnement de développement (réseau bloqué). Les licences sont à confirmer avant publication.

| Besoin | Source retenue | Module | Statut | Remarque |
|---|---|---|---|---|
| Prix OHLCV (actions, cryptos, matières, indices) | Yahoo Finance via `yfinance`, instantané figé | M0 | Code testé avec un faux téléchargeur ; **réseau réel non testé** | Source non officielle. Usage pédagogique ; citer. Prix ajustés des splits et dividendes (`auto_adjust=True`). |
| Actualités datées | FNSPID (Hugging Face) : 15,7 M d'articles, 1999 à 2023, sociétés du S&P 500 | Sprint 6 | Fiche lue | Les droits d'usage sont libérés selon le dépôt GitHub. Prendre un sous-ensemble (notre fenêtre, nos 22 actions). |
| Actualités (secours) | financial-news-multisource (Hugging Face) | Sprint 6 | Fiche lue | Licences variables selon le sous-ensemble : vérifier avant de citer. |
| Banques conventionnelles | EBA, stress tests 2023 (70 banques) et 2025 (64 banques) | Sprint 5 | Fiche lue | Résultats par banque, scénarios de base et défavorable. |
| Banques islamiques | IFSB, indicateurs prudentiels par pays (T4 2013 à T4 2023) | Sprint 5 | Fiche lue | **Niveau pays, pas banque.** Conditions d'accès non vérifiées. Compléter par des banques synthétiques calibrées, **étiquetées comme telles**. À valider avec le PO. |
| Fréquence et sévérité des sinistres | freMTPL2 (Hugging Face, miroir GPL-2.0, ou OpenML) | Sprint 7 | Fiche lue | Environ 678 000 contrats ; fréquence et montants reliés par l'identifiant. |
| Provisionnement (Chain Ladder) | Triangle RAA du paquet R ChainLadder | Sprint 7 | Fiche lue | Un paquet Python équivalent existe ; installation non testée. |
| Probabilité de défaut | Give Me Some Credit (Kaggle) | Sprint 5 | Fiche lue | Compte Kaggle nécessaire. |
| Macro-économie, long terme | Pink Sheet de la Banque mondiale (mensuel depuis 1960) | Option | Fiche lue | Mensuel : analyse fondamentale uniquement. |

## Procédure pour l'équipe

```
cd backend
pip install -r requirements.txt -r requirements-data.txt
python -m pipeline tout          # télécharge, vérifie, nettoie, écrit le rapport de qualité
python -m pipeline verifier      # chaque membre vérifie qu'il a le même instantané
```

Partager l'instantané : un membre lance le téléchargement, puis envoie `data/raw/` (fichiers CSV + `MANIFEST.json`) aux autres, qui vérifient avec `verifier`. Les CSV ne vont pas sur GitHub (déjà exclus).

## Premier téléchargement réel (30 octobre 2026, sur la machine de l'utilisateur)
Constats tirés du rapport de qualité (`data/clean/RAPPORT_QUALITE.md`), sans interprétation au-delà :
- 43 actifs sur 43 téléchargés sans erreur, instantané identique à son empreinte, aucun doublon, aucun trou long, aucune ligne supprimée.
- Actions, indices et matières premières : du 28 novembre 2016 (historique préalable de 400 jours) au 30 octobre 2026 (fenêtre décidée le 31 octobre 2026 ; **les chiffres précis de couverture seront à relever après le téléchargement : ceux de 2016 à 2023 ont été mesurés, la suite non**).
- Cryptomonnaies : jusqu'au 30 octobre 2026 (à confirmer au téléchargement). Bitcoin et Litecoin depuis fin novembre 2016 ; Ethereum, BNB, XRP, Cardano et Dogecoin depuis le 9 novembre 2017 ; **Solana seulement depuis le 10 avril 2020**. Un actif qui n'existe pas encore à la date simulée n'apparaît pas dans la liste, ses cotations répondent « ne cote pas encore » et un ordre est refusé avec ce motif (testé).
- Pétrole WTI (CL=F) : 2 bougies à prix négatif conservées (cas réel autorisé, décision D7). À contrôler visuellement autour du 20 avril 2020 (clôture du contrat de mai : −37,63 dollars, selon plusieurs sources dont S&P Global et la CFTC).
- **Café (KC=F) : 278 bougies corrigées sur 1 785, soit 15,6 %** ; cuivre (HG=F) : 1. Une correction aligne le plus haut et le plus bas sur l'ouverture et la clôture, qui ne changent jamais. L'ampleur de ces corrections n'était pas dans le rapport : la version suivante du pipeline l'indique (`python -m pipeline nettoyer`) et `python -m pipeline comparer KC=F` montre les bougies avant et après.
- Séances de plus de 50 % en un jour, signalées et conservées : BNB 3, XRP 5, Cardano 3, Dogecoin 5, Litecoin 1, VIX 3, pétrole WTI 2. Les dates sont maintenant listées dans le rapport ; elles restent à contrôler sur une source indépendante.
