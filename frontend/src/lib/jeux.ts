"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * Progression des jeux de la Formation (« Repère le piège », défi « Survis à mars 2020 »).
 * Mémorisée dans le navigateur, par compte : elle ne compte pas dans la ligue (qui juge les vrais portefeuilles).
 */
export interface Defi {
  debut: string;             // jour de départ (AAAA-MM-JJ)
  fin: string;
  limite: number;            // pire baisse tolérée (0,15 = 15 %)
  statut: "en_cours" | "reussi" | "echoue";
  pire: number;              // pire baisse constatée depuis le départ
  rendement: number;         // rendement à la fin ou à l'élimination
  points: number;
}
export interface EtatJeux { pieges: Record<string, number>; defi: Defi | null }

const VIDE: EtatJeux = { pieges: {}, defi: null };
const caches = new Map<string, EtatJeux>();
const ecouteurs = new Set<() => void>();
const cle = (compte: string) => `sdm.jeux.${compte}`;

function lire(compte: string): EtatJeux {
  if (typeof window === "undefined") return VIDE;
  const memo = caches.get(compte);
  if (memo) return memo;
  let etat = VIDE;
  try {
    const b = JSON.parse(localStorage.getItem(cle(compte)) || "{}");
    etat = { pieges: b && typeof b.pieges === "object" && b.pieges ? b.pieges : {}, defi: b?.defi && typeof b.defi.debut === "string" ? b.defi : null };
  } catch { /* état vide */ }
  caches.set(compte, etat);
  return etat;
}
function ecrire(compte: string, etat: EtatJeux): void {
  caches.set(compte, etat);
  try { localStorage.setItem(cle(compte), JSON.stringify(etat)); } catch { /* non mémorisé */ }
  ecouteurs.forEach((f) => f());
}
const abonner = (r: () => void) => { ecouteurs.add(r); return () => { ecouteurs.delete(r); }; };

export function useJeux(compte: string) {
  const etat = useSyncExternalStore(abonner, () => lire(compte), () => VIDE);
  const enregistrerPiege = useCallback((id: string, pts: number) => {
    const e = lire(compte);
    if (e.pieges[id] === undefined || pts > e.pieges[id]) ecrire(compte, { ...e, pieges: { ...e.pieges, [id]: pts } });
  }, [compte]);
  const definirDefi = useCallback((d: Defi | null) => ecrire(compte, { ...lire(compte), defi: d }), [compte]);
  const points = Object.values(etat.pieges).reduce((s, p) => s + p, 0) + (etat.defi?.statut === "en_cours" ? 0 : etat.defi?.points ?? 0);
  return { etat, points, enregistrerPiege, definirDefi };
}

const NIVEAUX = [
  { nom: "Débutant", min: 0 }, { nom: "Apprenti", min: 250 }, { nom: "Trader", min: 600 },
  { nom: "Stratège", min: 1100 }, { nom: "Expert", min: 1800 },
];
/** Niveau atteint pour un total de points, et avancement vers le suivant. */
export function niveauDepuis(points: number) {
  let i = 0;
  while (i + 1 < NIVEAUX.length && points >= NIVEAUX[i + 1].min) i++;
  const suivant = NIVEAUX[i + 1];
  return { numero: i + 1, nom: NIVEAUX[i].nom, suivant: suivant?.nom ?? null, restant: suivant ? suivant.min - points : 0,
    avancement: suivant ? (points - NIVEAUX[i].min) / (suivant.min - NIVEAUX[i].min) : 1 };
}
