"use client";

import { useEffect, useMemo, useState } from "react";
import { Pause, Play } from "lucide-react";
import { dateCourte, heure, instantDate } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import { HEURE_ARRIVEE, jourPlus } from "@/lib/temps";
import type { Barre } from "@/lib/types";
import { useMarche } from "./Contexte";
import { BoutonXAI } from "./xai/Assistant";

const JOUR_SEMAINE = new Intl.DateTimeFormat("fr-FR", { weekday: "short", timeZone: "UTC" });

/** La pellicule en pied d'écran : le passé est projeté, l'avenir reste hachuré. */
export default function BarreTemps({ instant, signaler }: { instant: string | null; signaler: (message: string) => void }) {
  const { inst, aller, basculerPause, changerFacteur } = useMarche();
  const [occupe, setOccupe] = useState(false);
  // Passé du S&P 500 : le serveur ne renvoie jamais au-delà de l'instant simulé.
  const { donnees: passe, relire } = useLecture<Barre[]>(inst ? `/api/v1/historique/${encodeURIComponent("^GSPC")}?barres=2000` : null, 30_000);

  const debut = inst?.fenetre.debut;
  const fin = inst?.fenetre.fin;
  const jour = instant?.slice(0, 10);
  const jourServeur = inst?.instant.slice(0, 10);
  useEffect(() => { if (jourServeur) void relire(); }, [jourServeur, relire]);

  const trace = useMemo(() => {
    if (!passe || !debut || !fin || !jour) return "";
    const pts = passe.filter((b) => b.date >= debut && b.date <= fin && b.date <= jour);
    if (pts.length < 2) return "";
    const valeurs = pts.map((b) => b.close);
    const bas = Math.min(...valeurs), haut = Math.max(...valeurs);
    const t0 = Date.parse(debut), etendue = Date.parse(fin) - t0;
    const pas = Math.ceil(pts.length / 500);
    return pts.filter((_, i) => i % pas === 0 || i === pts.length - 1).map((b, i) =>
      `${i ? "L" : "M"}${(((Date.parse(b.date) - t0) / etendue) * 1000).toFixed(1)},${(25 - ((b.close - bas) / (haut - bas || 1)) * 20).toFixed(1)}`).join("");
  }, [passe, debut, fin, jour]);

  if (!inst || !instant || !debut || !fin) return <footer className="seance-film"><p>Connexion au marché…</p><BoutonXAI /></footer>;

  const { direct, termine, horloge } = inst;
  const enPause = horloge.en_pause || termine;
  const predefinis = horloge.facteurs_predefinis;
  const nomFacteur = Object.entries(predefinis).find(([, f]) => f === horloge.facteur)?.[0];
  const t0 = Date.parse(`${debut}T00:00:00Z`);
  const t1 = Date.parse(`${fin}T23:59:59Z`);
  const ecoule = direct ? 1 : Math.min(1, Math.max(0, (instantDate(instant).getTime() - t0) / (t1 - t0)));

  async function agir(action: () => Promise<void>) {
    setOccupe(true);
    try { await action(); }
    catch (e) { signaler(e instanceof Error ? e.message : "Le temps n’a pas pu changer."); }
    finally { setOccupe(false); }
  }
  function avancerDe(n: number) {
    const cible = jourPlus(instant!, n);
    void agir(() => aller(cible >= fin! ? `${fin}T23:59:59` : `${cible}T${HEURE_ARRIVEE}`));
  }
  const fige = direct || termine || occupe;

  return (
    <footer className="seance-film" aria-label="Temps simulé">
      <button type="button" className="seance-lecture" disabled={fige} onClick={() => void agir(basculerPause)}
        aria-label={direct ? "Le Direct suit l’heure réelle" : termine ? "Simulation terminée" : enPause ? "Lancer le temps" : "Mettre le temps en pause"}>
        {enPause || direct ? <Play size={17} fill="currentColor" aria-hidden="true" /> : <Pause size={17} fill="currentColor" aria-hidden="true" />}
      </button>
      <div className="seance-film-date">
        <strong>{JOUR_SEMAINE.format(instantDate(instant))} {dateCourte(instant)}</strong>
        <small>{direct ? "Direct, lecture seule" : termine ? "Séance terminée" : `${heure(instant)} UTC, ${enPause ? "en pause" : "le temps avance"}`}</small>
      </div>
      <div className="seance-bobine" role="img" aria-label={`Période rejouée : ${Math.round(ecoule * 100)} % écoulés. La suite est masquée.`}>
        <svg viewBox="0 0 1000 30" preserveAspectRatio="none" aria-hidden="true"><path d={trace} vectorEffect="non-scaling-stroke" /></svg>
        {ecoule < 1 && <div className="seance-futur" style={{ width: `${(1 - ecoule) * 100}%` }}>{ecoule < 0.88 && <span>Avenir masqué</span>}</div>}
      </div>
      <button type="button" className="seance-pas" disabled={fige} onClick={() => avancerDe(1)}>+1 j</button>
      <button type="button" className="seance-pas seance-option" disabled={fige} onClick={() => avancerDe(5)}>+5 j</button>
      <label className="seance-vitesse seance-option">
        <span className="sr-only">Vitesse de la simulation</span>
        <select value={nomFacteur ?? ""} disabled={fige} onChange={(e) => void agir(() => changerFacteur(predefinis[e.target.value]))}>
          {!nomFacteur && <option value="">×{horloge.facteur}</option>}
          {Object.keys(predefinis).map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>
      <BoutonXAI />
    </footer>
  );
}
