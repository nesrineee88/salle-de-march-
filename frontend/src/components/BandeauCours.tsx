"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { ouvrirActif, symboleCourt, variationCotation } from "@/lib/actif";
import { dateLongue, prix, variation } from "@/lib/format";
import { useSuivis } from "@/lib/suivis";
import type { Actif, Classe, CotationLigne } from "@/lib/types";
import { useMarche } from "./Contexte";

type Filtre = "tout" | Classe | "suivis";

const FILTRES: { cle: Filtre; nom: string }[] = [
  { cle: "tout", nom: "Tout" },
  { cle: "action", nom: "Actions" },
  { cle: "crypto", nom: "Crypto" },
  { cle: "matiere", nom: "Matières" },
  { cle: "indice", nom: "Indices" },
  { cle: "suivis", nom: "Suivis" },
];

interface Ligne { actif: Actif; cotation: CotationLigne; v: number | null }

/** Une cellule du bandeau. Elle clignote brièvement quand le prix change : bleu s'il monte, orange s'il baisse. */
function Cellule({ ligne, copie }: { ligne: Ligne; copie: boolean }) {
  const router = useRouter();
  const { actif, cotation, v } = ligne;
  const precedent = useRef(cotation.prix);
  const [flash, setFlash] = useState<"" | "hausse" | "baisse">("");
  useEffect(() => {
    if (cotation.prix === precedent.current) return;
    setFlash(cotation.prix > precedent.current ? "hausse" : "baisse");
    precedent.current = cotation.prix;
    const t = setTimeout(() => setFlash(""), 900);
    return () => clearTimeout(t);
  }, [cotation.prix]);
  const sens = v === null ? "" : v > 0 ? "gain" : v < 0 ? "perte" : "";
  return (
    <button
      type="button"
      className={`cours ${flash ? `cours-${flash}` : ""}`}
      onClick={() => ouvrirActif(router, actif)}
      tabIndex={copie ? -1 : 0}
      title={`${actif.nom} : ${prix(cotation.prix)} ${actif.devise}`}
      aria-label={`${actif.nom}, ${prix(cotation.prix)} ${actif.devise}, ${variation(v)}`}
    >
      <span className="cours-symbole">{symboleCourt(actif.symbole)}</span>
      <span className="cours-prix">{prix(cotation.prix)}</span>
      <span className={`cours-var ${sens}`}>
        {v !== null && v !== 0 && <span aria-hidden="true">{v > 0 ? "▲" : "▼"} </span>}
        {variation(v)}
      </span>
    </button>
  );
}

/**
 * Bandeau de cours dynamique : tous les actifs du simulateur, mis à jour avec l'horloge simulée
 * (ou avec les prix récents en mode Direct). Il défile, s'arrête au survol, au clavier et sur demande,
 * et il ne bouge pas du tout si le système demande de réduire les animations.
 */
export default function BandeauCours() {
  const { inst, actifs, utilisateur } = useMarche();
  const { suivis } = useSuivis(utilisateur.email);
  const [filtre, setFiltre] = useState<Filtre>("tout");
  const [pause, setPause] = useState(false);

  const lignes = useMemo<Ligne[]>(() => {
    if (!inst) return [];
    const parSymbole = new Map(actifs.map((a) => [a.symbole, a]));
    return inst.cotations.flatMap((c) => {
      const a = parSymbole.get(c.symbole);
      if (!a) return [];
      if (filtre === "suivis" ? !suivis.includes(a.symbole) : filtre !== "tout" && a.classe !== filtre) return [];
      return [{ actif: a, cotation: c, v: variationCotation(c) }];
    });
  }, [inst, actifs, filtre, suivis]);

  if (!inst) return null;
  const duree = Math.max(40, lignes.length * 2.4);
  const origine = inst.direct ? (inst.direct_flux?.demo ? "Direct, flux de démonstration" : "Direct") : `Cours au ${dateLongue(inst.instant)}`;

  return (
    <section className="bandeau-cours" aria-label="Cours des actifs">
      <div className="bandeau-cours-tete">
        <p className="bandeau-cours-origine" title="Les cours suivent l'horloge de la simulation, pas la date du jour.">{origine}</p>
        <div className="bandeau-cours-filtres" role="group" aria-label="Filtrer le bandeau">
          {FILTRES.map((f) => (
            <button key={f.cle} type="button" className="puce" aria-pressed={filtre === f.cle} onClick={() => setFiltre(f.cle)}>{f.nom}</button>
          ))}
        </div>
        <button type="button" className="btn-icone" onClick={() => setPause(!pause)} aria-pressed={pause}
          aria-label={pause ? "Relancer le défilement du bandeau" : "Mettre le bandeau en pause"} title={pause ? "Relancer" : "Pause"}>
          {pause ? <Play size={16} aria-hidden="true" /> : <Pause size={16} aria-hidden="true" />}
        </button>
      </div>
      {lignes.length === 0 ? (
        <p className="bandeau-cours-vide">{filtre === "suivis" ? "Aucun actif suivi pour l'instant. Ouvrez « Mes suivis » (étoile en haut) pour en ajouter." : "Aucun cours à cette date."}</p>
      ) : (
        <div className="bandeau-cours-piste" data-pause={pause} style={{ ["--duree" as string]: `${duree}s` }}>
          <div className="bandeau-cours-defile">
            <div className="bandeau-cours-liste">
              {lignes.map((l) => <Cellule key={l.actif.symbole} ligne={l} copie={false} />)}
            </div>
            <div className="bandeau-cours-liste" aria-hidden="true">
              {lignes.map((l) => <Cellule key={l.actif.symbole} ligne={l} copie />)}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
