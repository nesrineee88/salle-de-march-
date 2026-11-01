"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { montant, pctSigne } from "@/lib/format";
import type { PointValeur } from "@/lib/types";

interface Props {
  points: PointValeur[];
  capitalInitial: number;
  nomReference: string;
  hauteur?: number;
  /** Affiche la liste des valeurs en tableau, pour ceux qui ne peuvent pas lire la courbe. */
  tableau?: boolean;
}

const MARGE = { haut: 12, droite: 16, bas: 24, gauche: 64 };
const MOIS = new Intl.DateTimeFormat("fr-FR", { month: "short", year: "2-digit", timeZone: "UTC" });
const JOUR_COURT = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", timeZone: "UTC" });
const JOUR_COMPLET_COURT = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "2-digit", timeZone: "UTC" });
const JOUR = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const ms = (jour: string) => Date.parse(`${jour}T00:00:00Z`);

/** Arrondit un pas d'axe à 1, 2 ou 5 fois une puissance de dix. */
function pasLisible(brut: number): number {
  const p = 10 ** Math.floor(Math.log10(brut));
  const f = brut / p;
  return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p;
}

function compact(n: number): string {
  const a = Math.abs(n);
  if (a >= 1e6) return `${(n / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: 2 })} M`;
  if (a >= 1e4) return `${(n / 1e3).toLocaleString("fr-FR", { maximumFractionDigits: 0 })} k`;
  return n.toLocaleString("fr-FR", { maximumFractionDigits: 0 });
}

/** Courbe de valeur du portefeuille (trait plein) comparée à un indice de référence (trait gris). */
export default function Courbe({ points, capitalInitial, nomReference, hauteur = 280, tableau = true }: Props) {
  const zone = useRef<HTMLDivElement>(null);
  const [largeur, setLargeur] = useState(640);
  const [survol, setSurvol] = useState<number | null>(null);
  const [enTableau, setEnTableau] = useState(false);

  useEffect(() => {
    if (!zone.current) return;
    const obs = new ResizeObserver(([e]) => setLargeur(Math.max(280, e.contentRect.width)));
    obs.observe(zone.current);
    return () => obs.disconnect();
  }, []);

  const g = useMemo(() => {
    if (points.length < 2) return null;
    const t0 = ms(points[0].jour), t1 = ms(points[points.length - 1].jour);
    const valeurs = points.flatMap((p) => [p.equity, p.benchmark ?? p.equity]).concat(capitalInitial);
    let lo = Math.min(...valeurs), hi = Math.max(...valeurs);
    const pas = pasLisible((hi - lo || hi * 0.1 || 1) / 4);
    lo = Math.floor(lo / pas) * pas; hi = Math.ceil(hi / pas) * pas;
    const w = largeur - MARGE.gauche - MARGE.droite, h = hauteur - MARGE.haut - MARGE.bas;
    const x = (j: string) => MARGE.gauche + (t1 === t0 ? 0 : ((ms(j) - t0) / (t1 - t0)) * w);
    const y = (v: number) => MARGE.haut + (1 - (v - lo) / (hi - lo)) * h;
    const graduations: number[] = [];
    for (let v = lo; v <= hi + pas / 2; v += pas) graduations.push(v);
    // repères horizontaux : dates réparties régulièrement dans le TEMPS (pas dans la liste des points), sans doublon
    const nbDates = largeur < 480 ? 3 : 5;
    const jours = (t1 - t0) / 86_400_000;
    const format = jours > 60 ? MOIS : jours > 14 ? JOUR_COMPLET_COURT : JOUR_COURT;
    const dates: { x: number; texte: string }[] = [];
    for (let i = 0; i < nbDates; i++) {
      const t = t0 + ((t1 - t0) * i) / (nbDates - 1);
      const texte = format.format(t);
      if (dates.length === 0 || dates[dates.length - 1].texte !== texte) dates.push({ x: MARGE.gauche + (t1 === t0 ? 0 : ((t - t0) / (t1 - t0)) * w), texte });
    }
    const trace = (cle: "equity" | "benchmark") => {
      let d = "";
      for (const p of points) {
        const v = p[cle];
        if (v === null) continue;
        d += `${d ? "L" : "M"}${x(p.jour).toFixed(1)},${y(v).toFixed(1)}`;
      }
      return d;
    };
    const ligne = trace("equity");
    const bas = MARGE.haut + h;
    const aire = `${ligne}L${x(points[points.length - 1].jour).toFixed(1)},${bas}L${x(points[0].jour).toFixed(1)},${bas}Z`;
    return { x, y, graduations, dates, ligne, aire, reference: points.some((p) => p.benchmark !== null) ? trace("benchmark") : "", h, w };
  }, [points, capitalInitial, largeur, hauteur]);

  if (!g) {
    return (
      <p className="vide" role="status">
        La courbe apparaîtra dès que le temps aura avancé d&apos;au moins un jour. Lancez la simulation, ou choisissez une date sur la frise.
      </p>
    );
  }

  const dernier = points[points.length - 1];
  const actif = survol !== null ? points[survol] : null;

  function surPointeur(e: React.PointerEvent<SVGSVGElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - r.left;
    let meilleur = 0, dist = Infinity;
    points.forEach((p, i) => { const d = Math.abs(g!.x(p.jour) - px); if (d < dist) { dist = d; meilleur = i; } });
    setSurvol(meilleur);
  }
  function surClavier(e: React.KeyboardEvent) {
    if (e.key === "ArrowLeft") { e.preventDefault(); setSurvol((s) => Math.max(0, (s ?? points.length) - 1)); }
    else if (e.key === "ArrowRight") { e.preventDefault(); setSurvol((s) => Math.min(points.length - 1, (s ?? -1) + 1)); }
    else if (e.key === "Home") { e.preventDefault(); setSurvol(0); }
    else if (e.key === "End") { e.preventDefault(); setSurvol(points.length - 1); }
    else if (e.key === "Escape") setSurvol(null);
  }

  const xs = actif ? g.x(actif.jour) : 0;
  const bulleAGauche = actif ? xs > largeur * 0.6 : false;
  const rendement = (v: number) => (capitalInitial ? v / capitalInitial - 1 : null);

  return (
    <figure className="courbe">
      <figcaption className="courbe-legende">
        <span><i className="cle cle-pf" aria-hidden="true" />Votre portefeuille</span>
        {g.reference && <span><i className="cle cle-ref" aria-hidden="true" />{nomReference}, au même capital de départ</span>}
        <span className="discret">Les deux courbes partent du capital initial ({montant(capitalInitial)}).</span>
      </figcaption>
      <div ref={zone} className="courbe-zone" style={{ height: hauteur }}>
        <svg
          width={largeur} height={hauteur} role="img" tabIndex={0}
          aria-label={`Courbe de la valeur du portefeuille : ${montant(dernier.equity)} au dernier point, ${pctSigne(rendement(dernier.equity))} depuis le départ. Flèches gauche et droite pour parcourir les valeurs.`}
          onPointerMove={surPointeur} onPointerLeave={() => setSurvol(null)} onKeyDown={surClavier} onBlur={() => setSurvol(null)}
        >
          {g.graduations.map((v) => (
            <g key={v}>
              <line x1={MARGE.gauche} x2={largeur - MARGE.droite} y1={g.y(v)} y2={g.y(v)} className="courbe-grille" />
              <text x={MARGE.gauche - 8} y={g.y(v)} dy="0.32em" textAnchor="end" className="courbe-axe">{compact(v)}</text>
            </g>
          ))}
          {g.dates.map((d, i) => (
            <text key={`${d.texte}-${i}`} x={d.x} y={hauteur - 6} textAnchor={i === 0 ? "start" : i === g.dates.length - 1 ? "end" : "middle"} className="courbe-axe">
              {d.texte}
            </text>
          ))}
          <line x1={MARGE.gauche} x2={largeur - MARGE.droite} y1={g.y(capitalInitial)} y2={g.y(capitalInitial)} className="courbe-base" />
          <path d={g.aire} className="courbe-aire" />
          {g.reference && <path d={g.reference} className="courbe-ref" />}
          <path d={g.ligne} className="courbe-pf" />
          <circle cx={g.x(dernier.jour)} cy={g.y(dernier.equity)} r={4} className="courbe-point" />
          {actif && (
            <g>
              <line x1={xs} x2={xs} y1={MARGE.haut} y2={MARGE.haut + g.h} className="courbe-repere" />
              {actif.benchmark !== null && <circle cx={xs} cy={g.y(actif.benchmark)} r={4} className="courbe-point courbe-point-ref" />}
              <circle cx={xs} cy={g.y(actif.equity)} r={4} className="courbe-point" />
            </g>
          )}
        </svg>
        {actif && (
          <div className="courbe-bulle" style={bulleAGauche ? { right: largeur - xs + 12 } : { left: xs + 12 }} role="status">
            <p className="courbe-bulle-date">{JOUR.format(ms(actif.jour))}</p>
            <p><i className="cle cle-pf" aria-hidden="true" /><strong>{montant(actif.equity)}</strong> <span>portefeuille ({pctSigne(rendement(actif.equity))})</span></p>
            {actif.benchmark !== null && (
              <p><i className="cle cle-ref" aria-hidden="true" /><strong>{montant(actif.benchmark)}</strong> <span>{nomReference} ({pctSigne(rendement(actif.benchmark))})</span></p>
            )}
            <p className="discret">Liquidités : {montant(actif.cash)}</p>
          </div>
        )}
      </div>

      {tableau && (
        <div className="courbe-tableau">
          <button className="lien" aria-expanded={enTableau} onClick={() => setEnTableau(!enTableau)}>
            {enTableau ? "Masquer le tableau des valeurs" : "Afficher les valeurs en tableau"}
          </button>
          {enTableau && (
            <div className="tableau-defile">
              <table className="tableau">
                <caption className="sr-only">Valeur du portefeuille jour par jour (les 60 derniers jours)</caption>
                <thead><tr><th>Jour</th><th>Portefeuille</th><th>{nomReference}</th><th>Liquidités</th></tr></thead>
                <tbody>
                  {[...points].slice(-60).reverse().map((p) => (
                    <tr key={p.jour}><td>{JOUR.format(ms(p.jour))}</td><td>{montant(p.equity)}</td><td>{p.benchmark === null ? "–" : montant(p.benchmark)}</td><td>{montant(p.cash)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </figure>
  );
}
