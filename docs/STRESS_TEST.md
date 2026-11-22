# Module 3 : Stress test bancaire

**La question** : le portefeuille de prêts de chaque banque reste-t-il stable en crise ? Combien de prêts font défaut, combien
la banque perd, son capital tient-il ?

« Portefeuille » désigne ici les prêts des banques, pas le portefeuille d'actions de l'utilisateur.

## Données

Neuf banques saoudiennes réelles, au 31/12/2025, tirées de leurs rapports Pilier 3 : 4 islamiques, 5 conventionnelles mixtes.
Détail, sources et collecte : [`data/externes/README_BANQUES.md`](../data/externes/README_BANQUES.md).
Les chiffres restent côté serveur : le navigateur ne reçoit que les résultats des simulations. L'application lit seulement le CSV : elle marche sans internet.

## Formules

```text
1. PD de départ   = prêts en défaut / (prêts en défaut + prêts sains)
2. PD de crise    = Φ( (Φ⁻¹(PD) + √ρ · Φ⁻¹(q)) / √(1 − ρ) )            (Vasicek, si le scénario a un quantile q)
   ρ              = 12 % · w + 24 % · (1 − w),  w = (1 − e^(−50·PD)) / (1 − e^(−50))
3. PD stressée    = min(100 %, PD de crise + Δ)                        (Δ : défauts en plus, en points)
4. Perte          = prêts bruts × (PD stressée − PD de départ) × LGD
5. CET1 après     = (capital CET1 − perte) / actifs pondérés
6. Pire cas       = (capital − seuil × actifs pondérés) / (prêts bruts × LGD)
```

Seuils : 4,5 % (minimum), 7 % (avec le coussin de conservation).

## Scénarios : un type de crise et une intensité

Le catalogue est dans `backend/app/stress/scenarios.py`. Ajouter un scénario revient à y ajouter une entrée.

### Vasicek et les intensités

Le modèle de Vasicek, celui de la formule de Bâle, suppose que tous les emprunteurs dépendent d'un même facteur, l'économie.
Le quantile q dit à quel point cette année est mauvaise : q = 99 % veut dire une année que l'économie ne dépasse en gravité
qu'une fois sur 100. La formule donne alors la PD de cette année-là, à partir de la PD habituelle et de la corrélation ρ.
Plus ρ est grand, plus les défauts arrivent ensemble, et plus la PD de crise monte.

| Intensité | Quantile | Lecture | Origine |
|---|--:|---|---|
| Modérée | 95 % | Une mauvaise année sur 20 | Hypothèse de l'équipe |
| Sévère | 99 % | Une année sur 100 | Hypothèse de l'équipe |
| Extrême | 99,9 % | Une année sur 1 000 | Référence publiée : niveau de confiance de la formule de Bâle (à relire) |

### Paramètres exacts

| Type | Intensité | Quantile q | Défauts en plus Δ | LGD |
|---|---|--:|--:|--:|
| Récession économique | Modérée / Sévère / Extrême | 95 / 99 / 99,9 % | aucun | 45 % |
| Hausse des défauts | Modérée / Sévère / Extrême | aucun | +2 / +5 / +10 points | 45 % |
| Dégradation des actifs | Modérée / Sévère / Extrême | 95 % | aucun | 55 / 65 / 75 % |
| Choc combiné | Modérée / Sévère / Extrême | 95 / 99 / 99,9 % | +1 / +2 / +3 points | 55 / 65 / 75 % |

Origine de chaque valeur :
- **LGD 45 %** : référence publiée, Bâle fondation pour une créance senior non garantie. Valeur reprise de mémoire, à relire.
- **LGD 75 %** : référence publiée, Bâle fondation pour une créance subordonnée, utilisée comme plafond. À relire.
- **LGD 55 % et 65 %** : hypothèses, paliers réguliers entre 45 % et 75 %.
- **Hausses Δ** : hypothèses. +5 points reprend l'exemple chiffré de la consigne.

### Comment chaque levier s'applique

- **Hausse des défauts** : Δ points de prêts sains passent en défaut, pour toutes les banques. PD stressée = PD de départ + Δ.
  Exemple, AlJazira sévère : 1,03 % + 5 points = 6,03 %. Perte = 113,03 × 5 % × 45 % = 2,54 Md. CET1 = (15,07 − 2,54) ÷ 122,69 = 10,21 %.
- **Dégradation des actifs** : LGD = 1 − taux de récupération. Quand la garantie (immobilier, stock, titre) perd de la valeur,
  la banque récupère moins sur chaque prêt en défaut, donc la LGD monte. Les défauts sont ceux d'une récession modérée.
  Exemple, AlJazira modérée : même PD qu'une récession modérée, perte multipliée par 55 ÷ 45, soit 1,41 × 1,222 = 1,72 Md.
- **Choc combiné**, dans cet ordre :
  1. la crise générale donne la PD de crise (Vasicek) ;
  2. les défauts en plus s'ajoutent à cette même PD, plafonnée à 100 % ;
  3. une seule LGD, plus haute, s'applique à tous les nouveaux défauts.

**Pas de double comptage.** Il n'y a qu'une PD et qu'une LGD par banque. Chaque prêt ne peut faire défaut qu'une fois et ne perd qu'une fois.
La perte se ventile exactement en trois canaux, testés automatiquement :

```text
crise     = prêts × (PD de crise − PD de départ) × 45 %
défauts   = prêts × (PD stressée − PD de crise) × 45 %
garanties = prêts × (PD stressée − PD de départ) × (LGD − 45 %)
somme     = prêts × (PD stressée − PD de départ) × LGD        = la perte
```

### Résultats sur les 9 banques (LGD du scénario)

| Scénario | AlJazira : CET1 après | Banques sous 7 % | Banques sous 4,5 % |
|---|--:|--:|--:|
| Récession modérée / sévère / extrême | 11,13 / 9,61 / 6,81 % | 0 / 0 / 2 | 0 / 0 / 0 |
| Hausse des défauts modérée / sévère / extrême | 11,45 / 10,21 / 8,13 % | 0 / 0 / 0 | 0 / 0 / 0 |
| Dégradation des actifs modérée / sévère / extrême | 10,87 / 10,62 / 10,36 % | 0 / 0 / 0 | 0 / 0 / 0 |
| Choc combiné modéré / sévère / extrême | 10,37 / 7,23 / 1,09 % | 0 / 0 / 8 | 0 / 0 / 7 |

Le choc combiné extrême cumule une année sur 1 000 et une LGD de 75 % sur tous les prêts. C'est volontairement un cas limite,
fondé sur des hypothèses : il ne prédit pas la faillite de ces banques.

### Le capital à reconstituer

Chaque résultat affiche le calcul du capital à reconstituer pour revenir au seuil, avec les chiffres de la banque.
Pour une comparaison, un tableau le donne banque par banque, avec le total.

```text
Capital à reconstituer = max(0, seuil × actifs pondérés − capital restant)
AlJazira, choc combiné extrême : capital restant = 15,07 − 13,73 = 1,33 Md
  pour 7 %   : 7 % × 122,69 − 1,33   = 7,25 Md
  pour 4,5 % : 4,5 % × 122,69 − 1,33 = 4,19 Md
```

C'est un calcul mécanique, pas un conseil. Dans le choc combiné extrême, SAIB perd plus que tout son capital CET1 (−0,03 %).

### Pas encore calculables

Hausse des taux et baisse des marchés : il manque les titres et sukuk détenus, leur durée et la marge d'intérêt.
Hausse du chômage : il manque la part des prêts aux particuliers. COVID-19 et crise financière : il manque des taux de défaut
saoudiens historiques. Ils ne sont pas présentés comme des simulations calibrées.

### Exemple à la main : AlJazira, scénario adverse, LGD 45 %

Montants en milliards de SAR, lus aux pages 6 et 25 du rapport.

```text
PD de départ  = 1,165 / 113,030                       = 1,03 %
Corrélation   = 19,17 %   PD stressée (q = 95 %)       = 3,80 %   hausse = 2,77 points
Perte         = 113,030 × 2,77 % × 45 %               = 1,41
CET1 après    = (15,065 − 1,41) / 122,690             = 11,13 %   (avant : 12,28 %)
Pire cas      = (15,065 − 4,5 % × 122,690) / (113,030 × 45 %) = 9,544 / 50,863 = 18,76 points
```

En scénario extrême, la PD passe à 14,23 %, la perte à 6,71 Md, et le CET1 tombe à 6,81 % : sous 7 %, au-dessus de 4,5 %.

### Exemples de contrôle (tests automatiques)

| Cas | Calcul | Résultat |
|---|---|--:|
| Capital 12, RWA 100, prêts 100, hausse 5 points, LGD 45 % | (12 − 2,25) / 100 | 9,75 % |
| Capital 7,2, RWA 60, prêts 60, hausse 3 points, titres 5 en baisse de 25 % | (7,2 − 0,81 − 1,25) / 60 | 8,5667 % |
| Hausse qui casse : capital 7,2, RWA 60, prêts 60 | (7,2 − 2,7) / 27 | 16,6667 points |

Le canal « titres » n'existe que pour le deuxième exemple : il vaut 0 pour les vraies banques, dont les expositions de marché ne sont pas collectées.

## Limites

1. Les banques conventionnelles saoudiennes sont mixtes. À la fin de 2025, 83 % des financements de SNB et 62 % de ceux de Riyad Bank
   étaient conformes à la charia (S&P, repris par https://www.arabnews.pk/node/2651723/business-economy).
2. Le taux de prêts en défaut est un stock : il sert d'approximation de la PD à un an.
3. LGD 45 % et corrélation « entreprises » de Bâle : hypothèses, appliquées à tous les prêts. Référence à relire :
   https://www.bis.org/bcbs/irbriskweight.pdf (formules reprises de mémoire, **NON VÉRIFIÉ** dans le document).
4. Même formule pour toutes les banques : les mécanismes propres à la finance islamique ne sont pas appliqués aux vraies banques.
   L'ancien modèle (mourabaha, salam, istisna, comptes d'investissement) reste dans « Avancé », sur 12 banques inventées et étiquetées.
5. Actifs pondérés constants, un an, pas de second tour. Ni les provisions existantes ni les bénéfices futurs ne compensent la perte.
6. Le périmètre de la ligne « Loans » du tableau CR1 peut varier d'une banque à l'autre.
7. 7 % n'inclut pas les coussins propres à chaque banque. Ce n'est pas un test réglementaire.
8. 4 banques contre 5 : aucune conclusion du type « un modèle bancaire est meilleur ».
9. Pas d'apprentissage automatique sur 9 banques. L'explication est la décomposition exacte : capital de départ − perte = capital restant.

## Fichiers

| Fichier | Rôle |
|---|---|
| `backend/pipeline/banques.py` | Collecte vérifiable (robots.txt, PDF, empreinte, chiffres retrouvés) |
| `backend/app/stress/donnees_reelles.py` | Lecture contrôlée du CSV |
| `backend/app/stress/credit.py` | Vasicek, perte, CET1, pire cas, comparaison, matrice |
| `backend/app/stress/routes.py` | `GET /reelles/banques` (nom, type, source : pas de chiffres bruts), `POST /reelles/comparer` (`{scenario, lgd, banques}` : une banque ou plusieurs), `GET /reelles/matrice` ; anciennes routes gardées |
| `backend/tests/test_banques.py` | Contrôles du CSV, exemples, valeurs de référence, routes, robots.txt |
| `frontend/src/components/PageStress.tsx`, `components/stress/**`, `app/stress/stress.css` | Écran de simulation seulement : 1. une banque ou une comparaison, 2. le type de crise, l'intensité et la LGD avancée, 3. « Lancer la simulation ». Résultat : le calcul, le capital à reconstituer et le pire cas, ou la comparaison et le tableau du capital à reconstituer, puis les paramètres appliqués. Hypothèses, limites et collecte restent dans le backend et dans ce document |

## Demandes au poste A

1. **Assistant XAI : fait sur la branche `feature/xai-plus`.** L'assistant parle maintenant des vraies banques
   (`app/xai/couverture.py::stress_banques`). `app.stress.credit.synthese_xai` reste disponible. L'ancien contrat
   (`stress.modele` : `GROUPES`, `valider_chocs`, `stresser`, `panel_synthetique`) est inchangé.
2. Aucun fichier commun n'a été modifié. La feuille `app/stress/stress.css` est importée par la page elle-même.
3. **Fusion avec `main` du 23/11/2026** : la réponse « assurance » du poste A, qui chiffre la vraie protection du portefeuille
   (`protection.devis`), est gardée telle quelle. `app/analyse/lecture.py` n'est pas encore appelé par l'assistant : le ton de la
   presse passe par `scenarios/sentiment.analyser`. Le brancher demande une fonction dans `couverture.py`.

## Trois questions probables du jury

**Pourquoi la PD et pas le Z-score ?**
Le Z-score demande une série longue de rentabilité : sur 4 ans, il est instable. Celui d'Altman est fait pour les entreprises, pas pour
les banques. La PD répond directement à la question posée : combien de prêts font défaut. Elle se lit dans le tableau CR1 et Bâle
fournit la formule pour la stresser.

**D'où vient ce chiffre ?**
Chaque chiffre a son URL, sa page et sa date de collecte. Par exemple, AlJazira : capital CET1 15,07 Md et actifs pondérés 122,69 Md,
page 6 (tableau KM1) ; prêts en défaut 1,16 Md et prêts sains 111,86 Md, page 25 (tableau CR1). La commande `python -m pipeline.banques`
retélécharge le PDF et retrouve chaque chiffre à sa page devant vous.

**Pourquoi est-ce le pire cas ?**
Ce n'est pas un scénario choisi, c'est le calcul à l'envers : quelle hausse des défauts amène le CET1 exactement à 4,5 % ?
Pour AlJazira : (15,07 − 4,5 % × 122,69) ÷ (113,03 × 45 %) = 18,8 points. Même le scénario extrême, une année sur 1 000,
ne fait monter ses défauts que de 13,2 points. AlJazira est la plus fragile du panel, SNB la plus solide (33,2 points).
