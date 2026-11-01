"use client";

import { useState } from "react";
import { dateLongue, instantDate } from "@/lib/format";
import { REPERES } from "@/lib/reperes";

interface Props {
  fenetre: { debut: string; fin: string };
  instant: string;
  onAller: (instantIso: string) => void;
}

/** Frise de la période rejouée : on glisse pour changer de date, ou on saute à un repère historique. */
export default function Frise({ fenetre, instant, onAller }: Props) {
  const debut = Date.parse(`${fenetre.debut}T00:00:00Z`);
  const fin = Date.parse(`${fenetre.fin}T23:59:59Z`);
  const [glisse, setGlisse] = useState<number | null>(null);

  const position = (ms: number) => Math.min(1000, Math.max(0, ((ms - debut) / (fin - debut)) * 1000));
  const courant = position(instantDate(instant).getTime());
  const valeur = glisse ?? courant;
  const msDeValeur = (v: number) => debut + (v / 1000) * (fin - debut);

  function valider() {
    if (glisse === null) return;
    const iso = new Date(msDeValeur(glisse)).toISOString().slice(0, 10);
    setGlisse(null);
    onAller(`${iso}T17:00:00`);
  }

  const anneeDebut = new Date(debut).getUTCFullYear();
  const anneeFin = new Date(fin).getUTCFullYear();
  const annees = Array.from({ length: anneeFin - anneeDebut + 1 }, (_, i) => anneeDebut + i);

  return (
    <div className="frise">
      <div className="frise-reperes">
        {REPERES.map((r) => (
          <button
            key={r.date}
            type="button"
            className="frise-repere"
            style={{ left: `${position(Date.parse(`${r.date}T17:00:00Z`)) / 10}%` }}
            onClick={() => onAller(`${r.date}T17:00:00`)}
            aria-label={`Aller au repère : ${r.titre}, ${dateLongue(`${r.date}T00:00:00`)}`}
          >
            <span className="frise-bulle">
              <strong>{r.titre}</strong>
              <span>{r.explication}</span>
            </span>
          </button>
        ))}
      </div>
      <input
        className="frise-curseur"
        style={{ ["--pos" as string]: `${valeur / 10}%` }}
        type="range"
        min={0}
        max={1000}
        value={valeur}
        onChange={(e) => setGlisse(Number(e.target.value))}
        onPointerUp={valider}
        onKeyUp={valider}
        onBlur={valider}
        aria-label="Date simulée"
        aria-valuetext={dateLongue(new Date(msDeValeur(valeur)).toISOString())}
      />
      <div className="frise-annees" aria-hidden="true">
        {annees.map((a) => (
          <span key={a} style={{ left: `${position(Date.parse(`${a}-01-01T00:00:00Z`)) / 10}%` }}>{a}</span>
        ))}
      </div>
    </div>
  );
}
