"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * Liste de suivi (« Mes suivis ») : les actifs que l'utilisateur veut garder sous les yeux.
 * Elle est mémorisée dans le navigateur, par compte. Elle n'est pas encore partagée entre appareils.
 */
const VIDE: string[] = [];
const caches = new Map<string, string[]>();
const ecouteurs = new Set<() => void>();
const cle = (compte: string) => `sdm.suivis.${compte}`;

function lire(compte: string): string[] {
  if (typeof window === "undefined") return VIDE;
  const memo = caches.get(compte);
  if (memo) return memo;
  let liste: string[] = VIDE;
  try {
    const brut = JSON.parse(localStorage.getItem(cle(compte)) || "[]");
    if (Array.isArray(brut)) liste = brut.filter((s): s is string => typeof s === "string");
  } catch { /* liste vide */ }
  caches.set(compte, liste);
  return liste;
}

function ecrire(compte: string, liste: string[]): void {
  caches.set(compte, liste);
  try { localStorage.setItem(cle(compte), JSON.stringify(liste)); } catch { /* le choix ne sera pas mémorisé */ }
  ecouteurs.forEach((f) => f());
}

function abonner(rappel: () => void): () => void {
  ecouteurs.add(rappel);
  return () => { ecouteurs.delete(rappel); };
}

export function useSuivis(compte: string): {
  suivis: string[];
  estSuivi: (symbole: string) => boolean;
  basculer: (symbole: string) => void;
} {
  const suivis = useSyncExternalStore(abonner, () => lire(compte), () => VIDE);
  const basculer = useCallback((symbole: string) => {
    const actuel = lire(compte);
    ecrire(compte, actuel.includes(symbole) ? actuel.filter((s) => s !== symbole) : [...actuel, symbole]);
  }, [compte]);
  return { suivis, estSuivi: (s) => suivis.includes(s), basculer };
}
