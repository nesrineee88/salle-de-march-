"use client";

import { useSyncExternalStore } from "react";

export type Theme = "sombre" | "clair";
const CLE = "sdm.theme";

/** Script exécuté avant l'affichage : applique le thème enregistré, pour éviter un éclair de la mauvaise couleur. */
export const SCRIPT_THEME = `try{if(localStorage.getItem("${CLE}")==="clair"){document.documentElement.dataset.theme="clair"}}catch(e){}`;

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
