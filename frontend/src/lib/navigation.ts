import type { Role } from "./types";

export interface LienNav { href: string; libelle: string; description?: string; roles?: Role[]; aussi?: string[]; mobile?: boolean }

/** Destinations du rail, dans l'ordre du prototype (docs/design/seance-prototype.html).
 *  `mobile` : reste dans la barre du bas sur téléphone. Les autres passent dans « Plus ». */
export const PRINCIPALES: LienNav[] = [
  { href: "/", libelle: "Dashboard", description: "Rendement, indices et niveau de risque", mobile: true },
  { href: "/marche", libelle: "Marché", description: "Explorer les actifs et passer un ordre", aussi: ["/actions", "/crypto", "/matieres", "/actif"], mobile: true },
  { href: "/portefeuille", libelle: "Portefeuille", description: "Positions, historique et mesures de risque", mobile: true },
  { href: "/strategies", libelle: "Analyse", description: "Comparer des stratégies sur l'historique" },
  { href: "/jeu", libelle: "Jeu", description: "La Salle Obscure : rejouer une vraie crise", mobile: true },
  { href: "/stress", libelle: "Stress test", description: "Banques conventionnelles et islamiques face aux chocs" },
  { href: "/formation", libelle: "Formation", description: "Leçons, quiz, défi et ligue" },
  { href: "/actuariat", libelle: "Assurance", description: "Prime, probabilité de sinistre, provisions" },
  { href: "/xai", libelle: "XAI", description: "L'assistant qui répond et qui prouve" },
];

/** Pages gardées, rangées sous « Plus ». */
export const SECONDAIRES: LienNav[] = [
  { href: "/actualites", libelle: "Actualités", description: "Nouvelles datées et effet sur les cours" },
  { href: "/credit", libelle: "Crédit", description: "Score Z d'Altman et probabilité de défaut" },
  { href: "/ia", libelle: "Modèles IA", description: "Prédiction, régimes, anomalies, optimiseur", roles: ["trader", "formateur", "admin"] },
  { href: "/compte", libelle: "Compte", description: "Profil de risque, sessions, données" },
  { href: "/admin", libelle: "Admin", description: "Comptes, crises et actualités", roles: ["admin"] },
];

export const visiblesPour = (liens: LienNav[], role: Role) => liens.filter((l) => !l.roles || l.roles.includes(role));

export function estActif(lien: LienNav, chemin: string): boolean {
  if (lien.href === "/") return chemin === "/";
  return [lien.href, ...(lien.aussi ?? [])].some((h) => chemin === h || chemin.startsWith(`${h}/`));
}

export function pagesNavigation(role: Role): LienNav[] {
  return visiblesPour([...PRINCIPALES, ...SECONDAIRES], role);
}
