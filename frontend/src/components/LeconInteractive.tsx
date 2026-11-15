"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Check, X } from "lucide-react";
import { api, ErreurApi } from "@/lib/api";
import { pct } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import type { CorrectionLecon, DetailLecon } from "@/lib/types";

type Etape =
  | { type: "carte"; titre: string; texte: string }
  | { type: "action" }
  | { type: "question"; index: number };

/** Première phrase en gros (l'idée), le reste en dessous : on lit l'essentiel d'un coup d'œil. */
function decouper(texte: string): [string, string] {
  const m = /^(.+?[.!?])(\s+|$)/s.exec(texte);
  return m ? [m[1], texte.slice(m[0].length)] : [texte, ""];
}

function Confettis() {
  return <div className="confettis" aria-hidden="true">{Array.from({ length: 24 }, (_, i) => <i key={i} style={{ ["--i" as string]: i }} />)}</div>;
}

/** Une leçon jouée étape par étape : cartes à lire, exercices, puis une question par écran. Le quiz est corrigé par le serveur. */
export default function LeconInteractive({ id, retour }: { id: string; retour: () => void }) {
  const { donnees: d, erreur } = useLecture<DetailLecon>(`/api/v1/formation/lecons/${id}`, 3_600_000);
  const [i, setI] = useState(0);
  const [choix, setChoix] = useState<Record<number, number>>({});
  const [corr, setCorr] = useState<CorrectionLecon | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  const etapes = useMemo<Etape[]>(() => {
    if (!d) return [];
    return [
      ...d.sections.map((s): Etape => ({ type: "carte", titre: s.titre, texte: s.texte })),
      ...(d.exercices.length > 0 ? [{ type: "action" } as Etape] : []),
      ...d.questions.map((q): Etape => ({ type: "question", index: q.index })),
    ];
  }, [d]);

  const dernier = etapes.length - 1;
  const etape = etapes[i];
  useEffect(() => {
    if (corr) return;
    const touche = (e: KeyboardEvent) => {
      const cible = e.target as HTMLElement | null;
      if (cible && (cible.tagName === "INPUT" || cible.tagName === "TEXTAREA")) return;
      if (e.key === "ArrowRight" && etape && etape.type !== "question") setI((v) => Math.min(v + 1, dernier));
      if (e.key === "ArrowLeft") setI((v) => Math.max(v - 1, 0));
    };
    document.addEventListener("keydown", touche);
    return () => document.removeEventListener("keydown", touche);
  }, [etape, dernier, corr]);

  async function envoyer() {
    if (!d) return;
    setErr(null); setEnvoi(true);
    try {
      const reponses = d.questions.map((q) => (choix[q.index] === undefined ? null : choix[q.index]));
      setCorr(await api<CorrectionLecon>(`/api/v1/formation/lecons/${id}/repondre`, { methode: "POST", corps: { reponses } }));
    } catch (exc) { setErr(exc instanceof ErreurApi ? exc.message : "Envoi impossible."); }
    finally { setEnvoi(false); }
  }

  if (erreur) return <p className="erreur" role="alert">{erreur}</p>;
  if (!d || !etape) return <p className="vide">Chargement…</p>;

  // ---------- résultat
  if (corr) {
    const reste = d.questions.length - corr.bonnes;
    return (
      <section className="panneau resultat-lecon" aria-live="polite">
        {corr.reussie && <Confettis />}
        <div className="anneau" style={{ ["--p" as string]: `${Math.round(corr.score * 100)}%` }} data-reussi={corr.reussie}><strong>{Math.round(corr.score * 100)} %</strong></div>
        <h2>{corr.reussie ? "Leçon réussie" : "Pas encore, mais vous y êtes presque"}</h2>
        <p className="discret">{corr.bonnes} bonne(s) réponse(s) sur {corr.total}. Seuil de réussite : {pct(corr.seuil_reussite, 0)}.{reste > 0 && !corr.reussie ? " Relisez les explications ci-dessous puis réessayez." : ""}</p>
        <ol className="corrections">
          {d.questions.map((q) => {
            const c = corr.corrections[q.index];
            return (
              <li key={q.index} data-juste={c.juste}>
                <p><span className="correction-icone" aria-hidden="true">{c.juste ? <Check size={16} /> : <X size={16} />}</span><strong>{q.enonce}</strong></p>
                <p className="aide">Bonne réponse : {q.choix[c.bonne_reponse]}. {c.explication}</p>
              </li>
            );
          })}
        </ol>
        <div className="direct-actions">
          <button type="button" className="btn btn-principal" style={{ width: "auto", marginTop: 0 }} onClick={() => { setCorr(null); setChoix({}); setI(0); }}>Recommencer la leçon</button>
          <button type="button" className="btn" onClick={retour}>Retour au parcours</button>
        </div>
      </section>
    );
  }

  const q = etape.type === "question" ? d.questions.find((x) => x.index === etape.index) : undefined;
  const reponse = q ? choix[q.index] : undefined;
  const dernierEcran = i === dernier;
  const [idee, suite] = etape.type === "carte" ? decouper(etape.texte) : ["", ""];

  return (
    <section className="lecon-lecteur" aria-label={d.titre}>
      <div className="lecon-haut">
        <button type="button" className="btn-icone" onClick={retour} aria-label="Quitter la leçon"><X size={18} aria-hidden="true" /></button>
        <div className="lecon-progres" role="progressbar" aria-valuemin={0} aria-valuemax={etapes.length} aria-valuenow={i + 1} aria-label={`Étape ${i + 1} sur ${etapes.length}`}>
          <i style={{ width: `${((i + 1) / etapes.length) * 100}%` }} />
        </div>
        <span className="discret">{i + 1} / {etapes.length}</span>
      </div>

      <article className="panneau lecon-ecran" key={i}>
        {etape.type === "carte" && (
          <>
            <p className="lecon-surtitre">{d.titre}</p>
            <h2>{etape.titre}</h2>
            <p className="lecon-idee">{idee}</p>
            {suite && <p className="lecon-suite">{suite}</p>}
          </>
        )}
        {etape.type === "action" && (
          <>
            <p className="lecon-surtitre">À vous de jouer</p>
            <h2>Pratiquez dans le simulateur</h2>
            <ul className="lecon-actions">
              {d.exercices.map((x) => <li key={x.texte}><span>{x.texte}</span><Link className="btn" href={x.lien}>{x.libelle} <ArrowRight size={14} aria-hidden="true" /></Link></li>)}
            </ul>
            <p className="aide">Vous pouvez y aller maintenant ou continuer vers le quiz : ces exercices ne sont pas notés.</p>
          </>
        )}
        {q && (
          <fieldset className="lecon-question">
            <legend><span className="lecon-surtitre">Question {q.index + 1} sur {d.questions.length}</span><span className="lecon-enonce">{q.enonce}</span></legend>
            <div className="lecon-choix">
              {q.choix.map((txt, k) => (
                <label key={k} className="lecon-option" data-choisi={reponse === k}>
                  <input type="radio" name={`q${q.index}`} checked={reponse === k} onChange={() => setChoix({ ...choix, [q.index]: k })} />
                  <span className="lecon-lettre" aria-hidden="true">{"ABCD"[k]}</span>{txt}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        {err && <p className="erreur" role="alert">{err}</p>}
      </article>

      <div className="lecon-nav">
        <button type="button" className="btn btn-icone-texte" onClick={() => setI(i - 1)} disabled={i === 0}><ArrowLeft size={16} aria-hidden="true" /> Précédent</button>
        {dernierEcran ? (
          <button type="button" className="btn btn-principal btn-icone-texte" style={{ width: "auto", marginTop: 0 }} onClick={() => void envoyer()} disabled={envoi || (q ? reponse === undefined : false)}>
            {envoi ? "Correction…" : "Envoyer et corriger"} <Check size={16} aria-hidden="true" />
          </button>
        ) : (
          <button type="button" className="btn btn-principal btn-icone-texte" style={{ width: "auto", marginTop: 0 }} onClick={() => setI(i + 1)} disabled={q ? reponse === undefined : false}>
            Suivant <ArrowRight size={16} aria-hidden="true" />
          </button>
        )}
      </div>
    </section>
  );
}
