/** Scénarios du jeu « Repère le piège ». Chaque situation contient une erreur de gestion classique ; une seule réponse est la bonne. */
export interface Piege {
  id: string;
  titre: string;
  situation: string;
  tableau?: { entetes: string[]; lignes: string[][] };
  question: string;
  choix: { texte: string; explication: string }[];
  piege: number;           // indice du choix qui est l'erreur
  retenir: string;
}

export const PIEGES: Piege[] = [
  {
    id: "concentration", titre: "Tout dans le même panier",
    situation: "Léa investit 10 000 $ et pense avoir bien réparti son portefeuille.",
    tableau: { entetes: ["Actif", "Poids"], lignes: [["Tesla", "62 %"], ["Apple", "14 %"], ["Bitcoin", "10 %"], ["Or", "8 %"], ["Liquidités", "6 %"]] },
    question: "Quelle est l'erreur principale ?",
    choix: [
      { texte: "Elle garde trop de liquidités", explication: "6 % de liquidités, c'est raisonnable : cela permet de saisir des occasions et d'amortir un choc." },
      { texte: "Une seule action pèse 62 % du portefeuille", explication: "Exact. Si Tesla perd 40 %, le portefeuille perd environ 25 % à cause de cette seule ligne (0,62 × 40 %)." },
      { texte: "Elle détient de l'or", explication: "L'or peut au contraire diversifier : il ne bouge pas toujours comme les actions." },
      { texte: "Elle a acheté du Bitcoin", explication: "Ce n'est pas l'actif le problème, c'est la taille : ici 10 %, ce qui reste mesuré." },
    ],
    piege: 1, retenir: "Aucune position ne devrait, à elle seule, pouvoir ruiner le portefeuille.",
  },
  {
    id: "moyenne", titre: "Se rattraper à tout prix",
    situation: "Karim a acheté une action à 100 $. Elle tombe à 70 $, sans aucune nouvelle. Il décide d'acheter deux fois plus pour « se rattraper ».",
    question: "Quelle est l'erreur ?",
    choix: [
      { texte: "Il aurait dû vendre à 99 $", explication: "Facile à dire après coup. Personne ne sait à l'avance où une baisse s'arrête." },
      { texte: "Il double sa mise sur une position perdante sans avoir réexaminé sa raison d'acheter", explication: "Exact. Renforcer peut se défendre si la thèse est intacte et si la taille était prévue. Ici la décision est émotionnelle : on augmente le risque pour effacer une perte." },
      { texte: "Il aurait dû attendre le lendemain", explication: "Attendre un jour ne change rien à la qualité de la décision." },
      { texte: "Acheter après une baisse est toujours interdit", explication: "Faux : c'est parfois une bonne occasion. Tout dépend de la raison et de la taille." },
    ],
    piege: 1, retenir: "Une perte passée n'est pas une raison d'acheter. Décidez comme si vous partiez d'une feuille blanche.",
  },
  {
    id: "frais", titre: "Le gain qui n'en est pas un",
    situation: "Sam passe 30 ordres en deux jours et se félicite : son portefeuille a gagné.",
    tableau: { entetes: ["Mesure", "Valeur"], lignes: [["Gain avant frais", "+1,2 %"], ["Frais et écart achat-vente", "−1,5 %"], ["Résultat réel", "−0,3 %"]] },
    question: "Quelle est l'erreur de Sam ?",
    choix: [
      { texte: "Il compte son gain avant les frais", explication: "Exact. Chaque ordre coûte des frais et un écart achat-vente. Avec beaucoup d'ordres, ils dépassent souvent le gain." },
      { texte: "Il n'a pas assez diversifié", explication: "Le tableau ne dit rien de la diversification : le problème est ailleurs." },
      { texte: "Il a vendu trop tard", explication: "Rien n'indique cela. Le tableau montre un résultat net négatif à cause des coûts." },
      { texte: "Il a choisi un mauvais jour", explication: "Le jour n'explique pas un résultat qui devient négatif une fois les coûts comptés." },
    ],
    piege: 0, retenir: "Ce qui compte, c'est le résultat après frais. Plus on trade, plus les coûts pèsent.",
  },
  {
    id: "stop", titre: "Le stop qui saute tout de suite",
    situation: "Inès achète une action qui bouge en moyenne de 3 % par jour. Elle place son stop-loss à 0,5 % sous son prix d'achat.",
    question: "Quelle est l'erreur ?",
    choix: [
      { texte: "Un stop-loss est toujours inutile", explication: "Faux : bien placé, il limite la perte et évite de décider dans l'émotion." },
      { texte: "Son stop est plus serré que les mouvements normaux du prix", explication: "Exact. Une variation de 0,5 % arrive plusieurs fois par jour : elle sera sortie par le « bruit », sans que sa thèse soit fausse. On règle un stop selon la volatilité." },
      { texte: "Elle aurait dû mettre son stop à 50 %", explication: "Trop large, il ne protégerait plus rien. Le bon niveau tient compte de la volatilité, ni trop serré ni trop loin." },
      { texte: "Les stops ne fonctionnent que sur les cryptomonnaies", explication: "Faux : ils s'utilisent sur tous les actifs négociés." },
    ],
    piege: 1, retenir: "Réglez le stop au-delà du bruit habituel du prix, et pensez à la perte maximale acceptée.",
  },
  {
    id: "fausse-diversification", titre: "La diversification en trompe-l'œil",
    situation: "Yanis détient cinq grandes entreprises, 20 % chacune, et se dit bien diversifié.",
    tableau: { entetes: ["Actif", "Secteur", "Pays"], lignes: [["Apple", "Technologie", "États-Unis"], ["Microsoft", "Technologie", "États-Unis"], ["Nvidia", "Technologie", "États-Unis"], ["Alphabet", "Technologie", "États-Unis"], ["Amazon", "Technologie", "États-Unis"]] },
    question: "Où est l'erreur ?",
    choix: [
      { texte: "Cinq positions, c'est trop peu", explication: "Le nombre n'est pas le vrai problème : ce qui compte, c'est que les positions bougent différemment." },
      { texte: "Les grandes entreprises sont trop risquées", explication: "Pas en soi. Le défaut ici est que toutes se ressemblent." },
      { texte: "Elles sont du même secteur et du même pays : elles montent et baissent souvent ensemble", explication: "Exact. Compter les lignes ne suffit pas : des actifs très corrélés se comportent comme un seul gros pari. Regardez la page Portefeuille, onglet corrélations." },
      { texte: "20 % chacune, c'est trop équilibré", explication: "Une répartition égale n'est pas un défaut." },
    ],
    piege: 2, retenir: "Diversifier, c'est mélanger des actifs qui ne réagissent pas pareil, pas multiplier les lignes.",
  },
  {
    id: "fomo", titre: "La peur de rater le train",
    situation: "Un actif vient de gagner 40 % en trois jours et tout le monde en parle. Nour y met la moitié de son capital, sans plan de sortie.",
    question: "Quelle est l'erreur ?",
    choix: [
      { texte: "Elle aurait dû acheter avant la hausse", explication: "Impossible à savoir à l'avance. Le jugement après coup n'aide pas à décider." },
      { texte: "Acheter un actif qui a monté est interdit", explication: "Faux : une tendance peut continuer. Ce n'est pas l'achat qui pose problème." },
      { texte: "Elle aurait dû y mettre tout son capital", explication: "Cela aggraverait le risque, pas l'inverse." },
      { texte: "Elle achète par peur de rater le mouvement, avec une grosse mise et sans plan de sortie", explication: "Exact. Trois signaux d'alerte : la décision vient de la foule, la taille est démesurée, et rien n'est prévu si le prix retombe." },
    ],
    piege: 3, retenir: "Avant d'acheter, écrivez la taille, le niveau de sortie et la raison. Si vous ne pouvez pas, n'achetez pas.",
  },
];
