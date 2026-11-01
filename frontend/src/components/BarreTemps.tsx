"use client";

import { useEffect, useState } from "react";
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
  const { inst, aller, basculerPause, changerFacteur, activerDirect, quitterDirect } = useMarche();
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

      {enDirect ? (
        <div className="commandes-temps">
          <p className="direct-badge" role="status"><span aria-hidden="true">●</span> DIRECT (bêta) · heure réelle</p>
          <button className="btn" onClick={() => void quitterDirect()}>Quitter le Direct</button>
        </div>
      ) : (
      <div className="commandes-temps">
        <button className="btn btn-temps" onClick={basculerPause} disabled={!h || inst?.termine}
          aria-label={h?.en_pause ? "Lancer la simulation" : "Mettre la simulation en pause"}>
          {inst?.termine ? "Terminée" : h?.en_pause ? "▶ Lancer" : "❚❚ Pause"}
        </button>
        <label className="vitesse">
          <span>Vitesse</span>
          <select value={nomFacteur ?? ""} onChange={(e) => h && void changerFacteur(h.facteurs_predefinis[e.target.value])} disabled={!h}>
            {!nomFacteur && h && <option value="">×{h.facteur}</option>}
            {h && Object.keys(h.facteurs_predefinis).map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <button className="btn" onClick={() => void ouvrirDirect()} aria-haspopup="dialog" disabled={!h}>◉ Direct (bêta)</button>
      </div>
      )}

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
