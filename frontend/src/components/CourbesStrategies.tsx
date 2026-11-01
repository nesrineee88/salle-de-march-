"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { pctSigne } from "@/lib/format";
import type { ResultatStrategie } from "@/lib/types";

/** Couleur et trait de chaque courbe : la référence est grise ; les autres suivent la palette validée.
 *  Le trait (plein, tirets…) double la couleur pour que rien ne repose sur la couleur seule. */
export const TRAITS = ["", "6 3", "2 3", "8 3 2 3", "10 4", "1 3"];
export function styleSerie(nom: string, rang: number): { couleur: string; trait: string } {
  if (nom === "achat_conservation") return { couleur: "var(--ref)", trait: "" };
  return { couleur: `var(--serie-${(rang % 6) + 1})`, trait: TRAITS[rang % TRAITS.length] };
}

const MARGE = { haut: 12, droite: 16, bas: 24, gauche: 52 };
const MOIS = new Intl.DateTimeFormat("fr-FR", { month: "short", year: "2-digit", timeZone: "UTC" });
const JOUR = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const ms = (jour: string) => Date.parse(`${jour}T00:00:00Z`);

function pasLisible(brut: number): number {
  const p = 10 ** Math.floor(Math.log10(brut));
  const f = brut / p;
  return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p;
}

interface Props {
  strategies: ResultatStrategie[];
  masquees: Set<string>;
  hauteur?: number;
}

/** Valeur de 100 investis au départ, pour chaque stratégie. Les jours sont ceux de la première courbe (toutes partagent le même calendrier). */
export default function CourbesStrategies({ strategies, masquees, hauteur = 320 }: Props) {
  const zone = useRef<HTMLDivElement>(null);
  const [largeur, setLargeur] = useState(720);
  const [survol, setSurvol] = useState<number | null>(null);

  useEffect(() => {
    if (!zone.current) return;
    const obs = new ResizeObserver(([e]) => setLargeur(Math.max(300, e.contentRect.width)));
    obs.observe(zone.current);
    return () => obs.disconnect();
  }, []);

  const visibles = strategies.filter((s) => !masquees.has(s.nom));
  const dates = strategies[0]?.courbe.dates ?? [];

  const g = useMemo(() => {
    if (dates.length < 2 || visibles.length === 0) return null;
    const t0 = ms(dates[0]), t1 = ms(dates[dates.length - 1]);
    const vals = visibles.flatMap((s) => s.courbe.valeurs.map((v) => v * 100)).concat(100);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pas = pasLisible((hi - lo || hi * 0.1 || 1) / 4);
    lo = Math.floor(lo / pas) * pas; hi = Math.ceil(hi / pas) * pas;
    const w = largeur - MARGE.gauche - MARGE.droite, h = hauteur - MARGE.haut - MARGE.bas;
    const xi = (i: number) => MARGE.gauche + (dates.length === 1 ? 0 : (i / (dates.length - 1)) * w);
    const y = (v: number) => MARGE.haut + (1 - (v - lo) / (hi - lo)) * h;
    const graduations: number[] = [];
    for (let v = lo; v <= hi + pas / 2; v += pas) graduations.push(v);
    const nbDates = largeur < 520 ? 3 : 5;
    const reperes: { x: number; texte: string }[] = [];
    for (let k = 0; k < nbDates; k++) {
      const i = Math.round((k * (dates.length - 1)) / (nbDates - 1));
      const texte = MOIS.format(ms(dates[i]));
      if (!reperes.length || reperes[reperes.length - 1].texte !== texte) reperes.push({ x: xi(i), texte });
    }
    const traces = visibles.map((s) => {
      let d = "";
      s.courbe.valeurs.forEach((v, i) => { d += `${i ? "L" : "M"}${xi(i).toFixed(1)},${y(v * 100).toFixed(1)}`; });
      return d;
    });
    return { xi, y, graduations, reperes, traces, h, w, ordre: strategies.map((s) => s.nom) };
  }, [dates, visibles, largeur, hauteur, strategies]);

  if (!g) {
    return <p className="vide" role="status">{visibles.length === 0 ? "Toutes les courbes sont masquées : réactivez-en une dans la légende." : "Pas assez de jours pour tracer une courbe."}</p>;
  }

  const n = dates.length;
  function surPointeur(e: React.PointerEvent<SVGSVGElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - r.left - MARGE.gauche) / g!.w;
    setSurvol(Math.max(0, Math.min(n - 1, Math.round(frac * (n - 1)))));
  }
  function surClavier(e: React.KeyboardEvent) {
    const pas = e.shiftKey ? 20 : 1;
    if (e.key === "ArrowLeft") { e.preventDefault(); setSurvol((s) => Math.max(0, (s ?? n) - pas)); }
    else if (e.key === "ArrowRight") { e.preventDefault(); setSurvol((s) => Math.min(n - 1, (s ?? -1) + pas)); }
    else if (e.key === "Home") { e.preventDefault(); setSurvol(0); }
    else if (e.key === "End") { e.preventDefault(); setSurvol(n - 1); }
    else if (e.key === "Escape") setSurvol(null);
  }

  const xs = survol !== null ? g.xi(survol) : 0;
  const aGauche = survol !== null && xs > largeur * 0.6;
  const resume = visibles.map((s) => `${s.libelle} ${pctSigne(s.courbe.valeurs[n - 1] - 1)}`).join(", ");

  return (
    <div ref={zone} className="courbe-zone" style={{ height: hauteur }}>
      <svg
        width={largeur} height={hauteur} role="img" tabIndex={0}
        aria-label={`Valeur de 100 investis au départ. Résultat final : ${resume}. Flèches gauche et droite pour parcourir les jours, Maj pour aller plus vite.`}
        onPointerMove={surPointeur} onPointerLeave={() => setSurvol(null)} onKeyDown={surClavier} onBlur={() => setSurvol(null)}
      >
        {g.graduations.map((v) => (
          <g key={v}>
            <line x1={MARGE.gauche} x2={largeur - MARGE.droite} y1={g.y(v)} y2={g.y(v)} className="courbe-grille" />
            <text x={MARGE.gauche - 8} y={g.y(v)} dy="0.32em" textAnchor="end" className="courbe-axe">{v.toLocaleString("fr-FR", { maximumFractionDigits: 0 })}</text>
          </g>
        ))}
        {g.reperes.map((d, i) => (
          <text key={`${d.texte}-${i}`} x={d.x} y={hauteur - 6} textAnchor={i === 0 ? "start" : i === g.reperes.length - 1 ? "end" : "middle"} className="courbe-axe">{d.texte}</text>
        ))}
        <line x1={MARGE.gauche} x2={largeur - MARGE.droite} y1={g.y(100)} y2={g.y(100)} className="courbe-base" />
        {visibles.map((s, k) => {
          const st = styleSerie(s.nom, g.ordre.filter((x) => x !== "achat_conservation").indexOf(s.nom));
          return <path key={s.nom} d={g.traces[k]} fill="none" stroke={st.couleur} strokeWidth={s.nom === "achat_conservation" ? 2 : 2.25}
            strokeDasharray={st.trait || undefined} strokeLinejoin="round" strokeLinecap="round" />;
        })}
        {survol !== null && (
          <g>
            <line x1={xs} x2={xs} y1={MARGE.haut} y2={MARGE.haut + g.h} className="courbe-repere" />
            {visibles.map((s) => {
              const st = styleSerie(s.nom, g.ordre.filter((x) => x !== "achat_conservation").indexOf(s.nom));
              return <circle key={s.nom} cx={xs} cy={g.y(s.courbe.valeurs[survol] * 100)} r={4} fill={st.couleur} stroke="var(--nuit-2)" strokeWidth={2} />;
            })}
          </g>
        )}
      </svg>
      {survol !== null && (
        <div className="courbe-bulle" style={aGauche ? { right: largeur - xs + 12 } : { left: xs + 12 }} role="status">
          <p className="courbe-bulle-date">{JOUR.format(ms(dates[survol]))}</p>
          {visibles.map((s) => {
            const st = styleSerie(s.nom, g.ordre.filter((x) => x !== "achat_conservation").indexOf(s.nom));
            const v = s.courbe.valeurs[survol];
            return (
              <p key={s.nom}>
                <i className="cle" style={{ background: st.couleur }} aria-hidden="true" />
                <strong>{(v * 100).toLocaleString("fr-FR", { maximumFractionDigits: 1 })}</strong> <span>{s.libelle} ({pctSigne(v - 1)})</span>
              </p>
            );
          })}
        </div>
      )}
    </div>
  );
}
