"use client";

import { useState } from "react";
import { dateCourte, montant } from "@/lib/format";
import { REPERES } from "@/lib/reperes";
import { HEURE_ARRIVEE } from "@/lib/temps";
import { useMarche } from "./Contexte";
import Dialogue from "./ui/Dialogue";

const jourCourt = (jour: string) => dateCourte(`${jour}T00:00:00`);

/** Avancer garde le portefeuille. Reculer recommence avec le capital de départ, après confirmation. */
export default function DialogueDates({ fermer }: { fermer: () => void }) {
  const { inst, pf, execs, ordres, aller, recommencer, quitterDirect } = useMarche();
  const [jour, setJour] = useState(() => inst?.instant.slice(0, 10) ?? "");
  const [confirme, setConfirme] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  if (!inst) return null;

  async function lancer(action: () => Promise<void>, puisFermer = true) {
    setEnvoi(true); setMessage(null);
    try { await action(); if (puisFermer) fermer(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Action impossible."); }
    finally { setEnvoi(false); }
  }

  if (inst.direct) {
    return (
      <Dialogue titre="Le Direct suit la date d’aujourd’hui" fermer={fermer}>
        <p>Repassez en rejeu pour choisir une date. Vous retrouverez la date où vous l’aviez laissé.</p>
        {message && <p className="erreur" role="alert">{message}</p>}
        <div className="seance-dialogue-actions">
          <button type="button" className="btn" onClick={fermer}>Fermer</button>
          <button type="button" className="btn btn-principal" disabled={envoi} onClick={() => void lancer(quitterDirect)}>Passer en rejeu</button>
        </div>
      </Dialogue>
    );
  }

  const { debut, fin } = inst.fenetre;
  const capital = montant(pf?.capital_initial ?? 100_000);
  const valide = jour >= debut && jour <= fin;
  const cible = `${jour}T${HEURE_ARRIVEE}`;
  const enAvant = valide && cible > inst.instant;
  const utilise = execs.length > 0 || ordres.length > 0;
  const raccourcis = [
    { date: debut, titre: "Début 2019" },
    ...REPERES.filter((r) => r.date >= debut && r.date <= fin),
    { date: fin, titre: "Dernière séance" },
  ];
  const redemarrer = () => void lancer(() => recommencer(cible));

  if (confirme) {
    return (
      <Dialogue titre="Recommencer à cette date ?" fermer={fermer}>
        <p>Vos positions, vos ordres et votre courbe seront effacés. Vous repartirez du <strong>{jourCourt(jour)}</strong> avec <strong>{capital} USD</strong>.</p>
        {message && <p className="erreur" role="alert">{message}</p>}
        <div className="seance-dialogue-actions">
          <button type="button" className="btn" onClick={() => setConfirme(false)}>Garder mon portefeuille</button>
          <button type="button" className="btn btn-danger" disabled={envoi} onClick={redemarrer}>{envoi ? "Remise à zéro…" : "Effacer et recommencer"}</button>
        </div>
      </Dialogue>
    );
  }

  const effet = !valide ? `Choisissez une date entre le ${jourCourt(debut)} et le ${jourCourt(fin)}.`
    : enAvant ? "Avancer garde votre portefeuille : chaque jour traversé est joué, ordres et protections compris."
    : jour === inst.instant.slice(0, 10) ? "Vous êtes déjà à cette date."
    : `Reculer recommence avec ${capital} USD : on ne trade pas en connaissant la suite.`;

  return (
    <Dialogue titre="Changer la date" fermer={fermer}>
      <label className="seance-champ">
        Date simulée
        <input type="date" min={debut} max={fin} value={jour} onChange={(e) => setJour(e.target.value)} />
      </label>
      <div className="seance-raccourcis">
        {raccourcis.map((r) => (
          <button key={r.date} type="button" aria-pressed={jour === r.date} onClick={() => setJour(r.date)}>
            <strong>{r.titre}</strong><span>{jourCourt(r.date)}</span>
          </button>
        ))}
      </div>
      <p className="seance-note" role="status">{effet}</p>
      {message && <p className="erreur" role="alert">{message}</p>}
      <div className="seance-dialogue-actions">
        <button type="button" className={`btn ${valide && !enAvant ? "btn-principal" : ""}`} disabled={!valide || envoi}
          onClick={() => (utilise ? setConfirme(true) : redemarrer())}>
          Recommencer à cette date
        </button>
        <button type="button" className={`btn ${enAvant ? "btn-principal" : ""}`} disabled={!enAvant || envoi} onClick={() => void lancer(() => aller(cible))}>
          {envoi ? "Le temps avance…" : "Avancer jusqu’ici"}
        </button>
      </div>
    </Dialogue>
  );
}
