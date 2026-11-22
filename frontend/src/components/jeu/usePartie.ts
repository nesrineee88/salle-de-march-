"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ErreurApi, api } from "@/lib/api";
import type { Acte, Partie } from "./types";

type Action =
  | { nom: "avancer"; corps?: { jusqu_a_l_arret: boolean } }
  | { nom: "ordres"; corps: { rang: number; sens: "achat" | "vente" } }
  | { nom: "choix"; corps: { acte: Acte } }
  | { nom: "deviner"; corps: { film: string } };

const ATTENTE_RESEAU = 2000;
/** Le serveur ne répond pas, ou redémarre (le relais de Next renvoie alors une 500). */
const horsLigne = (e: unknown) => !(e instanceof ErreurApi) || e.statut === 0 || e.statut >= 500;

/** Une partie. Les actions partent l'une après l'autre, chacune depuis le dernier état connu du serveur. */
export function usePartie(initiale: Partie) {
  const [partie, setPartie] = useState(initiale);
  const [coupure, setCoupure] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const courante = useRef(initiale);
  const file = useRef<Promise<unknown>>(Promise.resolve());
  const monte = useRef(true);

  useEffect(() => {
    monte.current = true;
    return () => { monte.current = false; };
  }, []);

  const poser = useCallback((p: Partie) => {
    courante.current = p;
    if (monte.current) setPartie(p);
  }, []);

  const agir = useCallback((action: Action) => {
    const tour = file.current.then(async () => {
      if (!monte.current) return;
      const p = courante.current;
      if (action.nom === "avancer" && (p.arret || p.statut !== "en_cours")) return;
      try {
        poser(await api<Partie>(`/api/v1/jeu/parties/${p.id}/${action.nom}`, { methode: "POST", corps: { version: p.version, ...action.corps } }));
        if (monte.current) setCoupure(false);
      } catch (e) {
        if (!monte.current) return;
        if (horsLigne(e)) { setCoupure(true); return; }
        const erreur = e as ErreurApi;
        if (erreur.code !== "version_perimee" && erreur.code !== "decision_attendue") setMessage(erreur.message);
        if (erreur.statut === 409) {
          try { poser(await api<Partie>(`/api/v1/jeu/parties/${p.id}`)); } catch { setCoupure(true); }
        }
      }
    });
    file.current = tour;
    return tour;
  }, [poser]);

  // coupure ou redémarrage du serveur : on relit la partie jusqu'à ce qu'il réponde, puis le film reprend
  useEffect(() => {
    if (!coupure) return;
    let actif = true;
    let minuteur: number | undefined;
    const essayer = async () => {
      try {
        const p = await api<Partie>(`/api/v1/jeu/parties/${courante.current.id}`);
        if (actif) { poser(p); setCoupure(false); }
      } catch {
        if (actif) minuteur = window.setTimeout(() => void essayer(), ATTENTE_RESEAU);
      }
    };
    minuteur = window.setTimeout(() => void essayer(), ATTENTE_RESEAU);
    return () => { actif = false; window.clearTimeout(minuteur); };
  }, [coupure, poser]);

  useEffect(() => {
    if (!message) return;
    const t = window.setTimeout(() => setMessage(null), 4000);
    return () => window.clearTimeout(t);
  }, [message]);

  return { partie, agir, coupure, message };
}
