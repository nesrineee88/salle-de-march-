"""Contenu pédagogique : leçons courtes, questions à choix, exercices pratiques dans le simulateur.
Les bonnes réponses ne quittent jamais le serveur avant que l'apprenant ait répondu."""
from __future__ import annotations

SEUIL_REUSSITE = 0.7

LECONS: list[dict] = [
    {"id": "ordres", "titre": "Passer ses premiers ordres", "niveau": "Débutant", "minutes": 8,
     "resume": "Ordre au marché, ordre à cours limité, ordre stop, écart acheteur-vendeur.",
     "sections": [
         {"titre": "Trois types d'ordres", "texte": "Un ordre au marché s'exécute tout de suite au meilleur prix disponible : vous êtes sûr d'être exécuté, pas du prix. Un ordre à cours limité fixe le prix maximum d'achat (ou minimum de vente) : vous maîtrisez le prix, pas l'exécution. Un ordre stop reste dormant jusqu'à ce que le prix atteigne un seuil, puis se transforme en ordre au marché."},
         {"titre": "L'écart acheteur-vendeur", "texte": "Il existe toujours deux prix : celui auquel on achète (vendeur, plus haut) et celui auquel on vend (acheteur, plus bas). L'écart est un coût caché payé à chaque aller-retour, plus important sur les actifs peu échangés. Les frais de courtage s'y ajoutent."},
     ],
     "questions": [
         {"enonce": "Vous voulez acheter sans jamais payer plus de 50 $. Quel ordre ?", "choix": ["Au marché", "À cours limité à 50 $", "Stop à 50 $", "Aucun, c'est impossible"], "bonne": 1, "explication": "Le cours limité plafonne le prix d'achat ; en contrepartie, l'ordre peut ne jamais être exécuté."},
         {"enonce": "Un ordre stop de vente à 90 $ sur une action cotée 100 $ :", "choix": ["Vend immédiatement à 100 $", "Se déclenche si le prix descend à 90 $", "Se déclenche si le prix monte à 90 $", "Garantit de vendre exactement à 90 $"], "bonne": 1, "explication": "Il dort jusqu'à 90 $ puis devient un ordre au marché : en cas de trou de cotation (gap), l'exécution peut se faire sous 90 $."},
         {"enonce": "L'écart acheteur-vendeur est :", "choix": ["Un impôt", "Un coût implicite payé à l'achat et à la vente", "Un gain pour l'investisseur", "Toujours nul sur les actions"], "bonne": 1, "explication": "On achète au prix vendeur, on revend au prix acheteur : la différence est perdue à chaque aller-retour."},
     ],
     "exercices": [{"texte": "Achetez 10 actions d'un titre de votre choix, puis posez un stop-loss à −10 %.", "lien": "/actions", "libelle": "Ouvrir les actions"}]},
    {"id": "risque", "titre": "Gérer le risque", "niveau": "Débutant", "minutes": 10,
     "resume": "Taille de position, stop-loss, diversification, profil de risque.",
     "sections": [
         {"titre": "Perdre peu pour durer", "texte": "Une perte de 50 % exige un gain de 100 % pour revenir à zéro : les grosses pertes sont asymétriques. Limiter la taille de chaque position et fixer à l'avance une sortie (stop-loss) protège le capital."},
         {"titre": "Diversifier", "texte": "Des actifs qui ne montent pas et ne descendent pas ensemble réduisent le risque du portefeuille sans réduire proportionnellement le rendement attendu. La diversification n'élimine pas le risque de marché : dans une grande crise, beaucoup de corrélations montent vers 1."},
         {"titre": "Mesurer", "texte": "La volatilité mesure l'agitation, le drawdown la pire baisse depuis un sommet, la VaR la perte qu'on ne dépasse pas sur un jour avec un certain niveau de confiance (95 % ici), historiquement. Ce sont des estimations du passé, pas des garanties."},
     ],
     "questions": [
         {"enonce": "Après une perte de 50 %, quel gain faut-il pour revenir au point de départ ?", "choix": ["50 %", "75 %", "100 %", "150 %"], "bonne": 2, "explication": "Il reste 50 : pour retrouver 100, il faut le doubler, soit +100 %."},
         {"enonce": "La VaR à 95 % sur un jour de 3 % signifie :", "choix": ["On perdra 3 % chaque jour", "Sur 20 jours, environ 1 jour devrait dépasser 3 % de perte (selon le passé)", "La perte maximale possible est de 3 %", "Le portefeuille gagne 95 % du temps"], "bonne": 1, "explication": "C'est un seuil statistique : 5 % des jours dépassent la VaR, et rien ne borne la perte au-delà."},
         {"enonce": "Détenir dix actions technologiques américaines est-il bien diversifié ?", "choix": ["Oui, dix valeurs suffisent", "Non, elles réagissent aux mêmes facteurs", "Oui, si elles ont des noms différents", "Cela dépend de leur prix"], "bonne": 1, "explication": "Le nombre de lignes compte moins que leurs différences de secteur, de zone et de classe d'actifs."},
     ],
     "exercices": [{"texte": "Répondez au questionnaire de risque, puis regardez si votre portefeuille reste dans votre tolérance.", "lien": "/compte", "libelle": "Définir mon profil"}]},
    {"id": "graphiques", "titre": "Lire un graphique et ses indicateurs", "niveau": "Intermédiaire", "minutes": 10,
     "resume": "Bougies, moyennes mobiles, RSI, MACD, bandes de Bollinger.",
     "sections": [
         {"titre": "La bougie", "texte": "Une bougie résume une période : ouverture, plus haut, plus bas, clôture. Son corps relie ouverture et clôture, ses mèches montrent les extrêmes atteints."},
         {"titre": "Les indicateurs", "texte": "Une moyenne mobile lisse les prix : un prix au-dessus d'une moyenne longue suggère une tendance haussière. Le RSI (0 à 100) mesure la vigueur des hausses récentes ; au-dessus de 70 on parle de « suracheté », sous 30 de « survendu », sans que cela annonce un retournement. Le MACD compare deux moyennes pour repérer l'accélération d'une tendance. Les bandes de Bollinger entourent le prix de deux écarts-types : elles s'élargissent quand la volatilité monte."},
         {"titre": "Leur limite", "texte": "Les indicateurs sont calculés sur le passé et réagissent avec retard. Un RSI « survendu » peut le rester longtemps dans une forte baisse."},
     ],
     "questions": [
         {"enonce": "Un RSI à 80 signifie que :", "choix": ["Le prix va forcément baisser", "Les hausses récentes ont été très fortes", "L'action est chère pour toujours", "Le volume est élevé"], "bonne": 1, "explication": "Le RSI décrit la vigueur récente des hausses ; il n'annonce pas ce qui suit."},
         {"enonce": "Une moyenne mobile longue réagit :", "choix": ["Plus vite qu'une courte", "Plus lentement qu'une courte", "Exactement comme une courte", "Seulement aux gros volumes"], "bonne": 1, "explication": "Plus la fenêtre est longue, plus la moyenne est lisse et en retard."},
         {"enonce": "Des bandes de Bollinger qui s'écartent indiquent :", "choix": ["Une volatilité qui augmente", "Un prix qui va monter", "Un volume qui baisse", "Une erreur de données"], "bonne": 0, "explication": "Les bandes sont fondées sur l'écart-type des prix récents : plus il est grand, plus elles sont larges."},
     ],
     "exercices": [{"texte": "Affichez les moyennes mobiles, le RSI et le MACD sur un titre et notez où ils se contredisent.", "lien": "/actions", "libelle": "Ouvrir un graphique"}]},
    {"id": "backtest", "titre": "Tester une idée sans se tromper", "niveau": "Intermédiaire", "minutes": 10,
     "resume": "Backtesting, coûts, surajustement, test hors échantillon.",
     "sections": [
         {"titre": "Rejouer le passé", "texte": "Un backtest applique une règle à l'historique. Pour être honnête, le signal du jour ne doit utiliser que des informations déjà connues, l'ordre s'exécute au jour suivant, et les coûts de transaction sont comptés."},
         {"titre": "Le piège du surajustement", "texte": "Si vous testez beaucoup de réglages, l'un d'eux gagnera par hasard. Un bon résultat sur une période n'a de valeur que s'il se répète sur une autre : comparez les deux moitiés de l'historique et gardez la règle la plus simple."},
     ],
     "questions": [
         {"enonce": "Pourquoi exécuter l'ordre le lendemain du signal ?", "choix": ["Pour économiser des frais", "Parce que le signal utilise la clôture, qu'on ne connaît qu'une fois la séance finie", "Parce que la bourse est fermée le week-end", "Ce n'est pas nécessaire"], "bonne": 1, "explication": "Acheter à la clôture qui a produit le signal supposerait de connaître cette clôture à l'avance."},
         {"enonce": "Sur 50 stratégies testées, la meilleure a battu le marché. Que faire ?", "choix": ["La déployer aussitôt", "Se méfier : sur 50 essais, une peut gagner par chance", "Tester 50 de plus", "Ignorer les coûts"], "bonne": 1, "explication": "C'est le risque de comparaison multiple : il faut confirmer hors de l'échantillon."},
         {"enonce": "Une stratégie gagne sur la première moitié et perd sur la seconde. C'est :", "choix": ["Un signe de robustesse", "Un signe de fragilité", "Sans importance", "Une preuve de tendance"], "bonne": 1, "explication": "Un résultat qui dépend de la période choisie est probablement dû au hasard ou à un régime de marché particulier."},
     ],
     "exercices": [{"texte": "Comparez le croisement de moyennes et le RSI sur un titre : lequel gagne sur les deux moitiés ?", "lien": "/strategies", "libelle": "Ouvrir les stratégies"}]},
    {"id": "matieres", "titre": "Les matières premières", "niveau": "Intermédiaire", "minutes": 10,
     "resume": "Contrats à terme, chocs d'offre et de demande, prix négatif du pétrole.",
     "sections": [
         {"titre": "Des contrats plutôt que des barils", "texte": "Les investisseurs échangent des contrats à terme : l'engagement d'acheter ou de vendre une quantité à une date et un prix fixés. Quand l'échéance approche, on « roule » le contrat vers le suivant, ce qui peut coûter ou rapporter selon l'écart de prix entre les échéances."},
         {"titre": "Chocs et saisons", "texte": "L'offre des matières premières dépend de la météo, de la géopolitique et des décisions des producteurs ; la demande, de la conjoncture. Le pétrole et le gaz réagissent aux tensions internationales, les céréales aux récoltes, l'or à l'incertitude."},
         {"titre": "Quand le prix devient négatif", "texte": "En avril 2020, le contrat américain de pétrole WTI a clôturé sous zéro : la demande s'était effondrée, le stockage était saturé, et les détenteurs de contrats proches de l'échéance devaient payer pour ne pas recevoir de livraison. Un prix négatif est donc possible pour un actif physique difficile à stocker, et les rendements en pourcentage y perdent leur sens."},
     ],
     "questions": [
         {"enonce": "Pourquoi le prix du WTI a-t-il pu devenir négatif en avril 2020 ?", "choix": ["Erreur d'affichage", "Stockage saturé et demande effondrée près de l'échéance", "Le pétrole était devenu gratuit", "Décision de la banque centrale"], "bonne": 1, "explication": "Les détenteurs du contrat à échéance prochaine ne voulaient pas de livraison physique et payaient pour s'en défaire."},
         {"enonce": "Une sécheresse sévère fait en général :", "choix": ["Baisser les cours des céréales", "Monter les cours des céréales", "Monter le pétrole uniquement", "Ne rien changer"], "bonne": 1, "explication": "Une offre plus faible, à demande égale, pousse les prix à la hausse."},
         {"enonce": "« Rouler » un contrat à terme signifie :", "choix": ["Le revendre et acheter l'échéance suivante", "Le convertir en actions", "Le garder jusqu'à la livraison", "L'annuler sans frais"], "bonne": 0, "explication": "On évite la livraison physique en remplaçant le contrat proche par un contrat plus lointain."},
     ],
     "exercices": [{"texte": "Regardez le WTI en avril 2020 sur la frise du temps : que remarquez-vous sur le graphique ?", "lien": "/matieres", "libelle": "Ouvrir les matières premières"}]},
    {"id": "credit", "titre": "Risque de crédit : score Z et probabilité de défaut", "niveau": "Avancé", "minutes": 12,
     "resume": "Score Z d'Altman, probabilité de défaut, lecture des contributions.",
     "sections": [
         {"titre": "Le score Z", "texte": "Altman a combiné cinq ratios du bilan (fonds de roulement, bénéfices non distribués, rentabilité, capitaux propres sur dettes, rotation des actifs) en un score. Au-dessus de 2,99, l'entreprise est jugée saine ; sous 1,81, en zone de détresse ; entre les deux, la zone grise. C'est un repère statistique ancien, calé sur des entreprises industrielles américaines."},
         {"titre": "La probabilité de défaut", "texte": "Un modèle statistique estime la chance qu'un emprunteur ne rembourse pas. Dans une régression logistique, chaque variable pousse le « log des chances » vers le haut ou le bas : on peut donc expliquer précisément un résultat. Un bon modèle classe bien les emprunteurs (AUC) et ses probabilités sont calibrées (10 % prédit correspond à environ 10 % observé)."},
     ],
     "questions": [
         {"enonce": "Un score Z de 1,5 (version 1968) place l'entreprise en :", "choix": ["Zone saine", "Zone grise", "Zone de détresse", "Zone hors score"], "bonne": 2, "explication": "Sous 1,81, le modèle classe l'entreprise parmi celles qui ressemblent aux faillies du jeu d'origine."},
         {"enonce": "Une AUC de 0,5 signifie :", "choix": ["Un modèle parfait", "Un classement au hasard", "50 % de défauts", "Un modèle calibré"], "bonne": 1, "explication": "L'AUC est la chance de classer un défaut au-dessus d'un non-défaut : 0,5 correspond au hasard."},
         {"enonce": "Pourquoi une régression logistique est-elle facile à expliquer ?", "choix": ["Elle est toujours la plus précise", "Chaque variable ajoute une contribution exacte au log des chances", "Elle n'utilise pas de données", "Elle ne se trompe jamais"], "bonne": 1, "explication": "Le résultat est une somme de contributions : on voit ce qui a fait monter ou baisser le risque."},
     ],
     "exercices": [{"texte": "Calculez le score d'une entreprise en zone grise puis améliorez un ratio pour la faire passer en zone saine.", "lien": "/credit", "libelle": "Ouvrir le risque de crédit"}]},
    {"id": "banques", "titre": "Banques conventionnelles et islamiques face aux chocs", "niveau": "Avancé", "minutes": 12,
     "resume": "CET1, stress tests, mourabaha, salam, istisna, risque commercial déplacé.",
     "sections": [
         {"titre": "Le ratio de fonds propres", "texte": "Le ratio CET1 compare les fonds propres de meilleure qualité aux actifs pondérés des risques. Bâle III exige au moins 4,5 %, plus un coussin de conservation de 2,5 %, soit 7 %. Un test de résistance applique un choc et regarde où tombe le ratio."},
         {"titre": "Finance islamique", "texte": "La finance islamique interdit l'intérêt et s'adosse à des actifs réels. En mourabaha, la banque achète un bien puis le revend au client avec une marge connue, payable à terme. En salam, elle paie d'avance une marchandise livrée plus tard. En istisna, elle finance la fabrication d'un bien. Les déposants en comptes d'investissement partagent les pertes, mais la banque en absorbe souvent une partie pour éviter les retraits : c'est le risque commercial déplacé."},
     ],
     "questions": [
         {"enonce": "En mourabaha, quand la banque est-elle exposée au prix de la marchandise ?", "choix": ["Jamais", "Tant qu'elle détient le bien en stock avant de le revendre", "Seulement après la vente", "Uniquement en cas de salam"], "bonne": 1, "explication": "Entre l'achat et la revente, la banque porte le risque de variation du prix du bien."},
         {"enonce": "Le « risque commercial déplacé » désigne :", "choix": ["Un risque de change", "Des pertes que la banque absorbe à la place des déposants pour les retenir", "Un risque de fraude", "Un impôt spécifique"], "bonne": 1, "explication": "Elle renonce à une part de sa rémunération pour lisser le rendement des déposants, ce qui pèse sur ses fonds propres."},
         {"enonce": "Un CET1 de 6 % pour une banque soumise au coussin de conservation :", "choix": ["Respecte tous les seuils", "Est au-dessus du minimum de 4,5 % mais sous 7 %", "Est sous le minimum", "N'a pas de sens"], "bonne": 1, "explication": "Au-dessus de 4,5 % mais sous 7 %, la banque entame son coussin de conservation et voit ses distributions restreintes."},
     ],
     "exercices": [{"texte": "Appliquez un choc de −30 % sur l'énergie et comparez les banques conventionnelles et islamiques.", "lien": "/stress", "libelle": "Ouvrir les stress tests"}]},
    {"id": "assurance", "titre": "Assurance : prime et provisions", "niveau": "Avancé", "minutes": 10,
     "resume": "Fréquence, coût moyen, prime pure et commerciale, Chain Ladder.",
     "sections": [
         {"titre": "Calculer une prime", "texte": "La prime pure est le coût moyen attendu du contrat : fréquence des sinistres multipliée par leur coût moyen. La prime commerciale y ajoute une marge de sécurité (pour l'aléa) et les frais de gestion. La probabilité d'au moins un sinistre sur une durée est 1 moins l'exponentielle de moins fréquence fois durée."},
         {"titre": "Provisionner", "texte": "Une assurance doit mettre de côté de quoi régler des sinistres déjà survenus mais pas encore payés. Le Chain Ladder observe comment les règlements d'une année de survenance grossissent d'une année à l'autre, et applique ces facteurs aux années encore incomplètes."},
     ],
     "questions": [
         {"enonce": "Fréquence 0,10 par an et coût moyen 2 000 € : la prime pure annuelle vaut :", "choix": ["20 €", "200 €", "2 000 €", "20 000 €"], "bonne": 1, "explication": "0,10 × 2 000 = 200 €."},
         {"enonce": "La prime commerciale est :", "choix": ["Égale à la prime pure", "Inférieure à la prime pure", "La prime pure plus marge et frais", "Sans rapport avec la prime pure"], "bonne": 2, "explication": "Elle couvre le coût attendu, une marge de sécurité et les frais de l'assureur."},
         {"enonce": "Dans un triangle de règlements, les cases manquantes (en bas à droite) représentent :", "choix": ["Des erreurs de saisie", "Les règlements futurs à estimer", "Des sinistres refusés", "Des primes impayées"], "bonne": 1, "explication": "Ces règlements n'ont pas encore eu lieu : le Chain Ladder les estime."},
     ],
     "exercices": [{"texte": "Calculez la prime d'un conducteur de 22 ans puis celle d'un conducteur de 55 ans.", "lien": "/actuariat", "libelle": "Ouvrir l'actuariat"}]},
]
INDEX = {l["id"]: l for l in LECONS}
