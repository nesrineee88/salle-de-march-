"use client";

import { useMemo, useState } from "react";
import { NOMS_CLASSES, prix, variation } from "@/lib/format";
import type { Actif, Classe, CotationLigne } from "@/lib/types";

interface Props {
  actifs: Actif[];
  cotations: CotationLigne[];
  classes: Classe[];
  selection: string | null;
  onSelect: (s: string) => void;
  titre: string;
}

export default function Marches({ actifs, cotations, classes, selection, onSelect, titre }: Props) {
  const [recherche, setRecherche] = useState("");
  const parSymbole = useMemo(() => new Map(cotations.map((c) => [c.symbole, c])), [cotations]);

  const groupes = useMemo(() => {
    const q = recherche.trim().toLowerCase();
    return classes.map((classe) => ({
      classe,
      lignes: actifs.filter(
        (a) => a.classe === classe && parSymbole.has(a.symbole) &&
          (!q || a.symbole.toLowerCase().includes(q) || a.nom.toLowerCase().includes(q)),
      ),
    })).filter((g) => g.lignes.length > 0);
  }, [actifs, parSymbole, recherche, classes]);

  return (
    <nav className="marches" aria-label={titre}>
      <div className="marches-recherche">
        <label htmlFor="recherche" className="sr-only">Rechercher un actif</label>
        <input id="recherche" type="search" placeholder="Rechercher un actif" value={recherche} onChange={(e) => setRecherche(e.target.value)} />
      </div>
      {groupes.length === 0 && <p className="vide">Aucun actif ne correspond à votre recherche.</p>}
      {groupes.map((g) => (
        <section key={g.classe}>
          <h2 className="groupe">{classes.length > 1 ? NOMS_CLASSES[g.classe] : `${titre} · ${g.lignes.length}`}</h2>
          <ul className="liste-actifs">
            {g.lignes.map((a) => {
              const c = parSymbole.get(a.symbole)!;
              const base = c.reference ?? c.derniere_cloture;
              const v = base ? (c.prix - base) / Math.abs(base) : null;
              const classeV = v === null ? "" : v > 0 ? "gain" : v < 0 ? "perte" : "";
              return (
                <li key={a.symbole}>
                  <button className="ligne-actif" aria-current={selection === a.symbole} onClick={() => onSelect(a.symbole)}>
                    <span className="ligne-nom">
                      <strong>{a.symbole}</strong>
                      <small>{a.nom}</small>
                    </span>
                    <span className="ligne-prix">
                      <span className={c.statut === "ferme" ? "discret" : ""}>{prix(c.prix)}</span>
                      <small className={classeV}>
                        {v !== null && (v > 0 ? "▲ " : v < 0 ? "▼ " : "")}
                        {variation(v)}
                      </small>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </nav>
  );
}
