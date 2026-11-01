export interface LienNav { href: string; libelle: string; description?: string }
export interface GroupeNav { libelle: string; liens: LienNav[] }
export type EntreeNav = (LienNav & { groupe?: undefined }) | (GroupeNav & { href?: undefined });

/** Menu principal. Un groupe s'ouvre en liste déroulante. */
export const NAVIGATION: EntreeNav[] = [
  { href: "/", libelle: "Tableau de bord" },
  { libelle: "Marchés", liens: [
    { href: "/actions", libelle: "Actions" },
    { href: "/crypto", libelle: "Cryptomonnaies" },
    { href: "/matieres", libelle: "Matières premières" },
  ] },
  { href: "/portefeuille", libelle: "Portefeuille" },
  { libelle: "Analyse", liens: [
    { href: "/strategies", libelle: "Stratégies et backtesting", description: "Comparer des stratégies sur l'historique" },
    { href: "/actualites", libelle: "Actualités et sentiment", description: "Nouvelles datées et effet sur les cours" },
    { href: "/ia", libelle: "Intelligence artificielle", description: "Prédiction, régimes, anomalies, agent, optimiseur" },
  ] },
  { libelle: "Risque", liens: [
    { href: "/credit", libelle: "Risque de crédit", description: "Score Z d'Altman et probabilité de défaut" },
    { href: "/stress", libelle: "Stress tests bancaires", description: "Banques conventionnelles et islamiques face aux matières premières" },
    { href: "/actuariat", libelle: "Actuariat", description: "Prime d'assurance, probabilité de sinistre, provisions" },
  ] },
  { href: "/formation", libelle: "Formation" },
  { href: "/compte", libelle: "Compte" },
];
