"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EtatDirect } from "@/lib/types";
import { useMarche } from "./Contexte";
import Dialogue from "./ui/Dialogue";

export default function DialogueDirect({ fermer }: { fermer: () => void }) {
  const { activerDirect } = useMarche();
  const [etat, setEtat] = useState<EtatDirect | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    api<EtatDirect>("/api/v1/direct/etat").then(setEtat)
      .catch((e: unknown) => setMessage(e instanceof Error ? e.message : "Lecture impossible."));
  }, []);

  async function confirmer() {
    setEnvoi(true); setMessage(null);
    try { await activerDirect(); fermer(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Activation impossible."); }
    finally { setEnvoi(false); }
  }

  return (
    <Dialogue titre="Passer en Direct" fermer={fermer}>
      {!etat ? !message && <p role="status">Vérification du flux…</p> : !etat.disponible ? <p>Le mode Direct est désactivé sur ce serveur.</p> : (
        <>
          <p>Le marché suit l’heure réelle, <strong>en lecture seule</strong>. Votre rejeu est mis de côté : vous retrouverez sa date et son portefeuille en revenant.</p>
          <ul className="seance-avertissements">{etat.avertissements.map((a) => <li key={a}>{a}</li>)}</ul>
        </>
      )}
      {message && <p className="erreur" role="alert">{message}</p>}
      <div className="seance-dialogue-actions">
        <button type="button" className="btn" onClick={fermer}>Annuler</button>
        {etat?.disponible && (
          <button type="button" className="btn btn-principal" disabled={envoi} onClick={() => void confirmer()}>
            {envoi ? "Connexion au flux…" : "Passer en Direct"}
          </button>
        )}
      </div>
    </Dialogue>
  );
}
