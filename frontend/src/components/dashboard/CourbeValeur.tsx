"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { dateCourte, entier, pctSigne } from "@/lib/format";
import type { PointValeur } from "@/lib/types";

const AXE = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", timeZone: "UTC" });
const AXE_LONG = new Intl.DateTimeFormat("fr-FR", { month: "short", year: "numeric", timeZone: "UTC" });
const ms = (jour: string) => Date.parse(`${jour}T00:00:00Z`);
const MAX_POINTS = 600;
const GAUCHE = 8, DROITE = 64, HAUT = 12, BAS = 24;

function graduations(bas: number, haut: number, n: number): number[] {
  const brut = (haut - bas) / n || 1;
  const p = 10 ** Math.floor(Math.log10(brut));
  const pas = [1, 2, 2.5, 5, 10].map((x) => x * p).find((x) => x >= brut) ?? brut;
  const out: number[] = [];
  for (let v = Math.ceil(bas / pas) * pas; v <= haut + pas * 1e-6; v += pas) out.push(v);
  return out;
}

/** Portefeuille contre référence, même départ. L'avenir est hachuré ; lecture au survol ou aux flèches du clavier. */
export default function CourbeValeur({ points, nomReference, futur }: { points: PointValeur[]; nomReference: string; futur: boolean }) {
  const zone = useRef<HTMLDivElement>(null);
  const [taille, setTaille] = useState({ l: 640, h: 260 });
  const [survol, setSurvol] = useState<number | null>(null);

  useEffect(() => {
    if (!zone.current) return;
    const o = new ResizeObserver(([e]) => setTaille({ l: Math.max(220, e.contentRect.width), h: Math.max(160, e.contentRect.height) }));
    o.observe(zone.current);
    return () => o.disconnect();
  }, []);

  const g = useMemo(() => {
    if (points.length < 2) return null;
    const pas = Math.ceil(points.length / MAX_POINTS);
    const pts = points.filter((_, i) => i % pas === 0 || i === points.length - 1);
    const base = pts[0].equity;
    const ref0 = pts[0].benchmark;
    const refs = pts.map((p) => (ref0 && p.benchmark !== null ? (p.benchmark / ref0) * base : null));
    const tout = [...pts.map((p) => p.equity), ...refs.filter((v): v is number => v !== null), base];
    let bas = Math.min(...tout), haut = Math.max(...tout);
    const marge = (haut - bas || base * 0.02) * 0.1;
    bas -= marge; haut += marge;
    const largeurFutur = futur ? Math.min(74, taille.l * 0.12) : 0;
    const utile = taille.l - GAUCHE - DROITE - largeurFutur;
    const t0 = ms(pts[0].jour), t1 = ms(pts[pts.length - 1].jour);
    const xs = pts.map((p) => GAUCHE + ((ms(p.jour) - t0) / (t1 - t0 || 1)) * utile);
    const y = (v: number) => HAUT + ((haut - v) / (haut - bas)) * (taille.h - HAUT - BAS);
    const tracer = (vals: (number | null)[]) => {
      let d = "";
      vals.forEach((v, i) => { if (v !== null) d += `${d ? "L" : "M"}${xs[i].toFixed(1)},${y(v).toFixed(1)}`; });
      return d;
    };
    const format = t1 - t0 > 250 * 86_400_000 ? AXE_LONG : AXE;
    const n = Math.max(1, Math.min(5, Math.floor(utile / 100)));
    const dates: { x: number; texte: string }[] = [];
    for (let i = 0; i <= n; i++) {
      const texte = format.format(t0 + ((t1 - t0) * i) / n);
      if (dates[dates.length - 1]?.texte !== texte) dates.push({ x: GAUCHE + (utile * i) / n, texte });
    }
    const ligne = tracer(pts.map((p) => p.equity));
    const fin = GAUCHE + utile;
    const sol = taille.h - BAS;
    return {
      pts, refs, base, xs, y, dates, ligne, fin, largeurFutur, sol,
      aire: `${ligne}L${xs[xs.length - 1]},${sol}L${xs[0]},${sol}Z`,
      reference: tracer(refs),
      paliers: graduations(bas, haut, Math.max(2, Math.floor(taille.h / 65))),
    };
  }, [points, taille, futur]);

  const i = g && survol !== null ? Math.min(survol, g.pts.length - 1) : null;

  function viser(e: React.PointerEvent<SVGSVGElement>) {
    if (!g) return;
    const x = e.clientX - e.currentTarget.getBoundingClientRect().left;
    let meilleur = 0, ecart = Infinity;
    g.xs.forEach((v, k) => { const d = Math.abs(v - x); if (d < ecart) { ecart = d; meilleur = k; } });
    setSurvol(meilleur);
  }
  function clavier(e: React.KeyboardEvent) {
    if (!g) return;
    const dernier = g.pts.length - 1;
    if (e.key === "ArrowLeft") { e.preventDefault(); setSurvol((s) => Math.max(0, (s ?? dernier) - 1)); }
    else if (e.key === "ArrowRight") { e.preventDefault(); setSurvol((s) => Math.min(dernier, (s ?? -1) + 1)); }
    else if (e.key === "Escape") setSurvol(null);
  }

  return (
    <div className="dash-courbe" ref={zone}>
      {!g ? <p className="dash-vide">La courbe commence le lendemain de votre première transaction.</p> : (
        <svg width={taille.l} height={taille.h} role="img" tabIndex={0} onPointerMove={viser} onPointerLeave={() => setSurvol(null)}
          onKeyDown={clavier} onBlur={() => setSurvol(null)}
          aria-label={`Valeur du portefeuille : ${entier(g.pts[g.pts.length - 1].equity)} USD, ${pctSigne(g.pts[g.pts.length - 1].equity / g.base - 1)} sur la période affichée. Flèches pour parcourir.`}>
          <defs>
            <pattern id="dash-hachures" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(25)">
              <rect width="2" height="7" className="dash-hachure" />
            </pattern>
          </defs>
          {g.paliers.map((v) => (
            <g key={v}>
              <line x1={GAUCHE} x2={taille.l - DROITE} y1={g.y(v)} y2={g.y(v)} className="dash-grille" />
              <text x={taille.l - DROITE + 8} y={g.y(v) + 4}>{entier(v)}</text>
            </g>
          ))}
          {futur && (
            <g>
              <rect x={g.fin + 5} y={0} width={Math.max(0, g.largeurFutur - 5)} height={g.sol} fill="url(#dash-hachures)" />
              <line x1={g.fin + 5} x2={g.fin + 5} y1={0} y2={g.sol} className="dash-present" />
              {g.largeurFutur >= 56 && <text x={g.fin + g.largeurFutur / 2 + 3} y={18} textAnchor="middle">Avenir</text>}
            </g>
          )}
          <path d={g.aire} className="dash-aire" />
          {g.reference && <path d={g.reference} className="dash-ref" />}
          <path d={g.ligne} className="dash-pf" />
          <circle cx={g.xs[g.xs.length - 1]} cy={g.y(g.pts[g.pts.length - 1].equity)} r={4} className="dash-point" />
          {g.dates.map((d, k) => (
            <text key={d.texte} x={d.x} y={taille.h - 6} textAnchor={k === 0 ? "start" : k === g.dates.length - 1 ? "end" : "middle"}>{d.texte}</text>
          ))}
          {i !== null && <line x1={g.xs[i]} x2={g.xs[i]} y1={HAUT} y2={g.sol} className="dash-viseur" />}
        </svg>
      )}
      {g && i !== null && (
        <div className="dash-bulle" style={g.xs[i] > taille.l / 2 ? { right: taille.l - g.xs[i] + 12 } : { left: g.xs[i] + 12 }}>
          <strong>{dateCourte(`${g.pts[i].jour}T00:00:00`)}</strong>
          <p><span>Portefeuille</span><b>{entier(g.pts[i].equity)}</b></p>
          {g.refs[i] !== null && <p><span>{nomReference}</span><b>{entier(g.refs[i]!)}</b></p>}
        </div>
      )}
    </div>
  );
}
