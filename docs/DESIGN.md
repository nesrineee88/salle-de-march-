# Direction visuelle

## Le sujet
Un simulateur de salle de marché pour des étudiants et des professionnels. Sa particularité : le **temps se rejoue**.
C'est donc l'horloge et la frise de six ans qui portent l'identité de l'écran, pas un tableau de bord de plus.

## Choix
- **Palette « Nuit de Sidi »** : bleu-nuit `#0B1620`, surfaces `#0F1D2A` et `#162838`, filets `#213446`, texte `#E6EEF5`, discret `#8FA6B8`.
- **Gain = bleu clair `#5BAEFF`, perte = orange `#FF9255`** : lisible par les daltoniens, différent des habituels vert et rouge. La couleur n'est jamais seule : signe + ou −, flèches ▲ ▼.
- **Jasmin `#F0D58A`** réservé au temps : heure, curseur de la frise, repères, focus clavier. Rien d'autre n'est jaune.
- **Typographie** : Bricolage Grotesque (titres, heure, grands chiffres) et IBM Plex Sans (interface, chiffres tabulaires).
- **Structure** : une coque fixe (menu de pages, puis barre du temps avec horloge, vitesse et frise) et, dessous, une page par sujet. Les chiffres sont regroupés dans des panneaux à filet fin de 8 px de rayon, sans ombre. La page d'un marché garde l'écran de trading en trois colonnes (liste, graphique, ordre et carnet).
- **Texte** : phrases en minuscules, verbes précis (« Acheter AAPL », « Annuler »), erreurs qui disent quoi faire.
- **Mouvement** : aucun effet décoratif. L'horloge avance en continu, c'est le seul mouvement.

## Pages
- **Tableau de bord** : étapes de démarrage, valeur du portefeuille (un seul grand chiffre), courbe, indices, plus fortes hausses et baisses de chaque marché, plus grosses positions, machine à remonter le temps.
- **Actions, Cryptomonnaies, Matières premières** : un écran de trading par marché, le même portefeuille derrière.
- **Portefeuille** : chiffres clés, courbe contre le S&P 500, profil de risque comparé au risque réel, huit indicateurs de risque (chacun expliqué en une phrase en mode Apprenant), répartition, corrélations, positions, trades clôturés, ordres et exécutions.
- **Compte** : questionnaire de profil de risque, appareils connectés, mot de passe, export et remise à zéro.
- **Administration** : visible des seuls administrateurs.

## Graphiques (méthode « dataviz »)
- La courbe du portefeuille est en blanc, le S&P 500 en gris : une série mise en avant, l'autre en contexte. Trait de 2 px, légende toujours présente, point final de 8 px cerné de la couleur du fond.
- Au survol (ou avec les flèches du clavier) : repère vertical et une bulle avec les deux valeurs et les rendements ; un tableau des 60 derniers jours est disponible sous la courbe.
- Les répartitions sont des barres horizontales classées, d'une seule teinte, avec la valeur écrite au bout ; les liquidités sont en gris.
- Les corrélations sont une carte de chaleur à deux teintes autour d'un neutre (bleu : ensemble, orange : sens opposés), la valeur est écrite dans chaque case.
- Les états du profil de risque sont doublés d'une icône et d'un texte : ✓ dans la tolérance, ! proche de la limite, ✕ au-delà.

## Thèmes sombre et clair
Le bouton « Clair » / « Sombre » est en haut à droite (et sur la page de connexion). Le choix est mémorisé dans le navigateur. Les mêmes rôles de couleur sont définis deux fois ; le graphique des bougies, la courbe de valeur et la carte des corrélations suivent le thème sans recharger la page.

| Rôle | Sombre | Clair |
|---|---|---|
| Fond / panneau | `#0B1620` / `#0F1D2A` | `#F3F6F9` / `#FFFFFF` |
| Texte / discret | `#E6EEF5` / `#8FA6B8` | `#0F2233` / `#53677A` |
| Gain / perte | `#5BAEFF` / `#FF9255` | `#0F6FD0` / `#C24A14` |
| Temps (horloge, frise, focus) | `#F0D58A` | `#9A6A00` |

## Indicateurs techniques
Cases à cocher au-dessus du graphique : moyennes mobiles (SMA 20 et 50), EMA 20, bandes de Bollinger, RSI (volet du bas, repères 30 et 70), MACD (volet avec histogramme). L'ATR 14 s'affiche dans l'en-tête. Les volets se redimensionnent à la souris. Les choix sont mémorisés. En mode Apprenant, un texte repliable explique chaque indicateur en mots simples et rappelle qu'ils décrivent le passé.

## Protection automatique et alertes de risque
Sous le ticket d'ordre, le panneau « Protection automatique » propose les quatre règles pour l'actif choisi (un champ de pourcentage chacun, un bouton « Activer » ou « Remplacer », le prix de déclenchement affiché, « Retirer »). Dans le ticket, des alertes de risque apparaissent avant un achat : une icône « ! » pour une attention, « i » pour une information, toujours avec un texte (la couleur n'est pas seule). Les ordres placés par une règle portent la pastille « auto ». La page Portefeuille liste toutes les règles (onglet « Règles automatiques »).

## Ce qui a été écarté
Un fond noir avec un vert acide, des cartes arrondies identiques, des majuscules espacées au-dessus de chaque titre, un dégradé en décor.

## Modes
- **Apprenant** : chaque type d'ordre et le carnet sont expliqués en une phrase, dans le contexte.
- **Trader** : mêmes données, sans les explications.

## À faire
Anglais et arabe (écriture de droite à gauche), version téléphone dédiée, animation de la bougie en formation, intervalles hebdomadaire et mensuel, colonnes cours acheteur et vendeur dans la liste des actifs (à la MetaTrader).
