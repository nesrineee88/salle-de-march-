"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ShieldCheck, Skull, Trophy } from "lucide-react";
import { ErreurApi } from "@/lib/api";
import { dateLongue, pct, pctSigne } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import { useJeux, type Defi } from "@/lib/jeux";
import type { HistoriqueValeur } from "@/lib/types";
import { useMarche } from "./Contexte";

const DEBUT = "2020-02-14", FIN = "2020-03-31", LIMITE = 0.15;

/** Défi : traverser la chute de mars 2020 sans que le portefeuille ne perde plus de 15 % depuis son sommet. Corrigé automatiquement. */
export default function DefiMars2020() {
  const { utilisateur, inst, reinitialiser, aller } = useMarche();
  const { etat, definirDefi } = useJeux(utilisateur.email);
  const defi = etat.defi;
  const { donnees: hist } = useLecture<HistoriqueValeur>("/api/v1/portefeuille/historique", 3000);
  const [confirme, setConfirme] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  // mesures depuis le départ : pire baisse (sommet → creux) et rendement
  const mesure = useMemo(() => {
    if (!defi || !hist) return null;
    const pts = hist.points.filter((p) => p.jour.slice(0, 10) >= defi.debut);
    if (pts.length === 0) return null;
    let sommet = pts[0].equity, pire = 0;
    for (const p of pts) { sommet = Math.max(sommet, p.equity); pire = Math.max(pire, 1 - p.equity / sommet); }
    const dernier = pts[pts.length - 1];
    const bench = pts[0].benchmark && dernier.benchmark ? dernier.benchmark / pts[0].benchmark - 1 : null;
    return { pire, rendement: dernier.equity / pts[0].equity - 1, valeur: dernier.equity, bench };
  }, [defi, hist]);

  const jour = inst?.instant.slice(0, 10) ?? null;
  const jours = jour && defi ? Math.max(0, Math.round((Date.parse(defi.fin) - Date.parse(jour)) / 86_400_000)) : null;

  // verdict : éliminé dès que la limite est franchie, réussi à la date de fin
  useEffect(() => {
    if (!defi || defi.statut !== "en_cours" || !mesure || !jour) return;
    if (jour < defi.debut) return;
    if (mesure.pire >= defi.limite) definirDefi({ ...defi, statut: "echoue", pire: mesure.pire, rendement: mesure.rendement, points: 20 });
    else if (jour >= defi.fin) definirDefi({ ...defi, statut: "reussi", pire: mesure.pire, rendement: mesure.rendement, points: 300 + (mesure.rendement >= 0 ? 200 : 0) });
  }, [defi, mesure, jour, definirDefi]);

  async function demarrer() {
    setEnvoi(true); setMessage(null);
    try {
      await reinitialiser();
      await aller(`${DEBUT}T17:00:00`);
      const d: Defi = { debut: DEBUT, fin: FIN, limite: LIMITE, statut: "en_cours", pire: 0, rendement: 0, points: 0 };
      definirDefi(d);
      setConfirme(false);
    } catch (e) { setMessage(e instanceof ErreurApi ? e.message : e instanceof Error ? e.message : "Impossible de démarrer le défi."); }
    finally { setEnvoi(false); }
  }

  if (!defi || confirme) {
    return (
      <section className="panneau defi-intro">
        <p className="lecon-surtitre">Défi</p>
        <h2>Survis à mars 2020</h2>
        <p className="lecon-idee">En quelques semaines, les marchés ont chuté violemment. Saurez-vous protéger votre capital ?</p>
        <ul className="defi-regles">
          <li><strong>Départ :</strong> {dateLongue(`${DEBUT}T17:00:00`)}, avec le capital de départ.</li>
          <li><strong>Arrivée :</strong> {dateLongue(`${FIN}T17:00:00`)}.</li>
          <li><strong>Règle :</strong> votre portefeuille ne doit jamais perdre plus de {pct(LIMITE, 0)} depuis son sommet. Au-delà, vous êtes éliminé.</li>
          <li><strong>Points :</strong> 300 pour avoir survécu, +200 si vous finissez en gain.</li>
        </ul>
        <p className="aide">Pistes : limitez la taille de chaque position, posez des stops-loss, gardez des liquidités. Tout vendre est permis, mais ne rapporte pas le bonus.</p>
        {inst?.synthetiques && <p className="bandeau avertissement" role="note">Vous utilisez des prix de démonstration générés au hasard : la chute de mars 2020 n&apos;y existe pas. Le défi prend tout son sens avec les vrais prix (<code>python -m pipeline tout</code>).</p>}
        <p className="bandeau avertissement" role="note">Le départ remet votre portefeuille à zéro (ordres et positions) et place l&apos;horloge au {dateLongue(`${DEBUT}T17:00:00`)}.</p>
        <div className="direct-actions">
          <button type="button" className="btn btn-principal" style={{ width: "auto", marginTop: 0 }} onClick={() => void demarrer()} disabled={envoi}>{envoi ? "Préparation…" : defi ? "Confirmer le nouveau départ" : "Relever le défi"}</button>
          {defi && <button type="button" className="btn" onClick={() => setConfirme(false)}>Annuler</button>}
        </div>
        {message && <p className="erreur" role="alert">{message}</p>}
      </section>
    );
  }

  const ouvert = defi.statut === "en_cours";
  const part = mesure ? Math.min(mesure.pire / defi.limite, 1) : 0;
  return (
    <section className="panneau defi-suivi" aria-live="polite">
      <header className="defi-tete">
        <div>
          <p className="lecon-surtitre">Défi · Survis à mars 2020</p>
          <h2>{ouvert ? "Défi en cours" : defi.statut === "reussi" ? "Défi réussi" : "Éliminé"}</h2>
        </div>
        <span className="defi-badge" data-statut={defi.statut}>
          {defi.statut === "reussi" ? <Trophy size={18} aria-hidden="true" /> : defi.statut === "echoue" ? <Skull size={18} aria-hidden="true" /> : <ShieldCheck size={18} aria-hidden="true" />}
          {ouvert ? "En cours" : defi.statut === "reussi" ? `+${defi.points} pts` : `+${defi.points} pts`}
        </span>
      </header>

      <div className="defi-jauge" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((mesure?.pire ?? 0) * 100)} aria-label="Pire baisse depuis le sommet">
        <div className="defi-jauge-barre"><i style={{ width: `${part * 100}%` }} data-danger={part > 0.7} /></div>
        <p className="aide">Pire baisse : <strong>{pct(mesure?.pire ?? 0, 1)}</strong> sur {pct(defi.limite, 0)} tolérés.{part > 0.7 && ouvert ? " Attention, vous approchez de la limite." : ""}</p>
      </div>

      <dl className="faits">
        <div className="fait"><dt>Date simulée</dt><dd>{jour ? dateLongue(`${jour}T00:00:00`) : "–"}</dd></div>
        {ouvert && jours !== null && jour! >= defi.debut && <div className="fait"><dt>Jours restants</dt><dd>{jours}</dd></div>}
        <div className="fait"><dt>Rendement depuis le départ</dt><dd className={(mesure?.rendement ?? 0) >= 0 ? "gain" : "perte"}>{(mesure?.rendement ?? 0) >= 0 ? "▲ " : "▼ "}{pctSigne(mesure?.rendement ?? 0, 1)}</dd></div>
        {mesure?.bench !== null && mesure?.bench !== undefined && <div className="fait"><dt>{hist?.benchmark_nom ?? "Référence"} sur la même période</dt><dd>{pctSigne(mesure.bench, 1)}</dd></div>}
      </dl>

      {ouvert && <p className="aide">{jour && jour < defi.debut ? "Avancez dans le temps jusqu'au départ du défi." : "Lancez la simulation et vérifiez vos positions. Le verdict tombe tout seul."} <Link href="/actions">Aller aux marchés</Link></p>}
      {!ouvert && (
        <p className="lecon-idee">{defi.statut === "reussi"
          ? `Vous avez traversé la tempête avec une pire baisse de ${pct(defi.pire, 1)}.`
          : `Votre portefeuille a perdu ${pct(defi.pire, 1)} depuis son sommet, au-delà de la limite. Relisez vos erreurs et retentez.`}</p>
      )}
      <div className="direct-actions">
        <button type="button" className="btn" onClick={() => setConfirme(true)}>{ouvert ? "Recommencer" : "Retenter le défi"}</button>
      </div>
    </section>
  );
}
