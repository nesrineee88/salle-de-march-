"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

/** Lit une adresse de l'API et la relit à intervalle régulier tant que l'onglet est visible. */
export function useLecture<T>(chemin: string | null, intervalleMs = 5000): { donnees: T | null; erreur: string | null; relire: () => Promise<void> } {
  const [donnees, setDonnees] = useState<T | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const cheminRef = useRef(chemin);
  cheminRef.current = chemin;

  const relire = useCallback(async () => {
    const c = cheminRef.current;
    if (!c) return;
    try {
      const d = await api<T>(c);
      if (c === cheminRef.current) { setDonnees(d); setErreur(null); }
    } catch (e) {
      setErreur(e instanceof Error ? e.message : "Lecture impossible.");
    }
  }, []);

  useEffect(() => {
    void relire();
    const t = setInterval(() => { if (document.visibilityState === "visible") void relire(); }, intervalleMs);
    return () => clearInterval(t);
  }, [chemin, intervalleMs, relire]);

  return { donnees, erreur, relire };
}
