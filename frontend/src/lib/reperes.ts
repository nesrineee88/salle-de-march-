/** Repères historiques sur la frise. Dates à confirmer sur les données une fois l'instantané téléchargé. */
export interface Repere {
  date: string;
  titre: string;
  explication: string;
}

export const REPERES: Repere[] = [
  { date: "2018-12-24", titre: "Creux boursier de fin 2018", explication: "Les actions américaines touchent leur point bas de l'année." },
  { date: "2020-03-09", titre: "Krach du COVID-19", explication: "Chute brutale des marchés actions et du pétrole au début de la pandémie." },
  { date: "2020-04-20", titre: "Le WTI passe sous zéro", explication: "Le contrat de pétrole WTI clôture à un prix négatif." },
  { date: "2022-05-09", titre: "Krach des cryptomonnaies", explication: "L'effondrement de Terra et Luna entraîne une chute du marché crypto." },
  { date: "2024-08-05", titre: "Secousse sur la Bourse japonaise", explication: "Forte chute des marchés actions, surtout au Japon, et bond de la volatilité (de mémoire, à confirmer)." },
  { date: "2025-04-03", titre: "Annonce de nouveaux droits de douane américains", explication: "Les marchés actions chutent après l'annonce de droits de douane étendus (de mémoire, à confirmer). Aucun repère n'est fourni pour 2026." },
];
