"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Check, X } from "lucide-react";
import { dateCourte, entier, pct, pctSigne, signe } from "@/lib/format";
import type { Generique as TypeGenerique, Montage, Partie } from "./types";
import type { usePartie } from "./usePartie";

const ecartRond = (v: number) => `${signe(Math.round(v))}${entier(Math.abs(v))}`;

function Laurier() {
  return (
    <svg className="obscure-laurier" viewBox="0 0 120 54" aria-hidden="true">
      {Array.from({ length: 7 }, (_, i) => [1, -1].map((s) => {
        const t = ((80 - i * 15) * Math.PI) / 180;
        const x = (60 + s * (Math.cos(t) * 36 + 7)).toFixed(1), y = (24 + Math.sin(t) * 22).toFixed(1);
        return <ellipse key={`${i}${s}`} cx={x} cy={y} rx="7.5" ry="2.8" transform={`rotate(${s * (i * 12 - 30)} ${x} ${y})`} />;
      }))}
    </svg>
  );
}

interface Serie { classe: string; valeurs: number[] }

function Courbes({ series, arrets }: { series: Serie[]; arrets: number[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [l, setL] = useState(700);
  useEffect(() => {
    if (!ref.current) return;
    const o = new ResizeObserver(([e]) => setL(Math.max(240, e.contentRect.width)));
    o.observe(ref.current);
    return () => o.disconnect();
  }, []);
  const g = useMemo(() => {
    const h = 260, droite = 66, n = series[0].valeurs.length;
    const tout = series.flatMap((s) => s.valeurs);
    let bas = Math.min(...tout), haut = Math.max(...tout);
    const marge = (haut - bas || 1) * 0.1;
    bas -= marge; haut += marge;
    const x = (i: number) => 8 + (i * (l - 8 - droite)) / Math.max(1, n - 1);
    const y = (v: number) => 20 + ((haut - v) / (haut - bas)) * (h - 32);
    const paliers = [0.15, 0.5, 0.85].map((u) => Math.round((bas + (haut - bas) * u) / 1000) * 1000);
    return {
      h, x, y, paliers,
      traces: series.map((s) => ({ classe: s.classe, d: s.valeurs.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("") })),
    };
  }, [series, l]);
  return (
    <div ref={ref} className="obscure-courbes">
      <svg width={l} height={g.h} role="img" aria-label="Votre partie, votre double immobile et le montage alternatif choisi">
        {g.paliers.map((v, i) => (
          <g key={i}>
            <line x1="8" x2={l - 66} y1={g.y(v)} y2={g.y(v)} className="obscure-grille" />
            <text x={l - 60} y={g.y(v) + 4}>{entier(v)}</text>
          </g>
        ))}
        {arrets.map((j, i) => (
          <g key={i}>
            <line x1={g.x(j)} x2={g.x(j)} y1="20" y2={g.h - 10} className="obscure-repere" />
            <text x={g.x(j)} y="12" textAnchor="middle" className="obscure-repere-texte">{i + 1}</text>
          </g>
        ))}
        {g.traces.map((t) => <path key={t.classe} d={t.d} className={t.classe} />)}
      </svg>
    </div>
  );
}

function plusMarquant(montage: Montage[]): [number, number] {
  let choix: [number, number] = [0, 0];
  let max = -1;
  montage.forEach((m, k) => m.autres.forEach((a, i) => { if (Math.abs(a.ecart) > max) { max = Math.abs(a.ecart); choix = [k, i]; } }));
  return choix;
}

function MontageAlternatif({ partie, g }: { partie: Partie; g: TypeGenerique }) {
  const [[k, i], setChoix] = useState<[number, number]>(() => plusMarquant(g.montage));
  const etape = g.montage[k];
  const autre = etape?.autres[i];
  const jury = partie.mode === "jury";
  const series = useMemo(() => [
    { classe: "obscure-trace-double", valeurs: g.courbe_double },
    ...(autre ? [{ classe: "obscure-trace-autre", valeurs: autre.courbe }] : []),
    { classe: "obscure-trace-vous", valeurs: g.courbe },
  ], [g, autre]);
  if (!etape || !autre) return null;
  const quand = etape.date ? `le ${dateCourte(`${etape.date}T00:00:00`)}` : `à l’arrêt ${etape.arret + 1}`;
  return (
    <section className="obscure-panneau obscure-montage">
      <header>
        <h2>Le montage alternatif</h2>
        <p className="obscure-cle">
          <span><i className="cle-partie" />{jury ? "Le jury" : "Vous"}</span>
          <span><i className="cle-autre" />Autre montage</span>
          <span><i className="cle-immobile" />Double immobile</span>
        </p>
      </header>
      <p className="obscure-si">
        Si {jury ? "le jury avait" : "vous aviez"} choisi «&nbsp;{autre.nom}&nbsp;» {quand}, {jury ? "il aurait" : "vous auriez"} fini à{" "}
        <strong>{entier(autre.valeur)} USD</strong>{" "}
        <span className={autre.ecart >= 0 ? "gain" : "perte"}>({ecartRond(autre.ecart)})</span>
      </p>
      <Courbes series={series} arrets={g.montage.map((m) => m.jour)} />
      <div className="obscure-prises">
        {g.montage.map((m, kk) => (
          <div key={m.arret} className="obscure-prise">
            <p>
              <b>{m.arret + 1}</b>
              <span>
                <small>{m.date ? dateCourte(`${m.date}T00:00:00`) : `Arrêt ${m.arret + 1}`}{m.evenement ? `, ${m.evenement}` : ""}</small>
                <strong>{m.nom}</strong>
              </span>
            </p>
            <div>
              {m.autres.map((a, ii) => (
                <button key={a.acte} type="button" aria-pressed={k === kk && i === ii} onClick={() => setChoix([kk, ii])}>
                  <span>{a.nom}</span><b className={a.ecart >= 0 ? "gain" : "perte"}>{ecartRond(a.ecart)}</b>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="obscure-petit">On change une seule décision et on garde tout le reste. Une décision qui a rapporté n’était pas forcément une bonne décision.</p>
    </section>
  );
}

function Barre({ nom, valeur }: { nom: string; valeur: number }) {
  return <li><span>{nom}</span><i aria-hidden="true"><em style={{ width: `${valeur}%` }} /></i><b>{Math.round(valeur)}</b></li>;
}

export default function Generique({ jeu, accueil, rejouer }: { jeu: ReturnType<typeof usePartie>; accueil: () => void; rejouer: () => void }) {
  const { partie, agir, coupure, message } = jeu;
  const g = partie.generique;
  if (!g) return null;
  const jury = partie.mode === "jury";
  const mieux = g.valeur >= g.double;
  const egal = Math.abs(g.valeur - g.double) < 1;

  return (
    <div className="obscure-generique">
      <section className="obscure-palme">
        <Laurier />
        <p className="obscure-surtitre">{g.prix}</p>
        {g.note !== null ? <b className="obscure-note">{g.note}<small>/100</small></b> : <b className="obscure-note obscure-note-jury">{entier(g.valeur)}<small>USD</small></b>}
        <h1>{jury ? `${g.profil}, version jury` : g.profil}</h1>
        <p>
          {egal ? (jury ? "Le jury finit exactement comme le double qui n’a rien touché." : "Vous finissez exactement comme votre double qui n’a rien touché.")
            : `${jury ? "Le jury a fait" : "Vous avez fait"} ${mieux ? "mieux" : "moins bien"} que le double qui n’a rien touché : ${ecartRond(g.valeur - g.double)} USD.`}
        </p>
      </section>

      {g.a_deviner && (
        <section className="obscure-panneau obscure-devine">
          <h2>Quelle crise venez-vous de vivre ?</h2>
          <div>
            {g.a_deviner.map((f) => (
              <button key={f.film} type="button" className="obscure-bouton" data-film={f.film} onClick={() => void agir({ nom: "deviner", corps: { film: f.film } })}>{f.sujet}</button>
            ))}
          </div>
        </section>
      )}
      {g.devine && (
        <p className="obscure-revele" data-juste={g.devine.juste || undefined}>
          {g.devine.juste ? "Bien vu" : "Raté"} : c’était <strong>{g.devine.sujet}</strong>, « {partie.titre} ».
        </p>
      )}

      <div className="obscure-generique-grille">
        <section className="obscure-panneau">
          <header>
            <h2>{jury ? "Le bilan" : "Votre note"}</h2>
            {g.note !== null && <span className="seance-tag" data-ton={g.classee ? "accent" : undefined}>{g.classee ? "Classée" : "Hors classement"}</span>}
          </header>
          <ul className="obscure-barres">
            <Barre nom={jury ? "Résultat" : "Résultat, 40 %"} valeur={g.resultat} />
            <Barre nom={jury ? "Protection" : "Protection, 35 %"} valeur={g.protection} />
            {g.plan && <Barre nom="Respect du plan, 25 %" valeur={g.plan.note} />}
          </ul>
          {g.plafonnee && <p className="obscure-plafond">Plan non tenu : note plafonnée à {g.plafond}. Avoir eu de la chance n’est pas avoir bien décidé.</p>}
          {jury && <p className="obscure-petit">Hors classement et sans note : le jury n’est pas jugé sur le plan d’un autre.</p>}
        </section>

        <section className="obscure-panneau">
          <header><h2>{g.plan ? "Avez-vous tenu votre plan ?" : "Les chiffres"}</h2></header>
          {g.plan && (
            <ul className="obscure-plan">
              {g.plan.regles.map((r) => (
                <li key={r.regle} data-tenu={r.note >= 1 || undefined}>
                  <i aria-hidden="true">{r.note >= 1 ? <Check size={14} /> : <X size={14} />}</i>
                  <span><strong>{r.regle}<span className="sr-only">{r.note >= 1 ? ", tenu" : ", non tenu"}</span></strong><small>Attendu : {r.attendu}. Fait : {r.fait}.</small></span>
                </li>
              ))}
            </ul>
          )}
          <dl className="obscure-chiffres">
            <div><dt>Valeur finale</dt><dd>{entier(g.valeur)} USD ({pctSigne(g.rendement, 1)})</dd></div>
            <div><dt>Double immobile</dt><dd>{entier(g.double)} USD</dd></div>
            <div><dt>Pire baisse</dt><dd>{pct(g.pire_baisse)}</dd></div>
            <div><dt>Frais payés</dt><dd>{entier(g.frais)} USD</dd></div>
          </dl>
        </section>
      </div>

      <MontageAlternatif partie={partie} g={g} />

      {g.lecon && <p className="obscure-lecon"><small>Ce que ce film enseigne</small>{g.lecon}</p>}
      {(coupure || message) && <p className="erreur" role="alert">{message ?? "Connexion au serveur perdue, nouvel essai…"}</p>}

      <div className="obscure-fin">
        <button type="button" className="obscure-bouton obscure-bouton-fort" onClick={accueil}>Choisir un autre film</button>
        {partie.mode !== "mystere" && <button type="button" className="obscure-bouton" onClick={rejouer}>Rejouer ce film</button>}
        <Link className="obscure-bouton" href="/formation">Réviser en formation</Link>
      </div>
    </div>
  );
}
