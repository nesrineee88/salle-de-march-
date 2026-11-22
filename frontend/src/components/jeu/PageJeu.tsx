"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ErreurApi, api } from "@/lib/api";
import { useMarche } from "../Contexte";
import Accueil, { type Demarrage } from "./Accueil";
import Generique from "./Generique";
import Projection from "./Projection";
import type { AccueilJeu, Partie } from "./types";
import { usePartie } from "./usePartie";

const CLE_PARTIE = "sdm.jeu.partie";
const CLE_SON = "sdm.jeu.son";

function garder(cle: string, valeur: string | null) {
  try {
    if (valeur === null) sessionStorage.removeItem(cle);
    else sessionStorage.setItem(cle, valeur);
  } catch {
    /* stockage indisponible : la partie reste reprenable depuis l'accueil */
  }
}
function lire(cle: string): string | null {
  try { return sessionStorage.getItem(cle); } catch { return null; }
}

function Scene({ initiale, son, basculerSon, quitter, rejouer, pleinEcran }: {
  initiale: Partie;
  son: boolean;
  basculerSon: () => void;
  quitter: () => void;
  rejouer: (d: Demarrage) => void;
  pleinEcran: () => void;
}) {
  const jeu = usePartie(initiale);
  const { partie } = jeu;
  const projete = partie.statut === "en_cours";

  useEffect(() => {
    if (!projete) return;
    document.body.dataset.jeu = "projection";
    return () => { delete document.body.dataset.jeu; };
  }, [projete]);

  if (projete) return <Projection jeu={jeu} son={son} basculerSon={basculerSon} quitter={quitter} pleinEcran={pleinEcran} />;
  if (partie.generique) {
    return (
      <Generique jeu={jeu} accueil={quitter}
        rejouer={() => rejouer({ mode: partie.mode, film: partie.film, difficulte: partie.difficulte.cle, plan: partie.plan })} />
    );
  }
  return (
    <div className="obscure-vide">
      <p>Cette projection a été abandonnée, sans doute depuis un autre onglet.</p>
      <button type="button" className="obscure-bouton obscure-bouton-fort" onClick={quitter}>Retour à l’accueil du jeu</button>
    </div>
  );
}

export default function PageJeu() {
  const { utilisateur } = useMarche();
  const cle = `${CLE_PARTIE}.${utilisateur.id}`;
  const racine = useRef<HTMLDivElement>(null);
  const [accueil, setAccueil] = useState<AccueilJeu | null>(null);
  const [partie, setPartie] = useState<Partie | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [son, setSon] = useState(false);

  const signaler = useCallback((e: unknown) => {
    if (e instanceof ErreurApi && e.statut === 404) setErreur("Le serveur Python ne connaît pas encore le jeu : redémarrez-le, puis rechargez cette page.");
    else setErreur(e instanceof Error ? e.message : "Action impossible.");
  }, []);

  const lireAccueil = useCallback(async () => {
    try {
      setAccueil(await api<AccueilJeu>("/api/v1/jeu/accueil"));
      setErreur(null);
    } catch (e) {
      signaler(e);
    }
  }, [signaler]);

  // au rechargement on retombe dans sa projection
  useEffect(() => {
    let actif = true;
    setSon(lire(CLE_SON) === "1");
    const id = lire(cle);
    if (!id) { void lireAccueil(); return; }
    api<Partie>(`/api/v1/jeu/parties/${id}`)
      .then((p) => {
        if (!actif) return;
        if (p.statut === "abandonnee") { garder(cle, null); void lireAccueil(); } else setPartie(p);
      })
      .catch(() => {
        if (!actif) return;
        garder(cle, null);
        void lireAccueil();
      });
    return () => { actif = false; };
  }, [cle, lireAccueil]);

  function entrer(p: Partie) {
    garder(cle, p.id);
    setErreur(null);
    setPartie(p);
    racine.current?.scrollTo?.(0, 0);
  }
  async function demarrer(d: Demarrage) {
    setEnvoi(true);
    setErreur(null);
    try {
      const corps = { mode: d.mode, difficulte: d.difficulte, ...(d.film ? { film: d.film } : {}), ...(d.plan ? { plan: d.plan } : {}) };
      entrer(await api<Partie>("/api/v1/jeu/parties", { methode: "POST", corps }));
    } catch (e) {
      signaler(e);
    } finally {
      setEnvoi(false);
    }
  }
  async function reprendre(id: string) {
    try { entrer(await api<Partie>(`/api/v1/jeu/parties/${id}`)); } catch (e) { signaler(e); }
  }
  async function abandonner(id: string) {
    try {
      const p = await api<Partie>(`/api/v1/jeu/parties/${id}`);
      await api(`/api/v1/jeu/parties/${id}/abandonner`, { methode: "POST", corps: { version: p.version } });
      await lireAccueil();
    } catch (e) {
      signaler(e);
    }
  }
  function quitter() {
    garder(cle, null);
    setPartie(null);
    setAccueil(null);
    void lireAccueil();
  }
  function pleinEcran() {
    const action = document.fullscreenElement ? document.exitFullscreen() : racine.current?.requestFullscreen();
    action?.catch(() => setErreur("Le plein écran n’est pas autorisé ici."));
  }
  function basculerSon() {
    garder(CLE_SON, son ? "0" : "1");
    setSon(!son);
  }

  // la racine est commune aux trois vues : le plein écran tient de l'accueil jusqu'au générique
  return (
    <main className="obscure" ref={racine}>
      {partie ? (
        <Scene key={partie.id} initiale={partie} son={son} basculerSon={basculerSon} quitter={quitter}
          rejouer={(d) => void demarrer(d)} pleinEcran={pleinEcran} />
      ) : accueil ? (
        <Accueil accueil={accueil} envoi={envoi} demarrer={(d) => void demarrer(d)} reprendre={(id) => void reprendre(id)}
          abandonner={(id) => void abandonner(id)} pleinEcran={pleinEcran} />
      ) : !erreur && <p className="chargement" role="status">La salle s’allume…</p>}
      {erreur && <p className="obscure-erreur" role="alert">{erreur}</p>}
    </main>
  );
}
