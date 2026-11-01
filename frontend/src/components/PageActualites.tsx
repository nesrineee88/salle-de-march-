"use client";

import { useState } from "react";
import { nombre, pct, pctSigne } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import type { Actualite, EtudeSentiment } from "@/lib/types";
import { useMarche } from "./Contexte";

const JOUR = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const jourFr = (iso: string) => JOUR.format(Date.parse(`${iso}T00:00:00Z`));
const LIBELLE_SOURCE: Record<string, string> = { historique: "Repère historique", fictif: "Actualité fictive", scenario: "Actualité fictive (crise)", import: "Importée" };

function ton(v: number | null): "gain" | "perte" | undefined { return v === null ? undefined : v > 0 ? "gain" : v < 0 ? "perte" : undefined; }
function rendement(v: number | null): string {
  if (v === null) return "à venir";
  return `${v > 0 ? "▲ " : v < 0 ? "▼ " : ""}${pctSigne(v, 1)}`;
}

function Sentiment({ a }: { a: Actualite }) {
  const s = a.sentiment;
  const libelle = s.etiquette === "positif" ? "▲ Ton positif" : s.etiquette === "negatif" ? "▼ Ton négatif" : "Ton neutre";
  const mots = [...s.mots_positifs, ...s.mots_negatifs];
  return (
    <span className={`actu-sentiment ${s.etiquette === "positif" ? "gain" : s.etiquette === "negatif" ? "perte" : "discret"}`}
      title={mots.length ? `Mots repérés : ${mots.join(", ")}` : "Aucun mot du lexique repéré"}>
      {libelle} ({nombre(s.score, 2)})
    </span>
  );
}

export default function PageActualites() {
  const { actifs, mode } = useMarche();
  const [symbole, setSymbole] = useState("");
  const chemin = `/api/v1/actualites${symbole ? `?symbole=${encodeURIComponent(symbole)}` : ""}`;
  const { donnees, erreur } = useLecture<{ instant: string; actualites: Actualite[] }>(chemin, 8000);
  const { donnees: etude } = useLecture<EtudeSentiment>("/api/v1/actualites/etude", 15000);
  const liste = donnees?.actualites ?? [];

  return (
    <main className="page">
      <header className="page-tete">
        <h1>Actualités et sentiment</h1>
        <p className="aide">
          Les actualités parues jusqu&apos;à votre date simulée, avec le ton du texte (analysé par un lexique de mots) et ce que le marché a fait ensuite.
          Les mouvements affichés ne portent que sur des séances déjà terminées : « à venir » signifie que la séance n&apos;a pas encore eu lieu pour vous.
        </p>
      </header>

      <div className="champ actu-filtre">
        <label htmlFor="actu-actif">Filtrer par actif</label>
        <select id="actu-actif" value={symbole} onChange={(e) => setSymbole(e.target.value)}>
          <option value="">Toutes les actualités</option>
          {actifs.filter((a) => a.tradable).map((a) => <option key={a.symbole} value={a.symbole}>{a.symbole} · {a.nom}</option>)}
        </select>
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}

      <div className="grille-courbe">
        <section aria-label="Fil d'actualités" className="actu-fil">
          {liste.length === 0 && <p className="vide panneau">Aucune actualité parue à votre date simulée. Faites avancer le temps, ou choisissez une date sur la frise (les repères historiques commencent en 2018).</p>}
          {liste.map((a) => (
            <article key={a.id} className="panneau actu">
              <header className="actu-tete">
                <time dateTime={a.date} className="discret">{jourFr(a.date)}</time>
                <span className={`actu-badge actu-${a.type_source}`}>{LIBELLE_SOURCE[a.type_source] ?? a.type_source}</span>
              </header>
              <h2 className="actu-titre">{a.titre}</h2>
              {a.texte && <p>{a.texte}</p>}
              <p className="actu-pied"><Sentiment a={a} /> <span className="discret">· {a.symboles.length ? a.symboles.join(", ") : "marché en général"}</span></p>
              {a.impact && a.impact.length > 0 && (
                <div className="tableau-defile actu-impact">
                  <table className="tableau tableau-gauche">
                    <caption className="sr-only">Mouvement des cours après la parution</caption>
                    <thead><tr><th>Actif</th><th title="De la clôture précédente à la clôture du jour de parution">Le jour de parution</th><th title="De la clôture précédente à la clôture de la 5e séance">Sur 5 séances</th></tr></thead>
                    <tbody>
                      {a.impact.map((i) => (
                        <tr key={i.symbole}><td>{i.symbole}</td><td className={ton(i.rendement_1j)}>{rendement(i.rendement_1j)}</td><td className={ton(i.rendement_5j)}>{rendement(i.rendement_5j)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {a.type_source !== "import" && <p className="aide actu-note">{a.note_source}</p>}
            </article>
          ))}
        </section>

        <aside className="panneau actu-etude" aria-labelledby="titre-etude">
          <header className="panneau-tete"><h2 id="titre-etude">Le ton prédit-il le marché ?</h2></header>
          {etude ? (
            <>
              <dl className="mini-indicateurs">
                <div><dt>Actualités étudiées</dt><dd>{etude.nb_actualites}</dd></div>
                <div><dt>Ton et mouvement concordent</dt><dd>{etude.concordance === null ? "–" : pct(etude.concordance, 0)}</dd></div>
                <div><dt>Corrélation</dt><dd>{etude.correlation === null ? "–" : nombre(etude.correlation, 2)}</dd></div>
              </dl>
              <p className="aide">{etude.avertissement}</p>
              {mode === "apprenant" && (
                <p className="aide">« Concordent » : le texte est positif et le cours a monté le jour de parution (ou l&apos;inverse). Hasard pur : environ 50 %. La corrélation va de −1 à +1 ; elle n&apos;est calculée qu&apos;avec au moins 8 actualités.</p>
              )}
            </>
          ) : <p className="vide">Chargement…</p>}
        </aside>
      </div>
    </main>
  );
}
