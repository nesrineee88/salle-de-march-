"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Download } from "lucide-react";
import { lienFiche } from "@/lib/actif";
import { instantDate, montant, prix, quantite } from "@/lib/format";
import { useMarche } from "./Contexte";

type Filtre = "tout" | "achat" | "vente";
const FORMAT = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
/** Date, année et heure simulées (l'année compte : le rejeu couvre 2018 à 2026). */
const dateComplete = (iso: string) => FORMAT.format(instantDate(iso)).replace(" ", " à ");

/** Historique de toutes les transactions : quoi, quand (date et heure simulées), combien, à quel prix, avec les totaux. */
export default function HistoriqueTransactions() {
  const { execs, ordres, actifs } = useMarche();
  const [filtre, setFiltre] = useState<Filtre>("tout");
  const [symbole, setSymbole] = useState("");

  const origines = useMemo(() => new Map(ordres.map((o) => [o.id, o.origine])), [ordres]);
  const noms = useMemo(() => new Map(actifs.map((a) => [a.symbole, a.nom])), [actifs]);
  const symboles = useMemo(() => [...new Set(execs.map((e) => e.symbole))].sort(), [execs]);
  const lignes = execs.filter((e) => (filtre === "tout" || e.sens === filtre) && (!symbole || e.symbole === symbole));

  const achete = lignes.filter((e) => e.sens === "achat").reduce((s, e) => s + e.quantite * e.prix, 0);
  const vendu = lignes.filter((e) => e.sens === "vente").reduce((s, e) => s + e.quantite * e.prix, 0);
  const frais = lignes.reduce((s, e) => s + e.frais, 0);

  function exporter() {
    const entete = ["date_heure_simulee", "symbole", "nom", "sens", "quantite", "prix", "montant", "frais", "origine", "ordre"];
    const csv = [entete, ...lignes.map((e) => [e.instant, e.symbole, noms.get(e.symbole) ?? "", e.sens, e.quantite, e.prix, (e.quantite * e.prix).toFixed(2), e.frais, origines.get(e.ordre_id) ? "regle" : "manuel", e.ordre_id])]
      .map((l) => l.map((c) => `"${String(c).replaceAll('"', '""')}"`).join(";")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
    a.download = "historique-transactions.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  if (execs.length === 0) return <p className="vide">Aucune transaction pour le moment. Chaque achat et chaque vente apparaîtra ici, avec sa date et son heure.</p>;

  return (
    <div className="historique">
      <div className="historique-outils">
        <div className="segment" role="group" aria-label="Type de transaction">
          {([["tout", "Tout"], ["achat", "Achats"], ["vente", "Ventes"]] as const).map(([cle, lib]) => (
            <button key={cle} type="button" aria-pressed={filtre === cle} onClick={() => setFiltre(cle)}>{lib}</button>
          ))}
        </div>
        <label className="historique-actif">
          <span className="sr-only">Actif</span>
          <select value={symbole} onChange={(e) => setSymbole(e.target.value)} aria-label="Filtrer par actif">
            <option value="">Tous les actifs</option>
            {symboles.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <button type="button" className="btn btn-icone-texte" onClick={exporter}><Download size={16} aria-hidden="true" /> Exporter (CSV)</button>
      </div>

      <p className="historique-resume discret" role="status">
        {lignes.length} transaction(s) · acheté {montant(achete)} · vendu {montant(vendu)} · frais {montant(frais)}
        {execs.length >= 200 && " · les 200 plus récentes seulement"}
      </p>

      <table className="tableau">
        <thead><tr><th>Date et heure simulées</th><th>Actif</th><th>Sens</th><th>Quantité</th><th>Prix</th><th>Montant</th><th>Frais</th><th>Origine</th><th>N° d&apos;ordre</th></tr></thead>
        <tbody>
          {lignes.map((e, i) => (
            <tr key={`${e.ordre_id}-${e.instant}-${i}`}>
              <td>{dateComplete(e.instant)}</td>
              <td><Link href={lienFiche(e.symbole)} title={noms.get(e.symbole)}><strong>{e.symbole}</strong></Link> <small className="discret">{noms.get(e.symbole)}</small></td>
              <td><span className={e.sens === "achat" ? "gain" : "perte"}>{e.sens === "achat" ? "▲ Achat" : "▼ Vente"}</span></td>
              <td>{quantite(e.quantite)}</td><td>{prix(e.prix)}</td><td>{montant(e.quantite * e.prix)}</td><td>{montant(e.frais)}</td>
              <td>{origines.get(e.ordre_id) ? "Règle automatique" : "Manuel"}</td><td>{e.ordre_id}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {lignes.length === 0 && <p className="vide">Aucune transaction ne correspond à ce filtre.</p>}
    </div>
  );
}
