"use client";

import { nombre, pct } from "@/lib/format";
import { STATUT_ORIGINE, STATUTS, type Catalogue, type CleIntensite, type CleType, type Parametres, type StatutCet1 } from "./types";

/** Milliards à une décimale : 15 065 179 milliers de SAR deviennent « 15,1 Md ». */
export const md = (v: number, decimales = 1) => `${nombre(v, decimales)} Md`;
export const pc = (v: number) => pct(v, 2);

/** Comme `pc`, mais avec trois décimales si l'arrondi ferait croire qu'un seuil est atteint (6,997 % ne s'affiche pas « 7,00 % »). */
export function pcSeuil(v: number): string {
  const arrondi = Math.round(v * 10000) / 10000;
  return [0.045, 0.07].some((s) => (v < s) !== (arrondi < s)) ? pct(v, 3) : pct(v, 2);
}
export const points = (v: number, decimales = 2) => `${nombre(v, decimales)} point${Math.abs(v) >= 2 ? "s" : ""}`;
/** 0,95 → « 95 % », 0,999 → « 99,9 % » ; 0,45 → « 45 % ». */
export const pcCourt = (v: number) => `${nombre(v * 100, Math.round(v * 1000) % 10 ? 1 : 0)} %`;

export function Statut({ statut, valeur }: { statut: StatutCet1; valeur?: number }) {
  const s = STATUTS[statut];
  return (
    <span className={`stress-tag stress-tag-${s.classe}`} title={s.mot}>
      <span aria-hidden="true">{s.icone}</span> {valeur === undefined ? s.mot : pcSeuil(valeur)}
      <span className="sr-only"> ({s.mot})</span>
    </span>
  );
}

/** Une phrase courte de ce qui est choqué : « PD au quantile 99 %, +2 points de défauts, LGD 65 % ». */
export function resumeParametres(p: Parametres): string {
  const morceaux = [];
  if (p.quantile.valeur !== null) morceaux.push(`PD de crise au quantile ${pcCourt(p.quantile.valeur)}`);
  if (p.hausse.valeur) morceaux.push(`+${nombre(p.hausse.valeur * 100, 0)} points de défauts`);
  morceaux.push(`LGD ${pcCourt(p.lgd.valeur ?? 0)}`);
  return morceaux.join(", ");
}

export function ChoixCrise({ catalogue, type, intensite, choisirType, choisirIntensite }: {
  catalogue: Catalogue; type: CleType; intensite: CleIntensite; choisirType: (t: CleType) => void; choisirIntensite: (i: CleIntensite) => void;
}) {
  return (
    <>
      <div className="stress-scenarios" role="group" aria-label="Type de crise">
        {catalogue.types.map((t) => (
          <button key={t.cle} type="button" className="stress-scenario" aria-pressed={type === t.cle} onClick={() => choisirType(t.cle)}>
            <b>{t.nom}</b>
            <small>{t.phrase}</small>
          </button>
        ))}
      </div>
      <div className="stress-intensite">
        <span id="stress-libelle-intensite">Intensité</span>
        <div className="stress-bascule stress-bascule-3" role="radiogroup" aria-labelledby="stress-libelle-intensite">
          {catalogue.intensites.map((i) => (
            <button key={i.cle} type="button" role="radio" aria-checked={intensite === i.cle} onClick={() => choisirIntensite(i.cle)} title={i.lecture}>
              {i.nom}
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

const LIBELLE_LEVIER = { quantile: "Quantile de la crise (Vasicek)", hausse: "Défauts en plus", lgd: "Perte en cas de défaut (LGD)" } as const;

/** Les paramètres réellement appliqués, avec leur origine : toujours visibles dans le résultat. */
export function ParametresAppliques({ p }: { p: Parametres }) {
  const lignes = (["quantile", "hausse", "lgd"] as const).filter((k) => p[k].statut);
  return (
    <section className="stress-panneau" aria-labelledby="stress-titre-parametres">
      <header className="stress-tete">
        <h2 id="stress-titre-parametres">Paramètres appliqués : {p.nom.toLowerCase()}, intensité {p.nom_intensite.toLowerCase()}</h2>
      </header>
      <table className="stress-parametres">
        <caption className="sr-only">Valeur, origine et justification de chaque paramètre</caption>
        <thead><tr><th scope="col">Paramètre</th><th scope="col">Valeur</th><th scope="col">Origine</th><th scope="col">Pourquoi</th></tr></thead>
        <tbody>
          {lignes.map((k) => {
            const v = p[k];
            const valeur = k === "hausse" ? `+${nombre((v.valeur ?? 0) * 100, 0)} points` : pcCourt(v.valeur ?? 0);
            return (
              <tr key={k}>
                <th scope="row">{LIBELLE_LEVIER[k]}</th>
                <td>{valeur}</td>
                <td><span className={`stress-tag stress-origine-${v.statut}`}>{STATUT_ORIGINE[v.statut!]}</span></td>
                <td>{v.justification}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

export function LienSource({ url, pages }: { url: string; pages: [number, number] }) {
  return (
    <a className="stress-source" href={url} target="_blank" rel="noopener noreferrer">
      Source, p. {pages[0]} et p. {pages[1]}<span className="sr-only"> (s&apos;ouvre dans un nouvel onglet)</span>
    </a>
  );
}
