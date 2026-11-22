"use client";

import { useEffect, useMemo, useState } from "react";
import { ErreurApi, api } from "@/lib/api";
import { dateCourte, nombre, pct } from "@/lib/format";
import { useMarche } from "../Contexte";

export interface TestSignal {
  n: number; verdict: "bruit" | "plus_souvent_hausse" | "plus_souvent_baisse" | "trop_peu";
  n_independantes?: number; taux?: number; base?: number; marge?: number; moyenne?: number; moyenne_base?: number;
}
interface Signal { cle: string; nom: string; mesure: string; etat: string; phrase: string; valeurs: Record<string, number>; test: TestSignal }
type Serie = (number | null)[];
interface Courbes {
  dates: string[]; prix: Serie; moyenne_50: Serie; moyenne_200: Serie; bande_haute: Serie; bande_basse: Serie;
  rsi: Serie; macd: Serie; signal: Serie; volume: Serie; volume_moyen_20: Serie;
}
interface Lecture {
  symbole: string; nom: string; date: string; seances: number; premiere: string; horizon: number;
  prix: number; plus_bas_60: number; plus_haut_60: number; signaux: Signal[]; courbes: Courbes;
}

const jour = (iso: string) => dateCourte(`${iso}T12:00:00`);
const W = 600;

function echelle(series: Serie[], h: number, marge = 4) {
  const v = series.flat().filter((x): x is number => x !== null);
  const lo = Math.min(...v), hi = Math.max(...v);
  return (x: number) => marge + (1 - (x - lo) / (hi - lo || 1)) * (h - 2 * marge);
}
function trace(s: Serie, y: (v: number) => number) {
  const pas = W / Math.max(1, s.length - 1);
  let d = "", ouvert = false;
  s.forEach((v, i) => {
    if (v === null) { ouvert = false; return; }
    d += `${ouvert ? "L" : "M"}${(i * pas).toFixed(1)},${y(v).toFixed(1)}`;
    ouvert = true;
  });
  return d;
}

/** Bande fermée : le bord haut de gauche à droite, puis le bord bas de droite à gauche, aux mêmes abscisses. */
function bande(haute: Serie, basse: Serie, y: (v: number) => number) {
  const pas = W / Math.max(1, haute.length - 1);
  const i = haute.map((_, k) => k).filter((k) => haute[k] !== null && basse[k] !== null);
  if (i.length < 2) return "";
  const haut = i.map((k, n) => `${n ? "L" : "M"}${(k * pas).toFixed(1)},${y(haute[k] as number).toFixed(1)}`).join("");
  const bas = [...i].reverse().map((k) => `L${(k * pas).toFixed(1)},${y(basse[k] as number).toFixed(1)}`).join("");
  return `${haut}${bas}Z`;
}

/** Le verdict en un coup d'œil : la zone du hasard, et où tombe le signal. */
export function Jauge({ t, horizon }: { t: TestSignal; horizon: number }) {
  if (t.verdict === "trop_peu" || t.taux === undefined || t.base === undefined || t.marge === undefined) {
    return <p className="lecture-jauge" data-verdict="trop_peu"><b>?</b> Trop peu d’historique</p>;
  }
  const mot = t.verdict === "bruit" ? "Comme le hasard" : t.verdict === "plus_souvent_hausse" ? "A servi : hausse" : "A servi : baisse";
  return (
    <div className="lecture-jauge" data-verdict={t.verdict}>
      <p><b aria-hidden="true">{t.verdict === "bruit" ? "≈" : t.verdict === "plus_souvent_hausse" ? "▲" : "▼"}</b>{mot}</p>
      <i role="img" aria-label={`Hausse ${horizon} séances après : ${pct(t.taux, 0)} contre ${pct(t.base, 0)} d’habitude, marge ${pct(t.marge, 0)}`}>
        <span style={{ left: `${Math.max(0, t.base - t.marge) * 100}%`, width: `${Math.min(1, 2 * t.marge) * 100}%` }} />
        <em style={{ left: `${t.base * 100}%` }} />
        <b style={{ left: `${t.taux * 100}%` }} />
      </i>
      <small><span>0 %</span><span>hausse à {horizon} séances</span><span>100 %</span></small>
    </div>
  );
}

function Mini({ cle, c }: { cle: string; c: Courbes }) {
  const h = 70;
  if (cle === "rsi") {
    const y = (v: number) => 4 + (1 - v / 100) * (h - 8);
    return (
      <svg viewBox={`0 0 ${W} ${h}`} preserveAspectRatio="none" aria-hidden="true">
        <rect x="0" width={W} y={y(100)} height={y(70) - y(100)} className="lecture-zone-haut" />
        <rect x="0" width={W} y={y(30)} height={y(0) - y(30)} className="lecture-zone-bas" />
        <path d={trace(c.rsi, y)} className="lecture-trace lecture-dessin" vectorEffect="non-scaling-stroke" />
      </svg>
    );
  }
  if (cle === "macd") {
    const hist = c.macd.map((m, i) => (m === null || c.signal[i] === null ? null : m - (c.signal[i] as number)));
    const m = Math.max(...hist.map((x) => Math.abs(x ?? 0)), 1e-9), pas = W / hist.length;
    return (
      <svg viewBox={`0 0 ${W} ${h}`} preserveAspectRatio="none" aria-hidden="true">
        <line x1="0" x2={W} y1={h / 2} y2={h / 2} className="lecture-zero" vectorEffect="non-scaling-stroke" />
        {hist.map((x, i) => x === null ? null : (
          <rect key={i} x={i * pas} width={Math.max(1, pas - 1)} y={x >= 0 ? h / 2 - (x / m) * (h / 2 - 3) : h / 2} height={Math.abs(x / m) * (h / 2 - 3)}
            className={`lecture-barre ${x >= 0 ? "lecture-pos" : "lecture-neg"}`} style={{ animationDelay: `${i * 6}ms` }} />
        ))}
      </svg>
    );
  }
  if (cle === "volume") {
    const m = Math.max(...c.volume.map((x) => x ?? 0), 1), pas = W / c.volume.length;
    const y = (v: number) => h - (v / m) * (h - 4);
    return (
      <svg viewBox={`0 0 ${W} ${h}`} preserveAspectRatio="none" aria-hidden="true">
        {c.volume.map((v, i) => v === null ? null : (
          <rect key={i} x={i * pas} width={Math.max(1, pas - 1)} y={y(v)} height={h - y(v)}
            className={`lecture-barre ${(c.volume_moyen_20[i] ?? Infinity) * 1.5 < v ? "lecture-fort" : "lecture-calme"}`} style={{ animationDelay: `${i * 6}ms` }} />
        ))}
        <path d={trace(c.volume_moyen_20, y)} className="lecture-trace-2" vectorEffect="non-scaling-stroke" />
      </svg>
    );
  }
  const series = cle === "bollinger" ? [c.prix, c.bande_haute, c.bande_basse] : [c.prix, c.moyenne_50, c.moyenne_200];
  const y = echelle(series, h);
  return (
    <svg viewBox={`0 0 ${W} ${h}`} preserveAspectRatio="none" aria-hidden="true">
      {cle === "bollinger" && <path d={bande(c.bande_haute, c.bande_basse, y)} className="lecture-bande" />}
      {cle === "tendance" && <path d={trace(c.moyenne_200, y)} className="lecture-trace-2" vectorEffect="non-scaling-stroke" />}
      {cle === "croisement" && <><path d={trace(c.moyenne_50, y)} className="lecture-trace-3" vectorEffect="non-scaling-stroke" /><path d={trace(c.moyenne_200, y)} className="lecture-trace-2" vectorEffect="non-scaling-stroke" /></>}
      {cle !== "croisement" && <path d={trace(c.prix, y)} className="lecture-trace lecture-dessin" vectorEffect="non-scaling-stroke" />}
    </svg>
  );
}

const LEGENDES: Record<string, [string, string][]> = {
  tendance: [["lecture-c1", "Prix"], ["lecture-c2", "Moyenne 200"]],
  croisement: [["lecture-c3", "Moyenne 50"], ["lecture-c2", "Moyenne 200"]],
  rsi: [["lecture-c1", "RSI"], ["lecture-c4", "zones 30 et 70"]],
  macd: [["lecture-c5", "élan haussier"], ["lecture-c6", "élan baissier"]],
  bollinger: [["lecture-c1", "Prix"], ["lecture-c4", "bandes"]],
  volume: [["lecture-c5", "volume fort"], ["lecture-c2", "moyenne 20"]],
};

export default function LectureTechnique({ symbole }: { symbole: string }) {
  const { inst } = useMarche();
  const [l, setL] = useState<Lecture | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const jourCompte = (inst?.instant_compte ?? inst?.instant)?.slice(0, 10);

  useEffect(() => {
    let actif = true;
    setErreur(null);
    api<Lecture>(`/api/v1/lecture/technique/${encodeURIComponent(symbole)}`)
      .then((d) => { if (actif) setL(d); })
      .catch((e) => {
        if (!actif) return;
        setL(null);
        setErreur(e instanceof ErreurApi && e.statut === 404 ? "Le serveur Python ne connaît pas encore cette page : redémarrez-le."
          : e instanceof Error ? e.message : "Lecture impossible.");
      });
    return () => { actif = false; };
  }, [symbole, jourCompte]);

  const grand = useMemo(() => {
    if (!l) return null;
    const c = l.courbes, h = 220;
    const y = echelle([c.prix, c.bande_haute, c.bande_basse, c.moyenne_50, c.moyenne_200], h, 8);
    return {
      h,
      bande: bande(c.bande_haute, c.bande_basse, y),
      prix: trace(c.prix, y), m50: trace(c.moyenne_50, y), m200: trace(c.moyenne_200, y),
      dernier: y(c.prix[c.prix.length - 1] ?? 0),
    };
  }, [l]);

  if (erreur) return <p className="lecture-alerte" role="alert">{erreur}</p>;
  if (!l || l.symbole !== symbole || !grand) return <p className="lecture-petit" role="status">Lecture des séances passées…</p>;
  const juges = l.signaux.filter((s) => s.test.verdict !== "trop_peu");
  const servis = juges.filter((s) => s.test.verdict !== "bruit").length;
  const var60 = l.prix / (l.courbes.prix[Math.max(0, l.courbes.prix.length - 61)] ?? l.prix) - 1;

  return (
    <div className="lecture-corps" key={`${symbole}-${l.date}`}>
      <section className="lecture-scene">
        <header>
          <div>
            <p className="lecture-sur">{l.nom} · {jour(l.date)}</p>
            <p className="lecture-grand">{nombre(l.prix, 2)} <span className={var60 >= 0 ? "gain" : "perte"}>{var60 >= 0 ? "▲" : "▼"} {pct(Math.abs(var60), 1)} <small>sur 60 séances</small></span></p>
          </div>
          <div className="lecture-score" role="img" aria-label={`${servis} indicateur sur ${juges.length} a fait mieux que le hasard`}>
            <ul>{l.signaux.map((s, i) => <li key={s.cle} data-verdict={s.test.verdict} style={{ animationDelay: `${300 + i * 120}ms` }} title={s.nom} />)}</ul>
            <p><strong>{servis}/{juges.length}</strong> ont battu le hasard</p>
          </div>
        </header>
        <svg className="lecture-grand-graphe" viewBox={`0 0 ${W} ${grand.h}`} preserveAspectRatio="none" role="img"
          aria-label={`Cours des ${l.courbes.dates.length} dernières séances avec moyennes et bandes de Bollinger`}>
          <path d={grand.bande} className="lecture-bande" />
          <path d={grand.m200} className="lecture-trace-2" vectorEffect="non-scaling-stroke" />
          <path d={grand.m50} className="lecture-trace-3" vectorEffect="non-scaling-stroke" />
          <path d={grand.prix} className="lecture-trace lecture-dessin" vectorEffect="non-scaling-stroke" />
          <circle cx={W} cy={grand.dernier} r="4" className="lecture-point" vectorEffect="non-scaling-stroke" />
        </svg>
        <p className="lecture-legende">
          <span><i className="lecture-c1" />Prix</span><span><i className="lecture-c3" />Moyenne 50</span>
          <span><i className="lecture-c2" />Moyenne 200</span><span><i className="lecture-c4" />Bandes de Bollinger</span>
          <span className="lecture-axe-texte">{jour(l.courbes.dates[0])} → {jour(l.date)}</span>
        </p>
      </section>

      <ul className="lecture-signaux">
        {l.signaux.map((s, i) => (
          <li key={s.cle} style={{ animationDelay: `${i * 80}ms` }}>
            <header>
              <h2>{s.nom}</h2>
              <span className="lecture-etat" data-etat={s.etat}>{s.etat}</span>
            </header>
            <div className="lecture-mini"><Mini cle={s.cle} c={l.courbes} /></div>
            <p className="lecture-legende lecture-legende-mini">{LEGENDES[s.cle]?.map(([c, t]) => <span key={t}><i className={c} />{t}</span>)}</p>
            <Jauge t={s.test} horizon={l.horizon} />
            <details className="lecture-pourquoi">
              <summary>Pourquoi ?</summary>
              <p>{s.phrase}</p>
              <p className="lecture-petit">{s.mesure}.</p>
              {s.test.taux !== undefined && s.test.base !== undefined && (
                <p className="lecture-petit">
                  Après cet état, hausse {l.horizon} séances plus tard {pct(s.test.taux, 0)} du temps, contre {pct(s.test.base, 0)} d’habitude,
                  marge ±{pct(s.test.marge ?? 0, 0)} ({s.test.n} cas, environ {nombre(s.test.n_independantes ?? 0, 0)} indépendants).
                </p>
              )}
            </details>
          </li>
        ))}
      </ul>
      <p className="lecture-petit">
        La barre grise est la zone du hasard, le trait la hausse habituelle, le curseur cyan le résultat du signal. Curseur dans la zone : le signal n’a pas servi.
        Séances terminées avant votre date seulement. Ce n’est pas un conseil.
      </p>
    </div>
  );
}
