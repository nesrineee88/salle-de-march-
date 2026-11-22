"use client";

import { useEffect, useMemo, useState } from "react";
import { ErreurApi, api } from "@/lib/api";
import { dateCourte, nombre } from "@/lib/format";
import { useMarche } from "../Contexte";
import { Jauge, type TestSignal } from "./LectureTechnique";

interface Sentiment {
  symbole: string; nom: string; requete: string | null; source: string;
  dernier_jour: string; premier_jour: string; jours: number; ton_7_jours: number; ton_annee: number; ecart_type_annee: number;
  horizon: number; test: TestSignal & { seuil?: number; correlation?: number };
  serie: { date: string; ton: number }[]; prix: { date: string; close: number }[];
}

const jour = (iso: string) => dateCourte(`${iso}T12:00:00`);
const L = 1000, H_PRIX = 110, H_TON = 70;

function Graphique({ s }: { s: Sentiment }) {
  const g = useMemo(() => {
    const t0 = Date.parse(s.serie[0].date), t1 = Date.parse(s.serie[s.serie.length - 1].date) || t0 + 1;
    const x = (d: string) => ((Date.parse(d) - t0) / (t1 - t0 || 1)) * L;
    const p = s.prix.filter((q) => q.date >= s.serie[0].date && q.date <= s.serie[s.serie.length - 1].date);
    const lo = Math.min(...p.map((q) => q.close)), hi = Math.max(...p.map((q) => q.close));
    const prix = p.map((q, i) => `${i ? "L" : "M"}${x(q.date).toFixed(1)},${(6 + (1 - (q.close - lo) / (hi - lo || 1)) * (H_PRIX - 12)).toFixed(1)}`).join("");
    const m = Math.max(0.5, ...s.serie.map((q) => Math.abs(q.ton)));
    const barres = s.serie.map((q) => ({ x: x(q.date), h: (Math.abs(q.ton) / m) * (H_TON / 2 - 2), neg: q.ton < 0 }));
    return { prix, barres, lo, hi };
  }, [s]);
  return (
    <figure className="lecture-graphe">
      <figcaption><span>Cours</span><small>{nombre(g.lo, 2)} à {nombre(g.hi, 2)}</small></figcaption>
      <svg viewBox={`0 0 ${L} ${H_PRIX}`} preserveAspectRatio="none" role="img" aria-label="Cours de l’actif sur la période"><path d={g.prix} className="lecture-trace" vectorEffect="non-scaling-stroke" /></svg>
      <figcaption><span>Ton de la presse, par jour</span><small>au-dessus de la ligne : positif · en dessous : négatif</small></figcaption>
      <svg viewBox={`0 0 ${L} ${H_TON}`} preserveAspectRatio="none" role="img" aria-label="Ton quotidien de la presse">
        <line x1="0" x2={L} y1={H_TON / 2} y2={H_TON / 2} className="lecture-zero" vectorEffect="non-scaling-stroke" />
        {g.barres.map((b, i) => <rect key={i} x={b.x} width={Math.max(1.2, L / g.barres.length - 0.6)} y={b.neg ? H_TON / 2 : H_TON / 2 - b.h} height={b.h} className={b.neg ? "lecture-neg" : "lecture-pos"} />)}
      </svg>
      <p className="lecture-axe"><span>{jour(s.serie[0].date)}</span><span>{jour(s.serie[s.serie.length - 1].date)}</span></p>
    </figure>
  );
}

export default function LectureSentiment({ symbole }: { symbole: string }) {
  const { inst } = useMarche();
  const [s, setS] = useState<Sentiment | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const jourCompte = (inst?.instant_compte ?? inst?.instant)?.slice(0, 10);

  useEffect(() => {
    let actif = true;
    setErreur(null);
    api<Sentiment>(`/api/v1/lecture/sentiment/${encodeURIComponent(symbole)}`)
      .then((d) => { if (actif) setS(d); })
      .catch((e) => { if (actif) { setS(null); setErreur(e instanceof Error ? e.message : "Lecture impossible."); } });
    return () => { actif = false; };
  }, [symbole, jourCompte]);

  if (erreur) return <p className="lecture-alerte" role="alert">{erreur}</p>;
  if (!s || s.symbole !== symbole) return <p className="lecture-petit" role="status">Lecture du ton de la presse…</p>;
  const ecart = s.ecart_type_annee > 0 ? (s.ton_7_jours - s.ton_annee) / s.ecart_type_annee : 0;
  const humeur = ecart <= -1 ? "nettement plus négative que d’habitude" : ecart < -0.3 ? "un peu plus négative que d’habitude"
    : ecart >= 1 ? "nettement plus positive que d’habitude" : ecart > 0.3 ? "un peu plus positive que d’habitude" : "dans ses habitudes";

  return (
    <div className="lecture-corps">
      <section className="lecture-synthese">
        <p className="lecture-sur">{s.nom}, presse jusqu’au {jour(s.dernier_jour)}</p>
        <p className="lecture-grand">{nombre(s.ton_7_jours, 2)}</p>
        <p>Ton moyen des 7 derniers jours. Sur un an, la moyenne est de {nombre(s.ton_annee, 2)} : la presse est <strong>{humeur}</strong>.</p>
        <p className="lecture-petit">Requête : {s.requete}. {s.jours} jours de presse depuis le {jour(s.premier_jour)}.</p>
      </section>
      <section className="lecture-carte">
        <h2>Le ton et le cours, sur un an</h2>
        <Graphique s={s} />
      </section>
      <section className="lecture-carte">
        <h2>La presse négative annonce-t-elle la baisse ?</h2>
        <p>On prend les jours de presse la plus négative (les 20 % les plus bas{s.test.seuil !== undefined ? `, ton sous ${nombre(s.test.seuil, 2)}` : ""}) et on regarde le prix {s.horizon} séances plus tard.</p>
        <Jauge t={s.test} horizon={s.horizon} />
        {s.test.correlation !== undefined && <p className="lecture-petit">Corrélation entre le ton du jour et le rendement des {s.horizon} séances suivantes : {nombre(s.test.correlation, 3)} (0 = aucun lien).</p>}
      </section>
      <p className="lecture-petit">
        Source : {s.source}. Le ton compte les mots positifs et négatifs des articles qui citent la requête : il ne comprend ni l’ironie ni le contexte,
        et un article peut parler d’autre chose. Le sentiment suit souvent le prix au lieu de l’annoncer. Reddit n’est pas utilisé : son robots.txt interdit la collecte.
      </p>
    </div>
  );
}
