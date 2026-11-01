"use client";

import { prix, quantite } from "@/lib/format";
import type { Carnet as CarnetT } from "@/lib/types";
import type { Mode } from "./Contexte";

export default function Carnet({ carnet, mode }: { carnet: CarnetT | null; mode: Mode }) {
  if (!carnet) return null;
  const max = Math.max(...carnet.achats.map((n) => n.quantite), ...carnet.ventes.map((n) => n.quantite));
  const ventes = [...carnet.ventes].reverse();
  return (
    <section className="carnet" aria-labelledby="titre-carnet">
      <h2 id="titre-carnet">Carnet d&apos;ordres simulé</h2>
      {mode === "apprenant" && (
        <p className="aide">En haut, les prix auxquels on accepte de vous vendre. En bas, ceux auxquels on accepte de vous acheter. L&apos;écart entre les deux est le spread.</p>
      )}
      <table className="tableau tableau-carnet">
        <thead><tr><th scope="col">Prix</th><th scope="col">Quantité</th></tr></thead>
        <tbody>
          {ventes.map((n) => (
            <tr key={`v${n.prix}`} className="carnet-vente" style={{ ["--part" as string]: `${(n.quantite / max) * 100}%` }}>
              <td>{prix(n.prix)}</td><td>{quantite(Math.round(n.quantite * 100) / 100)}</td>
            </tr>
          ))}
          <tr className="carnet-spread"><td colSpan={2}>Spread {prix(carnet.spread)}{carnet.statut_marche === "ferme" ? " · marché fermé" : ""}</td></tr>
          {carnet.achats.map((n) => (
            <tr key={`a${n.prix}`} className="carnet-achat" style={{ ["--part" as string]: `${(n.quantite / max) * 100}%` }}>
              <td>{prix(n.prix)}</td><td>{quantite(Math.round(n.quantite * 100) / 100)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
