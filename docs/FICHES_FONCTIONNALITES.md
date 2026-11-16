# Fiches des fonctionnalités

Une section par fonctionnalité : le concept en mots simples, les formules, où se trouve le code, comment la démontrer,
et trois questions d'examinateur avec leurs réponses.

---

## P1 — Tableau de bord : vue simple, vue professionnelle, niveau de risque et alertes (cahier, section 16)

**Branche :** `feature/tableau-de-bord`

### Le concept en mots simples

Le tableau de bord doit permettre à une personne sans formation financière de comprendre sa situation en quelques
secondes. Il répond à quatre questions : combien vaut mon portefeuille ? est-il risqué ? une de mes protections
(stop-loss, prise de profit) est-elle sur le point de se déclencher ? que s'est-il passé récemment ?

Deux vues, sur un même bouton en haut de la page :
- **Vue simple** (mode Apprenant) : phrases courtes au conditionnel, sans jargon, avec une aide sous chaque bloc.
- **Vue professionnelle** (mode Trader) : valeurs chiffrées, seuils, VaR et CVaR en USD, plus les marchés du jour et
  le tableau des plus grosses positions.

### Les formules

Le **niveau de risque global** retient le **pire** de cinq critères, chacun classé 0 (faible), 1 (modéré) ou 2 (élevé).
On prend le pire plutôt qu'une moyenne : un portefeuille à 90 % dans la technologie reste dangereux même si sa VaR passée
est faible (exemple du cahier des charges). Bornes incluses dans le niveau inférieur.

| Critère | Mesure | Faible | Modéré | Élevé |
|---|---|---|---|---|
| VaR | VaR historique 95 % à 1 jour, en fraction de la valeur totale | ≤ 1 % | ≤ 2,5 % | > 2,5 % |
| Position | part de la plus grosse position dans la valeur totale | ≤ 25 % | ≤ 50 % | > 50 % |
| Secteur | part du plus gros secteur dans la valeur totale | ≤ 40 % | ≤ 60 % | > 60 % |
| Profil | baisse actuelle comparée à la perte tolérée du questionnaire | ok | proche (> 75 %) | dépassée |
| Baisse | baisse depuis le plus haut de la courbe de valeur (drawdown courant) | ≤ 10 % | ≤ 20 % | > 20 % |

Les parts sont mesurées sur la valeur **totale** (liquidités comprises) : une petite ligne dans un portefeuille
surtout en liquidités n'est pas un risque de concentration. Seuils pédagogiques, non réglementaires.

**Distance d'une règle à son déclenchement :** distance = |seuil − prix actuel| / |prix actuel| (sans unité, affichée en %).
Une règle est « proche » si la distance est ≤ 5 %. Exemple : stop-loss à 196 USD, prix 200 USD → |196 − 200| / 200 = 2 %.

### Où c'est dans le code

- `backend/app/risque/synthese.py` : `niveau_risque(analyse)` et `alertes_regles(regles, prix)`, fonctions pures.
- `backend/app/routes_portefeuille.py` : `GET /api/v1/tableau-de-bord` (calcul côté serveur, relu toutes les 6 s) ;
  `_analyser_bac` factorise le calcul partagé avec `GET /portefeuille/analyse`.
- `backend/tests/test_synthese.py` : 10 tests (exemples chiffrés, bornes, portefeuille vide, prix nul, API).
- `frontend/src/components/SyntheseTableau.tsx` : `PanneauRisque`, `PanneauAlertes`, `ActualitesImportantes`, `ActiviteRecente`.
- `frontend/src/components/TableauDeBord.tsx` : choix de la vue et disposition.

### Démonstration

1. Se connecter, ouvrir le **Tableau de bord**. Compte neuf : niveau « aucune position », répartition 100 % liquidités,
   alertes vides avec une phrase d'aide.
2. Ouvrir **Actions**, acheter une grosse quantité d'une seule action technologique (par exemple 400 NVDA).
3. Revenir au tableau de bord : le niveau passe à « Élevé » ou « Modéré » et le critère du secteur Technologie apparaît en tête.
4. Page **Portefeuille** : poser un stop-loss à 3 % sur cette position. Au tableau de bord, l'alerte affiche
   « Proche du seuil : 3,0 % » avec une barre presque pleine.
5. Basculer « Vue professionnelle » : les phrases deviennent chiffrées (seuils, VaR en USD) et les marchés du jour apparaissent.
6. Lancer le temps : si le stop-loss se déclenche, il apparaît dans « Dernières règles déclenchées » et dans « Activité récente ».

### Questions d'examinateur

1. **Pourquoi prendre le pire critère et pas une moyenne pondérée ?**
   Parce qu'un risque grave ne se compense pas : une VaR faible ne protège pas d'une crise sectorielle si 90 % du
   portefeuille est dans ce secteur. La règle « pire critère » est aussi plus facile à expliquer à un débutant.
2. **La VaR affichée est-elle fiable ?**
   C'est une VaR historique (aucune loi supposée) sur au plus 260 séances passées, calculée sur les poids ACTUELS ;
   elle suppose que le passé récent ressemble à l'avenir et ne dit rien de la perte au-delà du quantile (d'où la CVaR).
   Sans 30 jours d'historique commun, le critère est omis plutôt qu'inventé.
3. **Le tableau de bord recalcule-t-il tout à chaque tick ?**
   Non : la synthèse est calculée côté serveur et relue toutes les 6 secondes ; les prix, eux, sont relus toutes les 1,5 s.

---

## P2 — Mesures de risque : écart-type, bêta, covariance, et une fiche par indicateur (cahier, section 5)

**Branche :** `feature/risque-indicateurs`

### Le concept en mots simples

Un portefeuille peut gagner et pourtant être dangereux. Les mesures de risque répondent à « combien puis-je perdre, et
pourquoi ? ». Chaque indicateur a maintenant sa fiche sur la page Portefeuille : sa formule, ce qu'il veut dire, comment
il est calculé ici, un graphique, et une phrase simple en mode Apprenant. Le RSI a aussi sa fiche, mais marquée
« indicateur technique » : il mesure l'élan d'un prix, pas l'ampleur d'une perte possible.

### Les formules (rendements de séance r, sans unité ; 0,01 = 1 %)

- Écart-type d'échantillon : σ = √( Σ (rᵢ − r̄)² / (n − 1) ) ; volatilité annuelle = σ × √252 (252 séances par an).
  Exemple : r = (1 %, −1 %, 3 %, −3 %) → σ = √(2·10⁻³ / 3) = 2,582 %.
- Bêta : β = Cov(r_p, r_m) / Var(r_m) ; alpha α = r̄_p − β r̄_m ; corrélation ρ = Cov / (σ_p σ_m).
  Exemple : r_m = (1, −1, 2, −2) %, r_p = (2, 0, 1, −3) % → Cov = Var(r_m) = 3,333·10⁻⁴ donc β = 1 ; ρ = 0,845.
- Covariance : Cov(X, Y) = Σ (xᵢ − x̄)(yᵢ − ȳ) / (n − 1), affichée en 10⁻⁴.
- VaR 95 % historique = − quantile à 5 % ; CVaR = moyenne des pertes ≥ VaR ; HHI = Σ wᵢ² (déjà présents, désormais documentés).

### Où c'est dans le code

- `backend/app/risque/indicateurs.py` : `ecart_type`, `beta`, `histogramme`.
- `backend/app/risque/analyse.py` : `_beta_portefeuille`, clés `beta`, `covariances`, `risque.distribution`.
- `backend/app/routes_portefeuille.py` : clôtures passées de `^GSPC` passées à `analyser` (barres terminées : pas de look-ahead).
- `backend/tests/test_risque_beta.py` : 8 tests (exemples à la main, variance nulle, historique court, séries non alignées).
- `frontend/src/components/FichesRisque.tsx` : fiches, histogramme (VaR, CVaR, ±σ), nuage du bêta, table de covariance.

### Démonstration

1. Acheter au moins deux actifs, puis avancer d'au moins deux mois simulés (ou utiliser la machine à remonter le temps).
2. Page **Portefeuille**, bloc « Comprendre chaque indicateur ».
3. Cliquer « VaR » : histogramme des rendements, barres de la queue en couleur de perte, lignes VaR (tirets) et CVaR.
4. Cliquer « Bêta » : nuage de points portefeuille / S&P 500 et droite de pente β ; survoler un point.
5. Cliquer « RSI (technique) » : badge « pas une mesure de risque ».
6. Basculer en mode Apprenant : la rubrique « En clair » apparaît.

### Limites connues

- Données de démonstration : chaque série synthétique est tirée indépendamment, donc bêtas et corrélations sont proches
  de 0. Avec les vraies données Yahoo Finance, le bêta d'un portefeuille d'actions américaines serait proche de 1.
- Le bêta et la VaR sont calculés sur les poids ACTUELS appliqués au passé (portefeuille « tel qu'il est aujourd'hui »).

### Questions d'examinateur

1. **Pourquoi √252 ici et 365 pour la volatilité de la courbe de valeur ?** Les rendements des actifs sont alignés sur
   les séances où tous cotent (environ 252 par an) ; la courbe de valeur, elle, avance en temps calendaire irrégulier,
   d'où une normalisation par la durée réelle et 365 jours.
2. **Un bêta de 0,3 veut-il dire que le portefeuille est peu risqué ?** Non : le bêta ne mesure que le risque lié au
   marché. Un portefeuille d'une seule crypto peut avoir un bêta faible et une volatilité énorme (risque spécifique).
3. **Y a-t-il un biais d'anticipation ?** Non : seules les barres strictement antérieures au jour simulé sont lues
   (`barres_terminees`), pour les actifs comme pour l'indice.

---

## P3 — CRUD des positions et historique des clôtures (cahier, section 3)

**Branche :** `feature/positions-historique`

### Le concept en mots simples

Une position naît au premier achat et meurt quand on a tout revendu. Le cahier exige qu'une position clôturée ne
disparaisse pas : l'historique la garde avec son résultat et la raison de sa clôture (vente manuelle, stop-loss,
prise de profit…). Il est reconstruit à partir des exécutions déjà enregistrées : aucune nouvelle table.

CRUD : ajouter = acheter ; consulter = onglet Positions ; modifier les paramètres = règles stop-loss / prise de profit
et clôture partielle (« Vendre la moitié ») ; supprimer = « Clôturer » ; historique = onglet « Historique des positions ».

### Les formules (USD)

- prix d'achat moyen = Σ qᵢ pᵢ (achats) / Σ qᵢ ; prix de vente moyen idem sur les ventes ;
- réalisé = Σ (prix de vente − prix de revient moyen) × quantité vendue ;
- résultat net = réalisé − frais du cycle ; rendement net = résultat net / coût des achats.
- Exemple (test) : achats 10 × 100 et 10 × 110 (revient 105), ventes 5 × 120 et 15 × 90 →
  réalisé 75 − 225 = −150 ; frais 2,025 ; net −152,025 ; rendement −152,025 / 2 100 = −7,24 %.

### Où c'est dans le code

- `backend/app/trading/historique.py` : `historique_positions(executions, origines, types_regles)`.
- `backend/app/routes_portefeuille.py` : `GET /api/v1/portefeuille/positions/historique`.
- `backend/tests/test_historique_positions.py` : 5 tests.
- `frontend/src/components/HistoriquePositions.tsx` ; `PagePortefeuille.tsx` (onglet, clôture partielle).

### Démonstration

1. Acheter 10 actions, page Portefeuille, cliquer « Vendre la moitié » : la position reste ouverte avec 5 actions.
2. Cliquer « Clôturer » : la position disparaît de l'onglet Positions…
3. … et apparaît dans « Historique des positions » (filtre « Clôturées »), motif « Vente manuelle ».
4. Poser une prise de profit, avancer le temps : la clôture affiche le motif « Prise de profit ».

### Questions d'examinateur

1. **Pourquoi ne pas stocker les positions clôturées dans une table ?** Les exécutions sont déjà enregistrées et
   jamais modifiées : reconstruire évite deux sources de vérité qui pourraient diverger.
2. **Le résultat net d'une position ouverte est-il son vrai résultat ?** Non : il ne compte que la partie vendue
   moins les frais ; le gain latent est affiché dans l'onglet Positions.
3. **Que se passe-t-il si on rachète après une clôture ?** Un nouveau cycle s'ouvre ; l'ancien reste clôturé.

---

## P4 — Analyse technique : unités de temps, volumes, supports et résistances, Fibonacci (cahier, section 7)

**Branche :** `feature/analyse-technique`

### Le concept en mots simples

Le graphique en chandeliers se lit maintenant en 1 min, 5 min, 15 min, 1 h ou 1 jour, avec les heures et minutes sur
l'axe (heures UTC, comme l'horloge du simulateur). Les données d'origine sont journalières : le moteur fabrique 96 ticks
simulés par séance qui respectent la bougie du jour, et le prix entre deux ticks est interpolé. Les bougies en minutes
sont lues sur cette même fonction de prix, celle qui sert à exécuter les ordres : elles sont cohérentes avec la
simulation, mais ce ne sont pas des cotations réelles (c'est écrit sous le graphique).

Repères automatiques : volumes (unité 1 jour), supports et résistances, cassures possibles avec le mouvement qui a suivi,
lignes de tendance, retracements de Fibonacci. Tracé manuel : ligne horizontale (un clic) ou ligne de tendance (deux clics).

### Les formules

- Bougie [a, b] : ouverture = P(a), clôture = P(b), plus haut / plus bas = extrêmes de P(a), P(b) et des ticks dans ]a, b[.
  Exemple (test) : ticks 100 (14:30), 110 (14:35), 90 (14:40) → bougie 5 min de 14:35 : O 110, H 110, B 90, C 90 ;
  bougie 1 min de 14:37 : de 102 à 98 (pente −4 par minute).
- Sommet confirmé en i : plus haut de la fenêtre [i − 3, i + 3], connu seulement à i + 3 (pas de look-ahead).
- Zone : sommets et creux à moins d'une demi-amplitude moyenne de bougie, au moins 2 contacts ; support si sous la
  dernière clôture, résistance sinon. Cassure : clôture qui traverse la zone après sa confirmation.
- Fibonacci : mouvement haussier → niveau(r) = haut − r × (haut − bas) ; r ∈ {23,6 ; 38,2 ; 50 ; 61,8 ; 78,6 %}.
  Exemple : de 100 à 200, 61,8 % → 138,2.

### Où c'est dans le code

- `backend/app/analyse/bougies.py` : `bougies_seance`, `bougies_intraday`.
- `backend/app/analyse/niveaux.py` : `pivots`, `supports_resistances`, `cassures`, `lignes_tendance`, `fibonacci`.
- `backend/app/analyse/routes.py` : `GET /api/v1/bougies/{symbole}?unite=1min|5min|15min|1h|1j&barres=300`.
- `backend/app/marche/moteur.py` : `chemin_seance` (lecture seule du chemin de ticks).
- `backend/tests/test_bougies.py` (7 tests), `backend/tests/test_niveaux.py` (5 tests).
- `frontend/src/components/Graphique.tsx`, `OutilsTechniques.tsx`, `PageMarche.tsx`, `lib/technique.ts`.

### Démonstration

1. Page **Actions**, choisir AAPL, lancer le temps pendant une séance (14:30-21:00 UTC).
2. Unité « 5 min » : l'axe affiche les heures ; la dernière bougie bouge avec l'horloge.
3. Cocher « Supports et résistances » : lignes pointillées titrées avec le nombre de contacts, flèches « Cassure possible »,
   et sous le graphique la phrase « Depuis, n bougies : +x % ».
4. Cocher « Fibonacci », puis « Lignes de tendance ». Passer en unité « 1 jour » et cocher « Volumes ».
5. « Tracer » → « Support / résistance », cliquer sur le graphique ; « Ligne de tendance », cliquer deux bougies.
   Changer d'actif puis revenir : les tracés sont toujours là.

### Questions d'examinateur

1. **Vos bougies d'une minute sont-elles réelles ?** Non, et c'est affiché : elles viennent des ticks simulés à partir de
   la bougie journalière réelle. Elles sont cohérentes avec les prix d'exécution du simulateur.
2. **Comment évitez-vous le look-ahead dans la détection des supports ?** Un sommet n'est retenu que lorsque les 3
   bougies suivantes sont connues ; les bougies s'arrêtent à l'instant simulé.
3. **Une cassure veut-elle dire qu'il faut acheter ?** Non : c'est un signal possible, souvent démenti (fausse cassure) ;
   l'interface montre ce que le cours a fait ensuite pour en juger.

---

## Cartes de synthèse du portefeuille (cahier, sections 3 et 16)

**Branche :** `feature/portefeuille-cartes` (depuis `integration/demo`)

### Le concept en mots simples

Sept cartes résument le portefeuille : valeur totale (avec une mini-courbe), valeur des positions, liquidités,
performance, gains et pertes réalisés, latents, frais payés. Chaque montant porte son unité (USD), un signe + ou −,
une couleur ET une flèche (la couleur n'est jamais la seule information). Un bouton (i), utilisable au clavier, explique
Performance, Réalisé, Latent et Frais : une phrase simple en mode Apprenant, la formule en mode Trader.

### Les formules (USD)

- Valeur des positions = valeur du portefeuille − liquidités.
- Résultat total = valeur du portefeuille − capital de départ = Réalisé + Latent − Frais (identité vérifiée par un test).
- Performance = Résultat total / Capital de départ.
- Réalisé = Σ (prix de vente − prix de revient moyen) × quantité vendue ; Latent = Σ (prix actuel − prix de revient moyen) × quantité.
- Pourquoi l'identité tient : le coût restant des positions est Σ achats − Σ (prix de revient × quantités vendues) ;
  en l'ajoutant au cash (capital − achats + ventes − frais) et au latent, on retrouve capital + réalisé + latent − frais.

### Où c'est dans le code

- `frontend/src/components/PagePortefeuille.tsx` : rangée de cartes, `MiniCourbe`.
- `frontend/src/components/Indicateur.tsx` : props `unite`, `infobulle`, `children` (facultatives, les autres pages ne changent pas).
- `frontend/src/app/globals.css` : section « cartes de synthèse du portefeuille » (grille en requêtes de conteneur,
  taille fluide `clamp(…, 10cqi, …)`, chiffres tabulaires, fond translucide flouté).
- `backend/tests/test_identite_resultat.py` : identité vérifiée après achat, vente partielle, rachat et passage du temps.

### Démonstration

1. Page **Portefeuille** : 7 cartes en 4 colonnes sur grand écran, 2 sur tablette, 1 sur mobile, sans carte isolée.
2. Survoler ou atteindre au clavier (Tab) le bouton (i) de « Performance » : phrase simple en mode Apprenant ; basculer
   en mode Trader : la formule apparaît.
3. Après quelques achats et ventes : vérifier à la main que Réalisé + Latent − Frais = Résultat total (sous Performance).
4. Réduire la fenêtre : le montant de la grande carte rétrécit au lieu d'être coupé.

### Questions d'examinateur

1. **Le réalisé inclut-il les frais ?** Non : il est hors frais, d'où la carte « Frais payés » et la ligne
   « dont frais » sous la performance ; le résultat total, lui, les inclut.
2. **Pourquoi une grille à 1, 2 ou 4 colonnes et pas un simple auto-fit ?** Avec 7 cartes dont une double (8 cases),
   un auto-fit libre peut produire 3, 5 ou 6 colonnes et laisser une carte seule sur sa ligne ; 1, 2 ou 4 colonnes
   divisent toujours 8.
3. **Comment garantissez-vous le contraste sur le fond animé ?** Le fond des cartes reste opaque à 84 % avec un flou
   d'arrière-plan ; les couleurs de texte sont les jetons du thème, au-dessus du ratio AA (4,5:1) dans les deux thèmes.
