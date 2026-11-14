"use client";

import { useSyncExternalStore } from "react";

/** Les trois modèles de mise en page. Ils changent l'allure (arrondis, densité, chiffres) sans toucher aux données. */
export type Modele = "courtage" | "terminal" | "fintech" | "crypto" | "wallet" | "investissement";
/** Palettes de couleurs : elles changent les fonds, les filets et l'accent, jamais le bleu des gains ni l'orange des pertes. */
export type Palette = "nuit" | "ocean" | "ardoise" | "foret";
/** Fond animé : courbes de prix en dérive derrière l'interface. */
export type Fond = "aucun" | "discret" | "vivant";
export type Densite = "compacte" | "normale" | "aeree";

export interface Apparence {
  modele: Modele;
  palette: Palette;
  fond: Fond;
  curseur: boolean;      // halo lumineux qui suit la souris
  densite: Densite;
  menuReplie: boolean;   // menu latéral réduit à ses icônes
  bandeau: boolean;      // bandeau de cours sous la barre du haut
}

export const MODELES: { cle: Modele; nom: string; description: string }[] = [
  { cle: "courtage", nom: "Courtage", description: "Équilibré : menu à gauche, panneaux à filet fin." },
  { cle: "terminal", nom: "Terminal pro", description: "Dense et technique : angles droits, chiffres à chasse fixe." },
  { cle: "fintech", nom: "Fintech", description: "Aéré : grands arrondis, grands chiffres, panneaux doux." },
  { cle: "crypto", nom: "Crypto Dashboard", description: "Fond noir profond, panneaux en verre dépoli, lueurs." },
  { cle: "wallet", nom: "Crypto Wallet", description: "Cartes à dégradé, très arrondi, boutons en pilule." },
  { cle: "investissement", nom: "Investment Platform", description: "Sobre et dense : filets fins, majuscules, bleu de confiance." },
];

export const PALETTES: { cle: Palette; nom: string; teintes: [string, string, string] }[] = [
  { cle: "nuit", nom: "Nuit", teintes: ["#0b1620", "#162838", "#f0d58a"] },
  { cle: "ocean", nom: "Océan", teintes: ["#071a1f", "#12323a", "#7fd6d0"] },
  { cle: "ardoise", nom: "Ardoise", teintes: ["#0e1116", "#1b212c", "#d8c9a3"] },
  { cle: "foret", nom: "Forêt", teintes: ["#0a1713", "#163029", "#e3d28f"] },
];

export const DENSITES: { cle: Densite; nom: string }[] = [
  { cle: "compacte", nom: "Compacte" },
  { cle: "normale", nom: "Normale" },
  { cle: "aeree", nom: "Aérée" },
];

export const APPARENCE_PAR_DEFAUT: Apparence = { modele: "wallet", palette: "nuit", fond: "vivant", curseur: true, densite: "normale", menuReplie: false, bandeau: true };

const CLE = "sdm.apparence";


let cache: Apparence = APPARENCE_PAR_DEFAUT;
let charge = false;
const ecouteurs = new Set<() => void>();

function valider(brut: Partial<Apparence>): Apparence {
  const modele = MODELES.some((m) => m.cle === brut.modele) ? (brut.modele as Modele) : APPARENCE_PAR_DEFAUT.modele;
  const palette = PALETTES.some((p) => p.cle === brut.palette) ? (brut.palette as Palette) : APPARENCE_PAR_DEFAUT.palette;
  const fond: Fond = brut.fond === "aucun" || brut.fond === "discret" || brut.fond === "vivant" ? brut.fond : APPARENCE_PAR_DEFAUT.fond;
  const densite = DENSITES.some((d) => d.cle === brut.densite) ? (brut.densite as Densite) : APPARENCE_PAR_DEFAUT.densite;
  return {
    modele,
    palette,
    fond,
    curseur: typeof brut.curseur === "boolean" ? brut.curseur : APPARENCE_PAR_DEFAUT.curseur,
    densite,
    menuReplie: typeof brut.menuReplie === "boolean" ? brut.menuReplie : APPARENCE_PAR_DEFAUT.menuReplie,
    bandeau: typeof brut.bandeau === "boolean" ? brut.bandeau : APPARENCE_PAR_DEFAUT.bandeau,
  };
}

function appliquer(a: Apparence): void {
  document.documentElement.dataset.modele = a.modele;
  document.documentElement.dataset.palette = a.palette;
  document.documentElement.dataset.fond = a.fond;
  document.documentElement.dataset.densite = a.densite;
}

function lire(): Apparence {
  if (typeof window === "undefined") return APPARENCE_PAR_DEFAUT;
  if (!charge) {
    charge = true;
    try { cache = valider(JSON.parse(localStorage.getItem(CLE) || "{}")); } catch { cache = APPARENCE_PAR_DEFAUT; }
    appliquer(cache);
  }
  return cache;
}

export function definirApparence(partiel: Partial<Apparence>): void {
  cache = valider({ ...lire(), ...partiel });
  appliquer(cache);
  try { localStorage.setItem(CLE, JSON.stringify(cache)); } catch { /* stockage indisponible : le choix ne sera pas mémorisé */ }
  ecouteurs.forEach((f) => f());
}

export function reinitialiserApparence(): void {
  definirApparence(APPARENCE_PAR_DEFAUT);
}

function abonner(rappel: () => void): () => void {
  ecouteurs.add(rappel);
  return () => { ecouteurs.delete(rappel); };
}

/** Préférences d'apparence actuelles ; se met à jour dès qu'on les change. */
export function useApparence(): Apparence {
  return useSyncExternalStore(abonner, lire, () => APPARENCE_PAR_DEFAUT);
}
