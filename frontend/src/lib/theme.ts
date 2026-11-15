"use client";

import { useSyncExternalStore } from "react";

export type Theme = "sombre" | "clair";
const CLE = "sdm.theme";


export function themeCourant(): Theme {
  return typeof document !== "undefined" && document.documentElement.dataset.theme === "clair" ? "clair" : "sombre";
}

export function definirTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem(CLE, t); } catch { /* stockage indisponible : le choix ne sera pas mémorisé */ }
}

function abonner(rappel: () => void): () => void {
  const o = new MutationObserver(rappel);
  o.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => o.disconnect();
}

/** Thème actuel ; se met à jour dès qu'on bascule. */
export function useTheme(): Theme {
  return useSyncExternalStore(abonner, themeCourant, () => "sombre" as Theme);
}
