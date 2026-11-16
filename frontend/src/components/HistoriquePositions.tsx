"use client";

import { useMemo, useState } from "react";
import { dateHeure, montantSigne, pctSigne, prix, quantite } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import type { PositionHistorique } from "@/lib/types";

const MOTIFS: Record<string, string> = {
  manuelle: "Vente manuelle", stop_loss: "Stop-loss", take_profit: "Prise de profit", stop_suiveur: "Stop suiveur",
  achat_complementaire: "Règle automatique", regle: "Règle automatique",
};
const FILTRES = [
  { cle: "toutes", libelle: "Toutes" },
  { cle: "ouverte", libelle: "Ouvertes" },
  { cle: "cloturee", libelle: "Clôturées" },
] as const;

function ton(n: number | null): "gain" | "perte" | undefined { return n === null ? undefined : n > 0 ? "gain" : n < 0 ? "perte" : undefined; }

/** Chaque position, de son ouverture à sa clôture. Une position clôturée reste visible ici avec son résultat. */
export default function HistoriquePositions() {
  const { donnees, erreur } = useLecture<PositionHistorique[]>("/api/v1/portefeuille/positions/historique", 5000);
  const [filtre, setFiltre] = useState<(typeof FILTRES)[number]["cle"]>("toutes");
  const lignes = useMemo(() => (donnees ?? []).filter((p) => filtre === "toutes" || p.statut === filtre), [donnees, filtre]);

  if (!donnees) return erreur ? <p className="erreur" role="alert">{erreur}</p> : <p className="chargement">Chargement de l&apos;historique…</p>;
  return (
    <>
      <div className="choix-filtre" role="group" aria-label="Filtrer les positions">
        {FILTRES.map((f) => (
          <button key={f.cle} type="button" aria-pressed={filtre === f.cle} onClick={() => setFiltre(f.cle)}>
            {f.libelle} ({(f.cle === "toutes" ? donnees : donnees.filter((p) => p.statut === f.cle)).length})
          </button>
        ))}
      </div>
      {lignes.length === 0 ? (
        <p className="vide">{donnees.length === 0 ? "Aucune position pour le moment : chaque achat ouvre une position, qui restera ici même après sa vente." : "Aucune position dans cette catégorie."}</p>
      ) : (
        <table className="tableau">
          <caption className="sr-only">Historique des positions, de l&apos;ouverture à la clôture</caption>
          <thead><tr><th>Actif</th><th>Statut</th><th>Ouverte le</th><th>Clôturée le</th><th>Quantité max.</th><th>Prix d&apos;achat moyen</th><th>Prix de vente moyen</th><th>Résultat net (USD)</th><th>Rendement net</th><th>Motif de clôture</th></tr></thead>
          <tbody>
            {lignes.map((p) => (
              <tr key={`${p.symbole}-${p.ouverte_le}`}>
                <td>{p.symbole}</td>
                <td>{p.statut === "ouverte" ? `Ouverte (${quantite(p.quantite_restante)})` : "Clôturée"}</td>
                <td>{dateHeure(p.ouverte_le)}</td>
                <td>{p.cloturee_le ? dateHeure(p.cloturee_le) : "–"}</td>
                <td>{quantite(p.quantite_max)}</td>
                <td>{prix(p.prix_achat_moyen)}</td>
                <td>{prix(p.prix_vente_moyen)}</td>
                <td className={ton(p.resultat_net)} title={`Réalisé ${montantSigne(p.pnl_realise)} moins frais ${montantSigne(p.frais)}`}>{montantSigne(p.resultat_net)}</td>
                <td className={ton(p.rendement_net)}>{p.rendement_net !== null ? pctSigne(p.rendement_net) : "–"}</td>
                <td>{p.motif_cloture ? MOTIFS[p.motif_cloture] ?? p.motif_cloture : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="aide">Résultat net = gains et pertes réalisés par les ventes, moins tous les frais de la position (achats et ventes). Pour une position encore ouverte, seule la partie déjà vendue est comptée.</p>
    </>
  );
}
