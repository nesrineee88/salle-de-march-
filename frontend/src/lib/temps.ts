"use client";

import { useEffect, useState } from "react";
import { instantDate } from "./format";
import type { Instantane } from "./types";

/** Événements qui ouvrent les fenêtres du temps depuis n'importe quel écran. */
export const OUVRIR_DATES_EVENT = "sdm:ouvrir-dates";
export const OUVRIR_DIRECT_EVENT = "sdm:ouvrir-direct";
export const ouvrirDates = () => window.dispatchEvent(new Event(OUVRIR_DATES_EVENT));
export const ouvrirDirect = () => window.dispatchEvent(new Event(OUVRIR_DIRECT_EVENT));

/** Heure d'arrivée d'un changement de date : en séance américaine (14 h 30 à 21 h UTC), pour pouvoir passer un ordre. */
export const HEURE_ARRIVEE = "17:00:00";

export function jourPlus(iso: string, n: number): string {
  return new Date(Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) + n * 86_400_000).toISOString().slice(0, 10);
}

/** Horloge affichée en continu : entre deux réponses du serveur, on avance localement au même rythme. */
export function useInstantLisse(inst: Instantane | null): string | null {
  const [affiche, setAffiche] = useState<string | null>(null);
  const instant = inst?.instant;
  const facteur = inst?.horloge.facteur;
  const enPause = inst?.horloge.en_pause;
  const fin = inst?.fenetre.fin;
  const direct = inst?.direct;

  useEffect(() => {
    if (!instant || facteur === undefined) return;
    const base = instantDate(instant).getTime();
    const limite = !direct && fin ? Date.parse(`${fin}T23:59:59Z`) : Infinity;
    const depart = performance.now();
    const maj = () => setAffiche(new Date(Math.min(limite, base + (enPause ? 0 : (performance.now() - depart) * facteur))).toISOString());
    maj();
    if (enPause) return;
    const t = setInterval(maj, 500);
    return () => clearInterval(t);
  }, [instant, facteur, enPause, fin, direct]);

  return inst ? affiche ?? inst.instant : null;
}
