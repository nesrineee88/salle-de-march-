"use client";

import { pctSigne, prix } from "@/lib/format";
import { OUTILS, UNITES, type Outil } from "@/lib/technique";
import type { ReponseBougies, Unite } from "@/lib/types";
import type { Mode } from "./Contexte";
import type { ModeTrace } from "./Graphique";

interface Props {
  unite: Unite;
  onUnite: (u: Unite) => void;
  outils: Outil[];
  onOutils: (o: Outil[]) => void;
  modeTrace: ModeTrace;
  onModeTrace: (m: ModeTrace) => void;
  nbDessins: number;
  onEffacer: () => void;
  donnees: ReponseBougies | null;
  mode: Mode;
}

const HEURE = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
const JOUR = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

/** Barre d'outils du graphique : unité de temps, repères automatiques, tracé manuel, et lecture des cassures en texte. */
export default function OutilsTechniques({ unite, onUnite, outils, onOutils, modeTrace, onModeTrace, nbDessins, onEffacer, donnees, mode }: Props) {
  const bascule = (o: Outil) => onOutils(outils.includes(o) ? outils.filter((x) => x !== o) : [...outils, o]);
  const date = (t: number) => (unite === "1j" ? JOUR : HEURE).format(t * 1000);
  const cassures = outils.includes("niveaux") ? donnees?.niveaux.cassures ?? [] : [];
  const pasMin = donnees?.pas_ticks_s ? donnees.pas_ticks_s / 60 : null;

  return (
    <div className="outils-techniques">
      <div className="outils-ligne">
        <div className="choix-filtre" role="group" aria-label="Unité de temps des bougies">
          <span className="indicateurs-titre">Unité</span>
          {UNITES.map((u) => <button key={u.cle} type="button" aria-pressed={unite === u.cle} onClick={() => onUnite(u.cle)}>{u.libelle}</button>)}
        </div>
        <div className="choix-filtre" role="group" aria-label="Repères automatiques">
          <span className="indicateurs-titre">Repères</span>
          {OUTILS.map((o) => (
            <button key={o.cle} type="button" aria-pressed={outils.includes(o.cle)} onClick={() => bascule(o.cle)} title={o.aide}
              disabled={o.cle === "volumes" && unite !== "1j"}>{o.libelle}</button>
          ))}
        </div>
        <div className="choix-filtre" role="group" aria-label="Tracé manuel sur le graphique">
          <span className="indicateurs-titre">Tracer</span>
          <button type="button" aria-pressed={modeTrace === "horizontal"} onClick={() => onModeTrace(modeTrace === "horizontal" ? "aucun" : "horizontal")}>Support / résistance</button>
          <button type="button" aria-pressed={modeTrace === "tendance"} onClick={() => onModeTrace(modeTrace === "tendance" ? "aucun" : "tendance")}>Ligne de tendance</button>
          {nbDessins > 0 && <button type="button" onClick={onEffacer}>Effacer mes tracés ({nbDessins})</button>}
        </div>
      </div>

      {modeTrace !== "aucun" && (
        <p className="outils-consigne" role="status">
          {modeTrace === "horizontal" ? "Cliquez sur le graphique au prix voulu : une ligne horizontale y sera tracée." : "Cliquez sur deux bougies : la ligne de tendance passera par ces deux points."}
          {" "}Vos tracés sont gardés dans ce navigateur pour cet actif.
        </p>
      )}
      {donnees?.intrajournalier && (
        <p className="graphique-note">
          Heures UTC. Bougies construites à partir des mouvements intrajournaliers <strong>simulés</strong> (un tick toutes les {pasMin ? pasMin.toLocaleString("fr-FR", { maximumFractionDigits: 1 }) : "–"} minutes environ, prix interpolé entre deux ticks comme pour l&apos;exécution des ordres) : ce ne sont pas des cotations réelles minute par minute. Volumes disponibles en unité 1 jour seulement.
        </p>
      )}
      {cassures.length > 0 && (
        <ul className="liste-cassures" aria-label="Cassures récentes">
          {cassures.slice(0, 3).map((c) => (
            <li key={`${c.niveau}-${c.t}`}>
              <span className={c.sens === "haussiere" ? "gain" : "perte"} aria-hidden="true">{c.sens === "haussiere" ? "▲" : "▼"}</span>{" "}
              Cassure {c.sens === "haussiere" ? "haussière" : "baissière"} <em>possible</em> du niveau {prix(c.niveau)} le {date(c.t)} (clôture {prix(c.prix)}).
              {" "}Depuis, {c.bougies_depuis} bougie{c.bougies_depuis > 1 ? "s" : ""} : {c.variation_depuis !== null ? pctSigne(c.variation_depuis) : "–"}.
            </li>
          ))}
        </ul>
      )}
      {mode === "apprenant" && outils.length > 0 && (
        <details className="indicateurs-aide">
          <summary>Que montrent ces repères ?</summary>
          <div>
            {OUTILS.filter((o) => outils.includes(o.cle)).map((o) => <p key={o.cle}><strong>{o.libelle}.</strong> {o.aide}</p>)}
            <p>Ces repères décrivent le passé. Une cassure est un signal possible, souvent démenti (« fausse cassure ») : ce n&apos;est jamais un conseil d&apos;achat ou de vente.</p>
          </div>
        </details>
      )}
    </div>
  );
}
