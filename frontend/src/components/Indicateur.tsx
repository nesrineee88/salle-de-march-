"use client";

import { useMarche } from "./Contexte";

interface Props {
  libelle: string;
  valeur: string;
  ton?: "gain" | "perte";
  detail?: string;
  /** Phrase simple affichée en mode Apprenant. */
  explication?: string;
  grand?: boolean;
}

export default function Indicateur({ libelle, valeur, ton, detail, explication, grand }: Props) {
  const { mode } = useMarche();
  return (
    <div className={`indicateur ${grand ? "indicateur-grand" : ""}`}>
      <p className="indicateur-libelle">{libelle}</p>
      <p className={`indicateur-valeur ${ton ?? ""}`}>{valeur}</p>
      {detail && <p className="indicateur-detail">{detail}</p>}
      {explication && mode === "apprenant" && <p className="indicateur-aide">{explication}</p>}
    </div>
  );
}
