"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { lienActif } from "@/lib/actif";
import { dateCourte, montant, montantSigne, pct, pctSigne, prix } from "@/lib/format";
import { cascade, PERIODES, SEUILS_SECTEUR, sousLEau, squarifier, statutSecteur, type CleePeriode } from "@/lib/portefeuille";
import { useTheme } from "@/lib/theme";
import type { Actif, Analyse, PointValeur, Portefeuille, Position } from "@/lib/types";
import { couleur } from "./Correlations";

const usd = (n: number) => `${montant(n)} USD`;
const usdSigne = (n: number) => `${montantSigne(n)} USD`;

/** Largeur réelle d'un conteneur (les graphiques se redessinent à la bonne taille, sans étirer le texte).
 *  Ref de rappel : la mesure démarre même si le conteneur n'apparaît qu'après le chargement des données. */
function useLargeur<T extends HTMLElement>(defaut = 600): [(el: T | null) => void, number] {
  const [largeur, setLargeur] = useState(defaut);
  const obs = useRef<ResizeObserver | null>(null);
  const ref = useCallback((el: T | null) => {
    obs.current?.disconnect();
    obs.current = null;
    if (!el) return;
    obs.current = new ResizeObserver(([e]) => setLargeur(Math.max(240, e.contentRect.width)));
    obs.current.observe(el);
  }, []);
  useEffect(() => () => obs.current?.disconnect(), []);
  return [ref, largeur];
}

interface Bulle { x: number; y: number; lignes: { texte: string; fort?: boolean; ton?: "gain" | "perte" }[] }

/** Infobulle positionnée dans le conteneur du graphique ; la valeur passe en premier, le libellé ensuite. */
function Infobulle({ bulle, largeur }: { bulle: Bulle | null; largeur: number }) {
  if (!bulle) return null;
  const aGauche = bulle.x > largeur * 0.6;
  return (
    <div className="infobulle" role="status" style={{ top: bulle.y, ...(aGauche ? { right: largeur - bulle.x + 12 } : { left: bulle.x + 12 }) }}>
      {bulle.lignes.map((l, i) => <p key={i} className={`${l.fort ? "infobulle-fort" : ""} ${l.ton ?? ""}`}>{l.texte}</p>)}
    </div>
  );
}

// ----------------------------------------------------------------------------- 2. cascade du résultat
export function CascadeResultat({ pf }: { pf: Portefeuille | null }) {
  const [zone, largeur] = useLargeur<HTMLDivElement>(560);
  const [bulle, setBulle] = useState<Bulle | null>(null);
  if (!pf) return <section className="panneau"><p className="chargement">Chargement…</p></section>;
  const marches = cascade(pf);
  const H = 230, haut = 26, bas = 44;
  const bornes = marches.flatMap((m) => (m.type === "total" ? [m.fin] : [m.debut, m.fin]));
  let lo = Math.min(...bornes), hi = Math.max(...bornes);
  const marge = Math.max((hi - lo) * 0.35, Math.abs(hi) * 0.002, 1);
  lo -= marge; hi += marge;                                  // axe tronqué : sinon les écarts de quelques dollars seraient invisibles
  const y = (v: number) => haut + (1 - (v - lo) / (hi - lo)) * (H - haut - bas);
  const bande = largeur / marches.length;
  const lb = Math.min(64, bande * 0.55);
  return (
    <section className="panneau" aria-labelledby="titre-cascade">
      <header className="panneau-tete"><h2 id="titre-cascade">D&apos;où vient votre résultat ?</h2></header>
      <div ref={zone} className="visuel-zone" onPointerLeave={() => setBulle(null)}>
        <svg width={largeur} height={H} role="img" aria-label="Cascade : capital de départ, gains réalisés, gains latents, frais, valeur actuelle">
          {marches.map((m, i) => {
            const cx = bande * i + bande / 2;
            const y1 = m.type === "total" ? y(lo) : y(Math.max(m.debut, m.fin));
            const y2 = m.type === "total" ? y(m.fin) : y(Math.min(m.debut, m.fin));
            const hauteur = Math.max(2, Math.abs(y1 - y2));
            const ecart = m.fin - m.debut;
            const valeur = m.type === "total" ? montant(m.fin) : montantSigne(ecart);
            const montrer = (e: React.PointerEvent | React.FocusEvent) => {
              const boite = (e.currentTarget as SVGGElement).ownerSVGElement?.getBoundingClientRect();
              const cible = (e.currentTarget as SVGGElement).getBoundingClientRect();
              setBulle({ x: cible.left - (boite?.left ?? 0) + cible.width / 2, y: Math.max(0, cible.top - (boite?.top ?? 0) - 10), lignes: [
                { texte: `${valeur} USD`, fort: true, ton: m.type === "hausse" && ecart > 0 ? "gain" : m.type === "baisse" && ecart < 0 ? "perte" : undefined },
                { texte: m.libelle }, { texte: m.aide },
              ] });
            };
            return (
              <g key={m.libelle} tabIndex={0} className="cascade-marche" onPointerEnter={montrer} onFocus={montrer} onBlur={() => setBulle(null)}
                aria-label={`${m.libelle} : ${valeur} USD`}>
                <rect x={cx - bande / 2} y={0} width={bande} height={H - bas} fill="transparent" />
                <rect x={cx - lb / 2} y={Math.min(y1, y2)} width={lb} height={hauteur} rx={4}
                  className={m.type === "total" ? "cascade-total" : ecart >= 0 ? "cascade-hausse" : "cascade-baisse"} />
                {i < marches.length - 1 && <line x1={cx + lb / 2} x2={cx + bande - lb / 2} y1={y(m.fin)} y2={y(m.fin)} className="cascade-lien" />}
                <text x={cx} y={Math.min(y1, y2) - 6} textAnchor="middle" className="graphe-texte graphe-texte-fort">{valeur}</text>
                <text x={cx} y={H - bas + 16} textAnchor="middle" className="graphe-texte">{m.libelle.split(" ").slice(0, 2).join(" ")}</text>
                <text x={cx} y={H - bas + 29} textAnchor="middle" className="graphe-texte">{m.libelle.split(" ").slice(2).join(" ")}</text>
              </g>
            );
          })}
        </svg>
        <Infobulle bulle={bulle} largeur={largeur} />
      </div>
      <p className="aide">Valeur actuelle = capital de départ + réalisé + latent − frais (en USD). Axe vertical tronqué pour rendre les écarts visibles.</p>
    </section>
  );
}

// ----------------------------------------------------------------------------- 3. carte des positions
export function CartePositions({ pf, actifs }: { pf: Portefeuille | null; actifs: Actif[] }) {
  const [zone, largeur] = useLargeur<HTMLDivElement>(600);
  const [bulle, setBulle] = useState<Bulle | null>(null);
  const theme = useTheme();
  const router = useRouter();
  const H = 300;
  const tuiles = useMemo(() => squarifier((pf?.positions ?? []).map((p) => ({ valeur: p.valeur, item: p })), largeur, H), [pf, largeur]);
  const parSymbole = useMemo(() => new Map(actifs.map((a) => [a.symbole, a])), [actifs]);

  const ouvrir = (p: Position) => { const a = parSymbole.get(p.symbole); if (a) router.push(lienActif(a)); };
  return (
    <section className="panneau" aria-labelledby="titre-carte">
      <header className="panneau-tete"><h2 id="titre-carte">Carte des positions</h2></header>
      {!pf ? <p className="chargement">Chargement…</p> : tuiles.length === 0 ? (
        <p className="vide">Aucune position : chaque actif acheté apparaîtra ici comme une tuile, d&apos;autant plus grande qu&apos;il pèse lourd, bleue s&apos;il gagne, orange s&apos;il perd.</p>
      ) : (
        <>
          <div ref={zone} className="visuel-zone" onPointerLeave={() => setBulle(null)}>
            <svg width={largeur} height={H} role="img" aria-label="Carte des positions : surface proportionnelle à la valeur, couleur selon le gain ou la perte latent">
              {tuiles.map(({ item: p, x, y, w, h }) => {
                const r = p.prix_moyen ? p.prix_marche / p.prix_moyen - 1 : 0;
                const c = couleur(Math.max(-1, Math.min(1, r / 0.2)), theme);
                const nom = parSymbole.get(p.symbole)?.nom ?? p.symbole;
                const montrer = () => setBulle({ x: x + w / 2, y: y + Math.min(h / 2, 40), lignes: [
                  { texte: `${pctSigne(r)} · ${usdSigne(p.pnl_latent)}`, fort: true, ton: r > 0 ? "gain" : r < 0 ? "perte" : undefined },
                  { texte: `${p.symbole} · ${nom}` },
                  { texte: `Valeur ${usd(p.valeur)} · ${pct(p.poids, 1)} du portefeuille` },
                  { texte: `Prix moyen ${prix(p.prix_moyen)} → actuel ${prix(p.prix_marche)}` },
                ] });
                return (
                  <g key={p.symbole} tabIndex={0} role="link" className="tuile" aria-label={`${p.symbole} : ${pct(p.poids, 1)} du portefeuille, ${pctSigne(r)}`}
                    onPointerEnter={montrer} onFocus={montrer} onBlur={() => setBulle(null)} onClick={() => ouvrir(p)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ouvrir(p); } }}>
                    <rect x={x + 1} y={y + 1} width={Math.max(0, w - 2)} height={Math.max(0, h - 2)} rx={4} fill={c.fond} />
                    {w > 54 && h > 34 && (
                      <text x={x + 8} y={y + 20} fill={c.texte} className="tuile-texte">
                        <tspan fontWeight={700}>{p.symbole.replace("-USD", "").replace("=F", "")}</tspan>
                        <tspan x={x + 8} dy={16}>{pctSigne(r)}</tspan>
                        {h > 70 && w > 90 && <tspan x={x + 8} dy={16}>{usd(p.valeur)}</tspan>}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
            <Infobulle bulle={bulle} largeur={largeur} />
          </div>
          <p className="correl-legende" aria-hidden="true"><span>−20 % ou moins</span><i className="correl-degrade" /><span>+20 % ou plus</span></p>
          <p className="aide">Surface = poids dans le portefeuille ; couleur = gain ou perte latent depuis l&apos;achat. Cliquez une tuile pour ouvrir l&apos;actif. Liquidités non représentées ({usd(pf.cash)}).</p>
        </>
      )}
    </section>
  );
}

// ----------------------------------------------------------------------------- 4. risque par secteur
const STATUT_SECTEUR = {
  ok: { icone: "✓", texte: "Exposition modérée" },
  attention: { icone: "!", texte: "Concentration à surveiller" },
  danger: { icone: "✕", texte: "Concentration dangereuse" },
} as const;

export function RisqueSecteurs({ analyse, pf }: { analyse: Analyse | null; pf: Portefeuille | null }) {
  const secteurs = analyse?.concentration_detail?.secteurs ?? [];
  return (
    <section className="panneau" aria-labelledby="titre-risque-secteurs">
      <header className="panneau-tete"><h2 id="titre-risque-secteurs">Risque par secteur</h2></header>
      {!analyse || !pf ? <p className="chargement">Chargement…</p> : secteurs.length === 0 ? (
        <p className="vide">Aucune position investie : l&apos;exposition de chaque secteur apparaîtra après un premier achat.</p>
      ) : (
        <ul className="risque-secteurs">
          {secteurs.map((s) => {
            const statut = statutSecteur(s.part);
            const perte = s.part * pf.valeur_positions * 0.3;          // choc hypothétique de −30 % sur le secteur
            return (
              <li key={s.secteur} data-statut={statut}>
                <div className="risque-secteur-tete">
                  <strong>{s.secteur}</strong>
                  <span className="risque-secteur-statut"><span aria-hidden="true">{STATUT_SECTEUR[statut].icone}</span> {STATUT_SECTEUR[statut].texte}</span>
                </div>
                <div className="risque-piste" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(s.part * 100)} aria-label={`${s.secteur} : ${pct(s.part, 1)} de la partie investie`}>
                  <span className="risque-rempli" style={{ width: `${Math.min(1, s.part) * 100}%` }} />
                  <span className="risque-seuil" style={{ left: `${SEUILS_SECTEUR.attention * 100}%` }} aria-hidden="true" />
                  <span className="risque-seuil" style={{ left: `${SEUILS_SECTEUR.danger * 100}%` }} aria-hidden="true" />
                </div>
                <p className="aide">{pct(s.part, 1)} de la partie investie · si ce secteur chutait de 30 % (simulation) : <span className="perte">−{usd(perte)}</span>, soit {pct(pf.equity ? perte / pf.equity : 0, 1)} du portefeuille.</p>
              </li>
            );
          })}
        </ul>
      )}
      <p className="aide">Repères verticaux : 40 % et 60 % de la partie investie (seuils pédagogiques). Le choc de −30 % est une hypothèse, pas une prévision.</p>
    </section>
  );
}

// ----------------------------------------------------------------------------- 5. période et graphique « sous l'eau »
export function ChoixPeriode({ valeur, changer }: { valeur: CleePeriode; changer: (c: CleePeriode) => void }) {
  return (
    <div className="choix-filtre" role="group" aria-label="Période affichée">
      {PERIODES.map((p) => <button key={p.cle} type="button" aria-pressed={valeur === p.cle} onClick={() => changer(p.cle)}>{p.libelle}</button>)}
    </div>
  );
}

export function SousLEau({ points }: { points: PointValeur[] }) {
  const [zone, largeur] = useLargeur<HTMLDivElement>(600);
  const [survol, setSurvol] = useState<number | null>(null);
  const serie = useMemo(() => sousLEau(points), [points]);
  const H = 120, gauche = 48, haut = 8, bas = 8;
  if (serie.length < 2) return <p className="vide">La plongée apparaîtra après quelques jours simulés.</p>;
  const max = Math.max(0.01, ...serie.map((s) => s.baisse));
  const x = (i: number) => gauche + (i / (serie.length - 1)) * (largeur - gauche - 8);
  const y = (b: number) => haut + (b / max) * (H - haut - bas);
  const ligne = serie.map((s, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(s.baisse).toFixed(1)}`).join("");
  const s = survol !== null ? serie[survol] : null;
  return (
    <div ref={zone} className="visuel-zone">
      <svg width={largeur} height={H} role="img" aria-label={`Baisse depuis le sommet au fil du temps ; pire baisse ${pct(max, 1)}`}
        onPointerMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); const i = Math.round(((e.clientX - r.left - gauche) / (r.width - gauche - 8)) * (serie.length - 1)); setSurvol(Math.max(0, Math.min(serie.length - 1, i))); }}
        onPointerLeave={() => setSurvol(null)}>
        <line x1={gauche} x2={largeur - 8} y1={y(0)} y2={y(0)} className="graphe-axe" />
        <text x={gauche - 6} y={y(0) + 4} textAnchor="end" className="graphe-texte">0 %</text>
        <text x={gauche - 6} y={y(max)} textAnchor="end" className="graphe-texte">−{pct(max, 0)}</text>
        <path d={`${ligne}L${x(serie.length - 1)},${y(0)}L${x(0)},${y(0)}Z`} className="sous-eau-aire" />
        <path d={ligne} className="sous-eau-ligne" />
        {s && survol !== null && <><line x1={x(survol)} x2={x(survol)} y1={0} y2={H} className="graphe-axe" /><circle cx={x(survol)} cy={y(s.baisse)} r={4} className="sous-eau-point" /></>}
      </svg>
      <p className="aide">{s ? `${dateCourte(`${s.jour}T00:00:00`)} : ${s.baisse > 0 ? `−${pct(s.baisse, 1)} sous le sommet` : "au sommet"}` : "Chaque creux montre de combien le portefeuille était sous son plus haut. Survolez pour lire une date."}</p>
    </div>
  );
}
