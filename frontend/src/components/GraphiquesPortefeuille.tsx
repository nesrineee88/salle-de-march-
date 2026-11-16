"use client";

import { useState } from "react";
import { montant, montantSigne, pct, pctSigne } from "@/lib/format";
import type { PartRepartitionDetail } from "@/lib/types";

const COULEURS = ["var(--serie-1)", "var(--serie-2)", "var(--serie-3)", "var(--serie-4)", "var(--serie-5)", "var(--serie-6)"];
const CLES = [
  { cle: "position", libelle: "Par actif" },
  { cle: "marche", libelle: "Par classe" },
  { cle: "secteur", libelle: "Par secteur" },
] as const;

export function DonutRepartition({ donnees }: {
  donnees: { position: PartRepartitionDetail[]; marche: PartRepartitionDetail[]; secteur: PartRepartitionDetail[] };
}) {
  const [mode, setMode] = useState<(typeof CLES)[number]["cle"]>("position");
  const [selection, setSelection] = useState(0);
  const [survol, setSurvol] = useState<number | null>(null);
  const lignes = donnees[mode].filter((l) => Math.abs(l.valeur) > 1e-9);
  const poidsTotal = lignes.reduce((s, l) => s + Math.abs(l.valeur), 0);
  const rayon = 36;
  const perimetre = 2 * Math.PI * rayon;
  const courant = lignes.length ? lignes[Math.min(survol ?? selection, lignes.length - 1)] : null;
  let decalage = 0;

  return (
    <div className="donut-repartition">
      <div className="onglets" role="tablist" aria-label="Répartition du portefeuille">
        {CLES.map((c) => (
          <button key={c.cle} type="button" role="tab" aria-selected={mode === c.cle} className="onglet" onClick={() => { setMode(c.cle); setSelection(0); setSurvol(null); }}>
            {c.libelle}
          </button>
        ))}
      </div>
      {lignes.length === 0 ? (
        <p className="vide">Aucune valeur à répartir pour le moment.</p>
      ) : (
        <div className="donut-corps">
          <div className="donut-visuel">
            <svg viewBox="0 0 100 100" role="img" aria-label={`Répartition ${CLES.find((c) => c.cle === mode)?.libelle.toLowerCase()}`}>
              <circle cx="50" cy="50" r={rayon} fill="none" stroke="var(--nuit-3)" strokeWidth="16" />
              <g transform="rotate(-90 50 50)">
                {lignes.map((l, i) => {
                  const longueur = perimetre * (poidsTotal ? Math.abs(l.valeur) / poidsTotal : 0);
                  const debut = decalage;
                  decalage += longueur;
                  return (
                    <circle
                      key={l.libelle}
                      cx="50" cy="50" r={rayon} fill="none" stroke={COULEURS[i % COULEURS.length]}
                      strokeWidth={courant?.libelle === l.libelle ? 19 : 16}
                      strokeDasharray={`${longueur} ${perimetre - longueur}`}
                      strokeDashoffset={-debut}
                      onMouseEnter={() => setSurvol(i)}
                      onMouseLeave={() => setSurvol(null)}
                    >
                      <title>{`${l.libelle} : ${pct(l.part)} · ${montant(l.valeur)}`}</title>
                    </circle>
                  );
                })}
              </g>
              <text x="50" y="46" textAnchor="middle" className="donut-centre-nom">{courant?.libelle ?? ""}</text>
              <text x="50" y="57" textAnchor="middle" className="donut-centre-valeur">{courant ? montant(courant.valeur) : ""}</text>
            </svg>
          </div>
          <ul className="donut-legende" aria-label="Détail de la répartition">
            {lignes.map((l, i) => (
              <li key={l.libelle}>
                <button
                  type="button"
                  className="donut-legende-ligne"
                  aria-pressed={selection === i}
                  onFocus={() => setSurvol(i)}
                  onBlur={() => setSurvol(null)}
                  onMouseEnter={() => setSurvol(i)}
                  onMouseLeave={() => setSurvol(null)}
                  onClick={() => setSelection(i)}
                >
                  <i className="donut-pastille" style={{ backgroundColor: COULEURS[i % COULEURS.length] }} aria-hidden="true" />
                  <span className="donut-libelle">{l.libelle}</span>
                  <span className="donut-chiffres">{pct(l.part)} · {montant(l.valeur)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {courant && (
        <p className={`donut-pnl ${courant.pnl_latent > 0 ? "gain" : courant.pnl_latent < 0 ? "perte" : ""}`}>
          P&amp;L latent : {montantSigne(courant.pnl_latent)}
          {courant.pnl_latent_pct !== null && ` (${pctSigne(courant.pnl_latent_pct)})`}
        </p>
      )}
    </div>
  );
}

export function PerformancesPositions({ lignes }: { lignes: PartRepartitionDetail[] }) {
  const positions = lignes.filter((l) => l.libelle !== "Liquidités" && l.pnl_latent_pct !== null);
  if (positions.length === 0) return <p className="vide">Les performances par position apparaîtront après un premier achat.</p>;
  const maximum = Math.max(...positions.map((l) => Math.abs(l.pnl_latent_pct ?? 0)), 0.01);

  return (
    <div className="performances-positions" role="list" aria-label="Performance latente par position">
      {positions.map((l) => {
        const rendement = l.pnl_latent_pct ?? 0;
        const largeur = Math.abs(rendement) / maximum * 50;
        return (
          <div className="performance-position" role="listitem" key={l.libelle}>
            <strong>{l.libelle}</strong>
            <div className="performance-piste" aria-hidden="true">
              <span className="performance-zero" />
              <span className={`performance-barre ${rendement >= 0 ? "gain" : "perte"}`}
                style={rendement >= 0 ? { left: "50%", width: `${largeur}%` } : { left: `${50 - largeur}%`, width: `${largeur}%` }} />
            </div>
            <span className={rendement >= 0 ? "gain" : "perte"}>{pctSigne(rendement)}</span>
            <small className={l.pnl_latent >= 0 ? "gain" : "perte"}>{montantSigne(l.pnl_latent)}</small>
          </div>
        );
      })}
    </div>
  );
}
