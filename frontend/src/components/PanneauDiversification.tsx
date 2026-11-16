"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { montant, nombre, pctSigne } from "@/lib/format";
import type { Analyse, ResultatChocSectoriel } from "@/lib/types";
import { useMarche } from "./Contexte";

export default function PanneauDiversification({ analyse }: { analyse: Analyse | null }) {
  const { actifs } = useMarche();
  const secteurs = [...new Set(actifs.filter((a) => a.tradable && a.secteur).map((a) => a.secteur))].sort();
  const [secteur, setSecteur] = useState("");
  const [choc, setChoc] = useState(-30);
  const [resultat, setResultat] = useState<ResultatChocSectoriel | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const concentration = analyse?.concentration_detail;

  useEffect(() => {
    if (secteurs.length > 0 && !secteurs.includes(secteur)) setSecteur(secteurs[0]);
  }, [secteurs, secteur]);

  async function simuler(e: React.FormEvent) {
    e.preventDefault();
    if (!secteur) return;
    setEnCours(true);
    setErreur(null);
    setResultat(null);
    try {
      setResultat(await api<ResultatChocSectoriel>("/api/v1/portefeuille/simuler-choc", {
        methode: "POST",
        corps: { secteur, choc_pct: choc },
      }));
    } catch (e) {
      setErreur(e instanceof Error ? e.message : "La simulation du choc a échoué.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="panneau panneau-diversification" aria-labelledby="titre-diversification">
      <header className="panneau-tete"><h2 id="titre-diversification">Diversification</h2></header>
      {concentration ? (
        <>
          <div className="diversification-indicateurs">
            <div><span>HHI des positions</span><strong>{nombre(concentration.hhi, 2)}</strong></div>
            <div><span>Positions équivalentes</span><strong>{nombre(concentration.nb_effectif, 2)}</strong></div>
            <div><span>HHI sectoriel</span><strong>{nombre(concentration.hhi_secteurs, 2)}</strong></div>
            <div><span>Équivalents sectoriels</span><strong>{nombre(concentration.nb_effectif_secteurs, 2)}</strong></div>
            <div><span>Plus grosse position</span><strong>{concentration.plus_grosse_position.symbole} · {nombre(concentration.plus_grosse_position.part * 100, 1)} %</strong></div>
            <div><span>Plus gros secteur</span><strong>{concentration.plus_gros_secteur.secteur} · {nombre(concentration.plus_gros_secteur.part * 100, 1)} %</strong></div>
          </div>
          <p className="diversification-niveau">
            Niveau selon le HHI des positions: <span className={`badge-hhi badge-hhi-${concentration.niveau}`}>{concentration.niveau}</span>
          </p>
          <p className="aide">Repères pédagogiques : HHI &lt; 0,15 diversifié ; de 0,15 à 0,25 modéré ; au-delà de 0,25 concentré.</p>
          <ul className="alertes-concentration" aria-live="polite">
            {concentration.alertes.length > 0
              ? concentration.alertes.map((a) => <li key={a.texte} className={`alerte-concentration alerte-concentration-${a.niveau}`}>{a.texte}</li>)
              : <li>Aucun des seuils de concentration pédagogique n’est dépassé.</li>}
          </ul>
        </>
      ) : (
        <p className="vide">Aucune position investie : la concentration sera calculée après un premier achat.</p>
      )}

      <div className="pistes-diversification">
        <h3>Pistes pédagogiques</h3>
        <ul>{(analyse?.pistes_diversification ?? ["Calcul des pistes en cours…"]).map((p) => <li key={p}>{p}</li>)}</ul>
        <p className="aide">Ce sont des pistes d’observation, pas des conseils d’achat.</p>
      </div>

      <div className="simulateur-choc">
        <h3>Simuler un choc sectoriel</h3>
        <p className="aide">Simulation indicative, sans modifier votre portefeuille ni les cours.</p>
        <form onSubmit={(e) => void simuler(e)}>
          <label htmlFor="secteur-choc">Secteur</label>
          <select id="secteur-choc" value={secteur} onChange={(e) => { setSecteur(e.target.value); setResultat(null); }} disabled={secteurs.length === 0}>
            {secteurs.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <label htmlFor="amplitude-choc">Choc : {choc > 0 ? "+" : ""}{choc} %</label>
          <input id="amplitude-choc" type="range" min="-60" max="60" step="5" value={choc}
            onChange={(e) => { setChoc(Number(e.target.value)); setResultat(null); }} />
          <button type="submit" className="btn btn-principal" disabled={enCours || !secteur}>{enCours ? "Simulation…" : "Simuler"}</button>
        </form>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        {resultat && (
          <div className="resultat-choc" role="status">
            <p>{resultat.perte_montant > 0 ? "Perte estimée" : "Variation estimée"} :
              <strong className={resultat.variation_portefeuille_pct < 0 ? "perte" : "gain"}>
                {" "}{montant(Math.abs(resultat.valeur_apres - resultat.valeur_avant))} ({pctSigne(resultat.variation_portefeuille_pct / 100)})
              </strong>
            </p>
            <dl>
              <div><dt>Valeur avant</dt><dd>{montant(resultat.valeur_avant)}</dd></div>
              <div><dt>Valeur après</dt><dd>{montant(resultat.valeur_apres)}</dd></div>
            </dl>
          </div>
        )}
      </div>
    </section>
  );
}
