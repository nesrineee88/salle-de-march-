"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Plus, Star, X } from "lucide-react";
import { ouvrirActif, symboleCourt, variationCotation } from "@/lib/actif";
import { prix, variation } from "@/lib/format";
import { useSuivis } from "@/lib/suivis";
import { useLecture } from "@/lib/hooks";
import type { Actif, Actualite, CotationLigne } from "@/lib/types";
import { useMarche } from "./Contexte";

interface Ligne { actif: Actif; cotation: CotationLigne; v: number | null }

function LigneCours({ ligne, action }: { ligne: Ligne; action?: React.ReactNode }) {
  const router = useRouter();
  const { actif, cotation, v } = ligne;
  const sens = v !== null && v > 0 ? "gain" : v !== null && v < 0 ? "perte" : "";
  return (
    <li className="suivi">
      <button type="button" className="suivi-corps" onClick={() => ouvrirActif(router, actif)} title={actif.nom}>
        <span className="suivi-nom"><strong>{symboleCourt(actif.symbole)}</strong><small className="discret">{actif.nom}</small></span>
        <span className="suivi-cours">{prix(cotation.prix)}<small className={sens}>{v !== null && v !== 0 ? (v > 0 ? "▲ " : "▼ ") : ""}{variation(v)}</small></span>
      </button>
      {action}
    </li>
  );
}

/** Tiroir « Mes suivis » : la liste personnelle de l'utilisateur et les plus fortes variations du jour simulé. */
export default function PanneauSuivis({ fermer }: { fermer: () => void }) {
  const { inst, actifs, utilisateur } = useMarche();
  const { suivis, basculer } = useSuivis(utilisateur.email);
  const [ajout, setAjout] = useState("");

  const lignes = useMemo<Ligne[]>(() => {
    const parSymbole = new Map(actifs.map((a) => [a.symbole, a]));
    return (inst?.cotations ?? []).flatMap((c) => {
      const a = parSymbole.get(c.symbole);
      return a ? [{ actif: a, cotation: c, v: variationCotation(c) }] : [];
    });
  }, [inst, actifs]);

  const { donnees: fil } = useLecture<{ actualites: Actualite[] }>("/api/v1/actualites?limite=60", 10000);
  const actusSuivies = (fil?.actualites ?? []).filter((a) => a.symboles.some((x) => suivis.includes(x))).slice(0, 5);

  const suivies = suivis.flatMap((s) => lignes.filter((l) => l.actif.symbole === s));
  const avecVar = lignes.filter((l) => l.v !== null && l.actif.classe !== "indice");
  const hausses = [...avecVar].sort((a, b) => (b.v ?? 0) - (a.v ?? 0)).slice(0, 3);
  const baisses = [...avecVar].sort((a, b) => (a.v ?? 0) - (b.v ?? 0)).slice(0, 3);

  const t = ajout.trim().toLowerCase();
  const propositions = t
    ? lignes.filter((l) => !suivis.includes(l.actif.symbole) && (l.actif.symbole.toLowerCase().includes(t) || l.actif.nom.toLowerCase().includes(t))).slice(0, 5)
    : [];

  return (
    <aside className="suivis" aria-label="Mes suivis">
      <header className="suivis-tete">
        <h2><Star size={16} aria-hidden="true" /> Mes suivis</h2>
        <button type="button" className="btn-icone" onClick={fermer} aria-label="Fermer le panneau"><X size={16} aria-hidden="true" /></button>
      </header>

      <div className="suivis-ajout">
        <label htmlFor="suivis-ajout" className="sr-only">Ajouter un actif à suivre</label>
        <input id="suivis-ajout" type="search" placeholder="Ajouter un actif" value={ajout} onChange={(e) => setAjout(e.target.value)} />
        {propositions.length > 0 && (
          <ul className="suivis-propositions">
            {propositions.map((l) => (
              <li key={l.actif.symbole}>
                <button type="button" onClick={() => { basculer(l.actif.symbole); setAjout(""); }}>
                  <Plus size={14} aria-hidden="true" /> {l.actif.symbole} <small className="discret">{l.actif.nom}</small>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {suivies.length === 0 ? (
        <div className="suivis-vide">
          <p><strong>Suivez votre premier actif</strong></p>
          <p className="discret">Cherchez-le ci-dessus, ou cliquez sur l&apos;étoile de sa page. Il apparaîtra ici et dans le filtre « Suivis » du bandeau.</p>
        </div>
      ) : (
        <ul className="suivis-liste">
          {suivies.map((l) => (
            <LigneCours key={l.actif.symbole} ligne={l} action={
              <button type="button" className="btn-icone" onClick={() => basculer(l.actif.symbole)} aria-label={`Ne plus suivre ${l.actif.symbole}`}><X size={14} aria-hidden="true" /></button>
            } />
          ))}
        </ul>
      )}

      <h3 className="suivis-sous-titre">Actualités</h3>
      {suivis.length === 0 ? <p className="aide">Le fil des actifs que vous suivez apparaîtra ici.</p>
        : actusSuivies.length === 0 ? <p className="aide">Aucune actualité sur vos actifs à cette date simulée.</p>
        : <ul className="suivis-actus">{actusSuivies.map((a) => (
            <li key={a.id}><small className="discret">{a.date} · {a.symboles.filter((x) => suivis.includes(x)).map(symboleCourt).join(", ")}</small><span>{a.titre}</span></li>
          ))}</ul>}

      {hausses.length > 0 && (
        <>
          <h3 className="suivis-sous-titre">Plus fortes hausses</h3>
          <ul className="suivis-liste">{hausses.map((l) => <LigneCours key={l.actif.symbole} ligne={l} />)}</ul>
          <h3 className="suivis-sous-titre">Plus fortes baisses</h3>
          <ul className="suivis-liste">{baisses.map((l) => <LigneCours key={l.actif.symbole} ligne={l} />)}</ul>
          <p className="aide">Variation depuis la dernière clôture, à la date de la simulation.</p>
        </>
      )}
    </aside>
  );
}
