"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import IconeSeance from "../ui/IconeSeance";
import { useXAI } from "./ContexteXAI";
import { Fil, Saisie, Suggestions } from "./Conversation";

/** Dans la pellicule, donc sur toutes les pages. Il disparaît avec elle pendant la projection du jeu. */
export function BoutonXAI() {
  const { page, ouvert, basculer } = useXAI();
  if (page === "xai") return null;
  return (
    <button type="button" id="xai-ouvrir" className="xai-ouvrir" onClick={basculer} aria-expanded={ouvert} aria-label="Demander à XAI">
      <IconeSeance nom="xai" taille={16} /><span>Demander à XAI</span>
    </button>
  );
}

function Panneau() {
  const { fermer } = useXAI();
  const panneau = useRef<HTMLElement>(null);
  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || document.querySelector("dialog[open]")) return;
      const dedans = panneau.current?.contains(document.activeElement);
      fermer();
      if (dedans) document.getElementById("xai-ouvrir")?.focus();
    };
    document.addEventListener("keydown", touche);
    return () => document.removeEventListener("keydown", touche);
  }, [fermer]);

  // sur téléphone le panneau couvre presque tout : il se ferme quand on suit un lien
  const naviguer = () => { if (window.innerWidth <= 820) fermer(); };
  return (
    <aside ref={panneau} className="xai-panneau" aria-label="Assistant XAI">
      <header>
        <h2>Assistant XAI</h2>
        <button type="button" className="xai-fermer" onClick={fermer} aria-label="Fermer l’assistant"><X size={18} aria-hidden="true" /></button>
      </header>
      <Fil avecPreuve naviguer={naviguer} />
      <Suggestions />
      <Saisie focus />
    </aside>
  );
}

export function PanneauXAI() {
  const { ouvert, page } = useXAI();
  return ouvert && page !== "xai" ? <Panneau /> : null;
}
