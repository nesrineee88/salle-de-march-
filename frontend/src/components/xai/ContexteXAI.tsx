"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { ErreurApi, api } from "@/lib/api";
import { useLecture } from "@/lib/hooks";

export interface Preuve {
  methode: string;
  donnees: string[];
  limite: string;
  barres: { nom: string; valeur: number; affiche: string }[];
}
export interface Reponse {
  intention: string;
  instant: string;
  texte: string;
  preuve: Preuve;
  lien: { href: string; libelle: string } | null;
}
export interface Echange { id: number; question: string; reponse: Reponse | null; erreur: string | null }

interface ValeurXAI {
  fil: Echange[];
  attente: boolean;
  ouvert: boolean;
  page: string;                      // première partie du chemin
  suggestions: string[];
  basculer: () => void;
  fermer: () => void;
  demander: (question: string) => Promise<void>;
}

const Contexte = createContext<ValeurXAI | null>(null);
const FIL_MAX = 40;

/** Un seul fil de discussion, partagé par le panneau flottant et la page XAI. */
export function FournisseurXAI({ children }: { children: React.ReactNode }) {
  const chemin = usePathname();
  const [page = "", detail] = chemin.split("/").filter(Boolean);
  const [ouvert, setOuvert] = useState(false);
  const [fil, setFil] = useState<Echange[]>([]);
  const [attente, setAttente] = useState(false);
  const occupe = useRef(false);
  const suivant = useRef(1);
  const { donnees } = useLecture<Record<string, string[]>>(ouvert || page === "xai" ? "/api/v1/xai/suggestions" : null, 600_000);
  const symbole = page === "actif" && detail ? decodeURIComponent(detail) : null;

  const demander = useCallback(async (texte: string) => {
    const question = texte.trim();
    if (!question || occupe.current) return;
    occupe.current = true;
    setAttente(true);
    const id = suivant.current++;
    setFil((f) => [...f, { id, question, reponse: null, erreur: null }].slice(-FIL_MAX));
    let reponse: Reponse | null = null;
    let erreur: string | null = null;
    try {
      reponse = await api<Reponse>("/api/v1/xai/question", { methode: "POST", corps: { question, symbole } });
    } catch (e) {
      erreur = e instanceof ErreurApi && e.statut === 404 ? "Le serveur Python ne connaît pas encore l’assistant : redémarrez-le."
        : e instanceof ErreurApi && e.statut >= 500 ? "Le serveur ne répond pas. Réessayez dans un instant."
        : e instanceof Error ? e.message : "Réponse impossible.";
    }
    setFil((f) => f.map((x) => (x.id === id ? { ...x, reponse, erreur } : x)));
    occupe.current = false;
    setAttente(false);
  }, [symbole]);

  const basculer = useCallback(() => setOuvert((v) => !v), []);
  const fermer = useCallback(() => setOuvert(false), []);
  const suggestions = useMemo(() => {
    const cle = page === "actions" || page === "crypto" || page === "matieres" ? "marche" : page;
    return donnees?.[cle] ?? donnees?.[""] ?? [];
  }, [donnees, page]);

  const valeur = useMemo<ValeurXAI>(() => ({ fil, attente, ouvert, page, suggestions, basculer, fermer, demander }),
    [fil, attente, ouvert, page, suggestions, basculer, fermer, demander]);
  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}

export function useXAI() {
  const valeur = useContext(Contexte);
  if (!valeur) throw new Error("useXAI doit être utilisé dans FournisseurXAI");
  return valeur;
}
