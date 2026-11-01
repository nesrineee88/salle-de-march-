"use client";

import { pct } from "@/lib/format";
import type { PartRepartition } from "@/lib/types";

interface Props {
  parts: PartRepartition[];
  /** Au-delà de ce nombre de lignes, le reste est regroupé dans « Autres ». */
  max?: number;
  titre: string;
}

/** Barres horizontales classées (une seule teinte) : la lecture exacte passe par la valeur écrite au bout de chaque barre. */
export default function Barres({ parts, max = 8, titre }: Props) {
  if (parts.length === 0) return <p className="vide">Rien à afficher pour l&apos;instant.</p>;
  const tri = [...parts].sort((a, b) => b.part - a.part);
  let lignes = tri;
  if (tri.length > max) {
    const reste = tri.slice(max - 1).reduce((s, p) => s + p.part, 0);
    lignes = [...tri.slice(0, max - 1), { libelle: "Autres", part: reste }];
  }
  const plafond = Math.max(...lignes.map((l) => l.part), 0.0001);
  return (
    <ul className="barres" aria-label={titre}>
      {lignes.map((l) => (
        <li key={l.libelle} className="barre" title={`${l.libelle} : ${pct(l.part)}`}>
          <span className="barre-nom">{l.libelle}</span>
          <span className="barre-piste" aria-hidden="true">
            <span className={`barre-rempli ${l.libelle === "Liquidités" ? "barre-neutre" : ""}`} style={{ width: `${(l.part / plafond) * 100}%` }} />
          </span>
          <span className="barre-valeur">{pct(l.part)}</span>
        </li>
      ))}
    </ul>
  );
}
