"use client";

import { useEffect, useState } from "react";
import { Gauge, Pause, Play } from "lucide-react";
import { ErreurApi, api } from "@/lib/api";
import { dateLongue, heure, instantDate } from "@/lib/format";
import type { EtatDirect, Instantane } from "@/lib/types";
import { useMarche } from "./Contexte";
import Frise from "./Frise";

/** Horloge affichée en continu : entre deux réponses du serveur, on avance localement au même rythme. */
function useInstantLisse(inst: Instantane | null): string | null {
  const [affiche, setAffiche] = useState<string | null>(null);
  const instant = inst?.instant;
  const facteur = inst?.horloge.facteur;
  const enPause = inst?.horloge.en_pause;

  useEffect(() => {
    if (!instant || facteur === undefined) return;
    const base = instantDate(instant).getTime();
    const depart = performance.now();
    const maj = () => setAffiche(new Date(base + (enPause ? 0 : (performance.now() - depart) * facteur)).toISOString());
    maj();
    if (enPause) return;
    const t = setInterval(maj, 200);
    return () => clearInterval(t);
  }, [instant, facteur, enPause]);

  return inst ? affiche ?? inst.instant : null;
}

export default function BarreTemps() {
  const { mode, setMode, inst, aller, basculerPause, changerFacteur, activerDirect, quitterDirect } = useMarche();
  const lisse = useInstantLisse(inst);
  const [fiche, setFiche] = useState<EtatDirect | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const enDirect = inst?.direct ?? false;

  async function ouvrirDirect() {
    setMessage(null);
    try { setFiche(await api<EtatDirect>("/api/v1/direct/etat")); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Lecture impossible."); }
  }
  async function confirmer() {
    setEnCours(true); setMessage(null);
    try { await activerDirect(); setFiche(null); }
    catch (e) { setMessage(e instanceof ErreurApi ? e.message : "Activation impossible."); }
    finally { setEnCours(false); }
  }
  const h = inst?.horloge;
  const nomFacteur = h ? Object.entries(h.facteurs_predefinis).find(([, f]) => f === h.facteur)?.[0] : undefined;

  return (
    <div className="temps">
      <div className="horloge" aria-label="Date et heure simulées">
        {inst && lisse ? (
          <>
            <p className="horloge-heure">{heure(lisse)}</p>
            <p className="horloge-date">{dateLongue(lisse)}</p>
          </>
        ) : <p className="horloge-date">Connexion au marché…</p>}
      </div>

      <div className="commandes-temps">
        {!enDirect && (
          <>
            <button type="button" className="btn-lecture" onClick={basculerPause} disabled={!h || inst?.termine}
              aria-label={inst?.termine ? "Simulation terminée" : h?.en_pause ? "Lancer la simulation" : "Mettre la simulation en pause"}
              title={inst?.termine ? "Simulation terminée" : h?.en_pause ? "Lancer" : "Pause"}>
              {h?.en_pause || inst?.termine ? <Play size={18} aria-hidden="true" fill="currentColor" /> : <Pause size={18} aria-hidden="true" fill="currentColor" />}
            </button>
            <label className="vitesse" title="Vitesse de la simulation">
              <Gauge size={16} aria-hidden="true" />
              <span className="sr-only">Vitesse</span>
              <select value={nomFacteur ?? ""} onChange={(e) => h && void changerFacteur(h.facteurs_predefinis[e.target.value])} disabled={!h}>
                {!nomFacteur && h && <option value="">×{h.facteur}</option>}
                {h && Object.keys(h.facteurs_predefinis).map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          </>
        )}
        <div className="segment" role="group" aria-label="Mode de jeu">
          <button type="button" aria-pressed={mode === "apprenant"} onClick={() => setMode("apprenant")} title="Explications et repères pédagogiques">Apprenant</button>
          <button type="button" aria-pressed={mode === "trader"} onClick={() => setMode("trader")} title="Vue dense, sans aides">Trader</button>
        </div>
        <div className="segment" role="group" aria-label="Source des prix">
          <button type="button" aria-pressed={!enDirect} onClick={() => enDirect && void quitterDirect()} disabled={!h}>Rejeu historique</button>
          <button type="button" aria-pressed={enDirect} onClick={() => !enDirect && void ouvrirDirect()} aria-haspopup={enDirect ? undefined : "dialog"} disabled={!h}>
            {enDirect && <span className="point-direct" aria-hidden="true" />}Direct <small>bêta</small>
          </button>
        </div>
        {enDirect && <p className="direct-badge" role="status">Heure réelle · prix Yahoo Finance</p>}
      </div>

      {fiche && (
        <div className="direct-fiche" role="dialog" aria-labelledby="titre-direct">
          <h2 id="titre-direct">Passer en mode Direct (bêta)</h2>
          {fiche.disponible ? (
            <>
              <p>Votre horloge suivra l&apos;heure réelle et les prix viendront de Yahoo Finance. Vous pourrez quitter à tout moment.</p>
              <ul>{fiche.avertissements.map((a) => <li key={a}>{a}</li>)}</ul>
              <div className="direct-actions">
                <button className="btn btn-principal" onClick={() => void confirmer()} disabled={enCours}>{enCours ? "Connexion à Yahoo…" : "Passer en Direct"}</button>
                <button className="btn" onClick={() => setFiche(null)}>Annuler</button>
              </div>
            </>
          ) : (
            <>
              <p>Le mode Direct est désactivé sur ce serveur.</p>
              <button className="btn" onClick={() => setFiche(null)}>Fermer</button>
            </>
          )}
          {message && <p className="erreur" role="alert">{message}</p>}
        </div>
      )}
      {!fiche && message && <p className="erreur direct-erreur" role="alert">{message}</p>}

      {inst && lisse && !enDirect ? <Frise fenetre={inst.fenetre} instant={lisse} onAller={(iso) => void aller(iso)} /> : <div />}
    </div>
  );
}