import type { Actif, Classe } from "./types";

/** Page de marché qui présente cet actif. Les indices de référence sont sur la page des actions. */
export function pageDeClasse(classe: Classe): string {
  return classe === "crypto" ? "/crypto" : classe === "matiere" ? "/matieres" : "/actions";
}

export function lienActif(actif: Pick<Actif, "symbole" | "classe">): string {
  return `${pageDeClasse(actif.classe)}?actif=${encodeURIComponent(actif.symbole)}`;
}

/** Événement envoyé quand on demande un actif alors qu'on est déjà sur la bonne page de marché. */
export const EVENEMENT_ACTIF = "sdm:actif";

/** Fiche de l'actif (À propos, graphique, actualités, indicateurs, position). */
export function lienFiche(symbole: string): string {
  return `/actif/${encodeURIComponent(symbole)}`;
}

/** Ouvre la fiche de l'actif. La page de négociation reste accessible depuis la fiche (« Trader »). */
export function ouvrirActif(router: { push: (url: string) => void }, actif: Pick<Actif, "symbole" | "classe">): void {
  router.push(lienFiche(actif.symbole));
}

/** Couleur et initiales de l'avatar d'un actif (repère visuel, pas un logo : aucun logo d'entreprise n'est utilisé). */
export function avatarActif(actif: Pick<Actif, "symbole" | "nom" | "classe">): { initiales: string; teinte: number } {
  const mots = actif.nom.replace(/[^\p{L}\p{N} ]/gu, "").split(" ").filter(Boolean);
  const initiales = (mots.length > 1 ? mots[0][0] + mots[1][0] : (mots[0] ?? actif.symbole).slice(0, 2));
  let h = 0;
  for (const c of actif.symbole) h = (h * 31 + c.charCodeAt(0)) % 360;
  return { initiales: initiales.charAt(0).toUpperCase() + initiales.slice(1).toLowerCase(), teinte: h };
}

/** Symbole demandé dans l'adresse (?actif=...), lu côté navigateur. */
export function symboleDansAdresse(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("actif");
}

/** Forme courte d'un symbole pour le bandeau : « BTC-USD » devient « BTC », « GC=F » devient « GC ». */
export function symboleCourt(symbole: string): string {
  return symbole.replace(/-USD$/, "").replace(/=F$/, "").replace(/^\^/, "");
}

/** Variation en fraction depuis la référence de la cotation, ou null si elle n'existe pas. */
export function variationCotation(c: { prix: number; reference: number | null; derniere_cloture: number | null }): number | null {
  const base = c.reference ?? c.derniere_cloture;
  return base ? (c.prix - base) / Math.abs(base) : null;
}
