"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { ErreurApi } from "@/lib/api";
import type { Actif, Execution, Instantane, Ordre, Portefeuille, Regle, TypeRegle, Utilisateur } from "@/lib/types";
import type { CorpsOrdre } from "./Ticket";

export type Mode = "apprenant" | "trader";

interface ValeurContexte {
  utilisateur: Utilisateur;
  majUtilisateur: (u: Utilisateur) => void;
  deconnecter: () => void;
  inst: Instantane | null;
  actifs: Actif[];
  pf: Portefeuille | null;
  ordres: Ordre[];
  execs: Execution[];
  regles: Regle[];
  poserRegle: (corps: { symbole: string; type: TypeRegle; seuil_pct: number; part_pct: number }) => Promise<Regle>;
  supprimerRegle: (id: number) => Promise<void>;
  erreurReseau: string | null;
  derniereReussiteMarche: string | null;
  derniereReussiteCompte: string | null;
  mode: Mode;
  setMode: (m: Mode) => void;
  aller: (iso: string) => Promise<void>;
  /** Repart du capital initial à cette date : seul moyen de reculer. */
  recommencer: (iso: string) => Promise<void>;
  basculerPause: () => Promise<void>;
  changerFacteur: (f: number) => Promise<void>;
  activerDirect: () => Promise<void>;
  quitterDirect: () => Promise<void>;
  reinitialiser: () => Promise<void>;
  envoyer: (corps: CorpsOrdre) => Promise<Ordre>;
  annuler: (id: number) => Promise<void>;
  rafraichir: () => Promise<void>;
}

const Ctx = createContext<ValeurContexte | null>(null);

export function useMarche(): ValeurContexte {
  const v = useContext(Ctx);
  if (!v) throw new Error("useMarche doit être utilisé dans le fournisseur de marché.");
  return v;
}

const CLE_MODE = "sdm.mode";

function useLecturePeriodique(lire: () => Promise<void>, intervalleMs: number) {
  useEffect(() => {
    let active = true;
    let enCours = false;
    let minuteur: number | undefined;

    const programmer = () => { minuteur = window.setTimeout(() => void executer(), intervalleMs); };
    const executer = async () => {
      if (!active || enCours) return;
      if (document.visibilityState !== "visible") { programmer(); return; }
      enCours = true;
      try {
        await lire();
      } finally {
        enCours = false;
        if (active) programmer();
      }
    };
    const retourVisible = () => {
      if (document.visibilityState === "visible" && !enCours) {
        if (minuteur !== undefined) window.clearTimeout(minuteur);
        void executer();
      }
    };

    void executer();
    document.addEventListener("visibilitychange", retourVisible);
    return () => {
      active = false;
      if (minuteur !== undefined) window.clearTimeout(minuteur);
      document.removeEventListener("visibilitychange", retourVisible);
    };
  }, [lire, intervalleMs]);
}

export function FournisseurMarche({ utilisateur, majUtilisateur, deconnecter, children }: {
  utilisateur: Utilisateur;
  majUtilisateur: (u: Utilisateur) => void;
  deconnecter: () => void;
  children: React.ReactNode;
}) {
  const [inst, setInst] = useState<Instantane | null>(null);
  const [actifs, setActifs] = useState<Actif[]>([]);
  const [pf, setPf] = useState<Portefeuille | null>(null);
  const [ordres, setOrdres] = useState<Ordre[]>([]);
  const [execs, setExecs] = useState<Execution[]>([]);
  const [regles, setRegles] = useState<Regle[]>([]);
  const [erreurInstantane, setErreurInstantane] = useState<string | null>(null);
  const [erreurCompte, setErreurCompte] = useState<string | null>(null);
  const [derniereReussiteMarche, setDerniereReussiteMarche] = useState<string | null>(null);
  const [derniereReussiteCompte, setDerniereReussiteCompte] = useState<string | null>(null);
  const erreurReseau = [erreurInstantane, erreurCompte].filter(Boolean).join(" · ") || null;
  const [mode, setModeEtat] = useState<Mode>(utilisateur.role === "apprenant" ? "apprenant" : "trader");
  const instantaneEnCours = useRef(false);
  const compteEnCours = useRef(false);

  useEffect(() => {
    const m = localStorage.getItem(CLE_MODE);
    if (m === "apprenant" || m === "trader") setModeEtat(m);
  }, []);
  const setMode = (m: Mode) => { setModeEtat(m); localStorage.setItem(CLE_MODE, m); };

  const lireInstantane = useCallback(async () => {
    if (instantaneEnCours.current) return;
    instantaneEnCours.current = true;
    try {
      setInst(await api<Instantane>("/api/v1/marche/instantane"));
      setErreurInstantane(null);
      setDerniereReussiteMarche(new Date().toISOString());
    } catch (e) {
      setErreurInstantane(e instanceof ErreurApi ? e.message : "Connexion au serveur impossible.");
    } finally {
      instantaneEnCours.current = false;
    }
  }, []);

  const lireLent = useCallback(async () => {
    if (compteEnCours.current) return;
    compteEnCours.current = true;
    try {
      const [p, o, e, r] = await Promise.all([
        api<Portefeuille>("/api/v1/portefeuille"), api<Ordre[]>("/api/v1/ordres"), api<Execution[]>("/api/v1/executions"),
        api<Regle[]>("/api/v1/regles"),
      ]);
      setPf(p); setOrdres(o); setExecs(e); setRegles(r);
      setErreurCompte(null);
      setDerniereReussiteCompte(new Date().toISOString());
    } catch (e) {
      setErreurCompte(e instanceof ErreurApi ? e.message : "Lecture du portefeuille impossible.");
    } finally {
      compteEnCours.current = false;
    }
  }, []);

  const rafraichir = useCallback(async () => { await Promise.all([lireInstantane(), lireLent()]); }, [lireInstantane, lireLent]);

  useEffect(() => { api<Actif[]>("/api/v1/actifs").then(setActifs).catch(() => undefined); }, []);
  useLecturePeriodique(lireInstantane, 1500);
  useLecturePeriodique(lireLent, 2500);

  const valeur = useMemo<ValeurContexte>(() => {
    const action = async (f: () => Promise<unknown>) => { await f(); await rafraichir(); };
    return {
      utilisateur, majUtilisateur, deconnecter, inst, actifs, pf, ordres, execs, regles, erreurReseau,
      derniereReussiteMarche, derniereReussiteCompte, mode, setMode, rafraichir,
      poserRegle: async (corps) => {
        const r = await api<Regle>("/api/v1/regles", { methode: "PUT", corps });
        await rafraichir();
        return r;
      },
      supprimerRegle: (id) => action(() => api(`/api/v1/regles/${id}`, { methode: "DELETE" })),
      aller: (iso) => action(() => api("/api/v1/horloge/aller-a", { methode: "POST", corps: { instant: iso } })),
      recommencer: (iso) => action(() => api("/api/v1/horloge/aller-a", { methode: "POST", corps: { instant: iso, recommencer: true } })),
      basculerPause: () => action(() => api(inst?.horloge.en_pause ? "/api/v1/horloge/reprendre" : "/api/v1/horloge/pause", { methode: "POST" })),
      changerFacteur: (facteur) => action(() => api("/api/v1/horloge/facteur", { methode: "POST", corps: { facteur } })),
      activerDirect: () => action(() => api("/api/v1/direct/activer", { methode: "POST" })),
      quitterDirect: () => action(() => api("/api/v1/direct/quitter", { methode: "POST" })),
      reinitialiser: () => action(() => api("/api/v1/bac/reinitialiser", { methode: "POST" })),
      envoyer: async (corps) => {
        const o = await api<Ordre>("/api/v1/ordres", { methode: "POST", corps });
        await rafraichir();
        return o;
      },
      annuler: (id) => action(() => api(`/api/v1/ordres/${id}`, { methode: "DELETE" }).catch(() => undefined)),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [utilisateur, inst, actifs, pf, ordres, execs, regles, erreurReseau, derniereReussiteMarche, derniereReussiteCompte, mode, rafraichir]);

  return <Ctx.Provider value={valeur}>{children}</Ctx.Provider>;
}
