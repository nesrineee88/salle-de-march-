"use client";

import { useId } from "react";
import { useMarche } from "./Contexte";

interface Props {
  libelle: string;
  valeur: string;
  ton?: "gain" | "perte";
  detail?: React.ReactNode;
  /** Phrase simple affichée en mode Apprenant. */
  explication?: string;
  grand?: boolean;
  /** Unité affichée en plus petit après la valeur (« USD »). */
  unite?: string;
  /** Bouton (i) : phrase simple en mode Apprenant, formule en mode Trader. Accessible au clavier. */
  infobulle?: { simple: string; formule: string };
  /** Visuel facultatif sous la valeur (mini-courbe). */
  children?: React.ReactNode;
}

export default function Indicateur({ libelle, valeur, ton, detail, explication, grand, unite, infobulle, children }: Props) {
  const { mode } = useMarche();
  const id = useId();
  return (
    <div className={`indicateur ${grand ? "indicateur-grand" : ""}`}>
      <p className="indicateur-libelle">
        {libelle}
        {infobulle && (
          <span className="info-carte">
            <button type="button" className="info-bouton" aria-label={`Comprendre : ${libelle}`} aria-describedby={id}>i</button>
            <span role="tooltip" id={id} className="info-bulle">{mode === "apprenant" ? infobulle.simple : infobulle.formule}</span>
          </span>
        )}
      </p>
      <p className={`indicateur-valeur ${ton ?? ""}`}>{valeur}{unite && <small className="indicateur-unite"> {unite}</small>}</p>
      {detail && <p className="indicateur-detail">{detail}</p>}
      {children}
      {explication && mode === "apprenant" && <p className="indicateur-aide">{explication}</p>}
    </div>
  );
}
