# Banques réelles : `banques_reelles.csv`

Neuf banques saoudiennes, chiffres au **31/12/2025**, en **milliers de riyals (SAR)**, un seul régulateur.
Quatre banques islamiques (Al Rajhi, Alinma, Albilad, AlJazira), cinq conventionnelles (SNB, Riyad Bank, Saudi Awwal,
Saudi Fransi, SAIB). En Arabie saoudite, les banques conventionnelles ont aussi des guichets islamiques : elles sont mixtes.

## Source de chaque chiffre

Chaque ligne vient du **rapport Pilier 3** publié par la banque elle-même (colonne `source_url`) :

| Colonnes | Tableau | Page |
|---|---|---|
| `cet1_capital`, `actifs_ponderes`, `cet1_ratio` | KM1 (indicateurs clés) | `page_km1` |
| `prets_defaut`, `prets_sains`, `provisions`, `prets_nets` | CR1 (qualité du crédit, ligne « Loans ») | `page_cr1` |

`date_collecte` donne le jour du téléchargement, `sha256` l'empreinte du PDF lu. `estime = non` : aucune valeur n'est estimée.
`statut = a_relire` : une personne de l'équipe doit encore comparer chaque chiffre à son PDF. Seule cette personne le passe à `relu`.

## Refaire la collecte

```powershell
cd backend
.\.venv\Scripts\python.exe -m pipeline.banques aljazira   # une banque, environ 25 s
.\.venv\Scripts\python.exe -m pipeline.banques            # les neuf, environ une minute
```

Pour chaque banque, le script :

1. lit `robots.txt` et respecte la pause demandée (20 s pour AlJazira). Un refus ou un fichier illisible arrête tout ;
2. télécharge le PDF en https, certificat vérifié, User-Agent générique `simulateur-pedagogique/1.0`, sans information personnelle ;
3. compare l'empreinte SHA-256 à celle du CSV ;
4. extrait le texte des deux pages citées avec `pdftotext` (fourni avec Git pour Windows) ;
5. vérifie que chaque chiffre du CSV figure sur sa page, à mille riyals près.

Le script **ne modifie jamais le CSV**. Les PDF restent dans `data/raw/banques/`, ignoré par Git.
Sans internet, il utilise la copie locale et le dit.

Dernière exécution : 22/11/2026, 9 banques sur 9, 54 chiffres sur 54 retrouvés, 9 empreintes identiques.

## Contrôles au chargement

`backend/app/stress/donnees_reelles.py` refuse le fichier, en nommant la ligne et la colonne, si :

- une valeur manque, n'est pas un nombre ou est négative ;
- `|cet1_capital / actifs_ponderes − cet1_ratio| ≥ 0,00011` (le ratio publié est arrondi à 0,01 %) ;
- `|prets_defaut + prets_sains − provisions − prets_nets| > 2` milliers ;
- `ratio_type` n'est pas `CET1`, ou l'adresse n'est pas en https.

Yahoo Finance n'est pas utilisé : son robots.txt refuse la collecte sur son API.
