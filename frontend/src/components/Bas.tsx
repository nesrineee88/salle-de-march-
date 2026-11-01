"use client";

import { useState } from "react";
import { dateHeure, montant, montantSigne, prix, quantite } from "@/lib/format";
import type { Execution, Ordre, Portefeuille } from "@/lib/types";

interface Props {
  pf: Portefeuille | null;
  ordres: Ordre[];
  executions: Execution[];
  onSelect: (s: string) => void;
  onAnnuler: (id: number) => void;
}

const LIBELLE_STATUT: Record<string, string> = {
  en_attente: "En attente", partiel: "Partiel", execute: "Exécuté", annule: "Annulé", rejete: "Refusé",
};
const LIBELLE_TYPE: Record<string, string> = { marche: "Marché", limite: "Limite", stop: "Stop" };

function Variation({ n }: { n: number }) {
  return <span className={n > 0 ? "gain" : n < 0 ? "perte" : ""}>{n > 0 ? "▲ " : n < 0 ? "▼ " : ""}{montantSigne(n)}</span>;
}

export default function Bas({ pf, ordres, executions, onSelect, onAnnuler }: Props) {
  const [onglet, setOnglet] = useState<"positions" | "ordres" | "executions">("positions");
  const origines = new Map(ordres.map((o) => [o.id, o.origine]));
  const ouverts = ordres.filter((o) => o.statut === "en_attente" || o.statut === "partiel").length;

  return (
    <section className="bas" aria-label="Portefeuille">
      {pf && (
        <dl className="synthese">
          <div><dt>Valeur du portefeuille</dt><dd>{montant(pf.equity)}</dd></div>
          <div><dt>Liquidités</dt><dd>{montant(pf.cash)}</dd></div>
          <div><dt>Gain ou perte depuis le départ</dt><dd><Variation n={pf.pnl_total} /></dd></div>
          <div><dt>Frais payés</dt><dd>{montant(pf.frais_cumules)}</dd></div>
        </dl>
      )}
      <div className="onglets onglets-bas" role="tablist" aria-label="Détail du portefeuille">
        <button role="tab" aria-selected={onglet === "positions"} className="onglet" onClick={() => setOnglet("positions")}>Positions ({pf?.positions.length ?? 0})</button>
        <button role="tab" aria-selected={onglet === "ordres"} className="onglet" onClick={() => setOnglet("ordres")}>Ordres{ouverts > 0 ? ` (${ouverts} en attente)` : ""}</button>
        <button role="tab" aria-selected={onglet === "executions"} className="onglet" onClick={() => setOnglet("executions")}>Exécutions</button>
      </div>

      <div className="bas-corps" role="tabpanel">
        {onglet === "positions" && (pf && pf.positions.length > 0 ? (
          <table className="tableau">
            <thead><tr><th>Actif</th><th>Quantité</th><th>Prix moyen</th><th>Prix actuel</th><th>Valeur</th><th>Gain ou perte</th><th>Poids</th></tr></thead>
            <tbody>
              {pf.positions.map((p) => (
                <tr key={p.symbole}>
                  <td><button className="lien" onClick={() => onSelect(p.symbole)}>{p.symbole}</button></td>
                  <td>{quantite(p.quantite)}</td><td>{prix(p.prix_moyen)}</td><td>{prix(p.prix_marche)}</td>
                  <td>{montant(p.valeur)}</td><td><Variation n={p.pnl_latent} /></td><td>{(p.poids * 100).toFixed(1).replace(".", ",")} %</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="vide">Aucune position. Passez un ordre d&apos;achat pour commencer.</p>)}

        {onglet === "ordres" && (ordres.length > 0 ? (
          <table className="tableau">
            <thead><tr><th>N°</th><th>Actif</th><th>Sens</th><th>Type</th><th>Quantité</th><th>Niveau</th><th>Prix moyen</th><th>Statut</th><th><span className="sr-only">Action</span></th></tr></thead>
            <tbody>
              {[...ordres].reverse().map((o) => (
                <tr key={o.id}>
                  <td>{o.id}</td><td>{o.symbole}</td><td>{o.sens === "achat" ? "Achat" : "Vente"}</td><td>{LIBELLE_TYPE[o.type]}{o.origine ? <span className="pastille" title="Placé par une règle automatique">auto</span> : null}</td>
                  <td>{quantite(o.quantite_executee)} / {quantite(o.quantite)}</td>
                  <td>{prix(o.prix_limite ?? o.prix_stop)}</td><td>{prix(o.prix_moyen)}</td>
                  <td title={o.motif ?? undefined}>{LIBELLE_STATUT[o.statut]}{o.statut === "rejete" && o.motif ? ` : ${o.motif}` : ""}</td>
                  <td>{(o.statut === "en_attente" || o.statut === "partiel") && <button className="lien" onClick={() => onAnnuler(o.id)}>Annuler</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="vide">Aucun ordre pour le moment.</p>)}

        {onglet === "executions" && (executions.length > 0 ? (
          <table className="tableau">
            <thead><tr><th>Date simulée</th><th>Actif</th><th>Sens</th><th>Quantité</th><th>Prix</th><th>Frais</th><th>Origine</th></tr></thead>
            <tbody>
              {executions.map((e, i) => (
                <tr key={`${e.ordre_id}-${i}`}>
                  <td>{dateHeure(e.instant)}</td><td>{e.symbole}</td><td>{e.sens === "achat" ? "Achat" : "Vente"}</td>
                  <td>{quantite(e.quantite)}</td><td>{prix(e.prix)}</td><td>{montant(e.frais)}</td>
                  <td>{origines.get(e.ordre_id) ? "Règle automatique" : "Manuel"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="vide">Aucune exécution pour le moment.</p>)}
      </div>
    </section>
  );
}
