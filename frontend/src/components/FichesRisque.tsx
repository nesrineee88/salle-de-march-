"use client";

import Link from "next/link";
import { useState } from "react";
import { nombre, pct } from "@/lib/format";
import type { Analyse, Beta, Distribution } from "@/lib/types";
import { useMarche } from "./Contexte";

const L = 320;   // largeur logique des graphiques (le SVG s'adapte à son conteneur)
const H = 150;

type Cle = "ecart_type" | "var" | "cvar" | "sharpe" | "drawdown" | "beta" | "covariance" | "secteurs" | "rsi";

interface Fiche {
  titre: string;
  nature: "risque" | "performance" | "technique";
  valeur: string;
  formule: string;
  interpretation: string;
  calcul: string;
  simple: string;
  visuel: React.ReactNode;
}

const NATURE: Record<Fiche["nature"], string> = {
  risque: "Mesure de risque",
  performance: "Rendement ajusté du risque",
  technique: "Indicateur technique (momentum) : pas une mesure de risque",
};

/** Histogramme des rendements de séance avec la VaR et la CVaR (pertes positives) ou une bande de ±1 écart-type. */
function Histogramme({ d, varPerte, cvarPerte, sigma, libelle }: { d: Distribution; varPerte?: number; cvarPerte?: number; sigma?: number; libelle: string }) {
  const min = d.bornes[0];
  const max = d.bornes[d.bornes.length - 1];
  const etendue = max - min || 1;
  const x = (v: number) => ((v - min) / etendue) * (L - 20) + 10;
  const plusHaut = Math.max(...d.effectifs, 1);
  const largeur = (L - 20) / d.effectifs.length;
  const total = d.effectifs.reduce((s, n) => s + n, 0);
  return (
    <figure className="graphe-risque">
      <svg viewBox={`0 0 ${L} ${H + 18}`} role="img" aria-label={libelle}>
        {sigma !== undefined && (
          <rect x={x(-sigma)} y={0} width={Math.max(0, x(sigma) - x(-sigma))} height={H} className="graphe-bande"><title>{`±1 écart-type : de −${pct(sigma, 2)} à +${pct(sigma, 2)}`}</title></rect>
        )}
        {d.effectifs.map((n, i) => {
          const h = (n / plusHaut) * (H - 8);
          const debut = d.bornes[i];
          const fin = d.bornes[i + 1];
          const queue = varPerte !== undefined && fin <= -varPerte + 1e-12;
          return (
            <rect key={i} x={10 + i * largeur + 0.5} y={H - h} width={Math.max(largeur - 1, 0.5)} height={h} className={queue ? "graphe-barre graphe-barre-queue" : "graphe-barre"}>
              <title>{`De ${pct(debut, 2)} à ${pct(fin, 2)} : ${n} séance${n > 1 ? "s" : ""} (${pct(total ? n / total : 0, 1)})`}</title>
            </rect>
          );
        })}
        <line x1={x(0)} x2={x(0)} y1={0} y2={H} className="graphe-axe" />
        {varPerte !== undefined && <line x1={x(-varPerte)} x2={x(-varPerte)} y1={0} y2={H} className="graphe-repere-var" />}
        {cvarPerte !== undefined && <line x1={x(-cvarPerte)} x2={x(-cvarPerte)} y1={0} y2={H} className="graphe-repere-cvar" />}
        <text x={10} y={H + 14} className="graphe-texte">{pct(min, 1)}</text>
        <text x={L - 10} y={H + 14} textAnchor="end" className="graphe-texte">{pct(max, 1)}</text>
      </svg>
      <figcaption className="legende-risque">
        {varPerte !== undefined && <span><i className="legende-trait legende-var" /> VaR : −{pct(varPerte, 2)}</span>}
        {cvarPerte !== undefined && <span><i className="legende-trait legende-cvar" /> CVaR : −{pct(cvarPerte, 2)}</span>}
        {sigma !== undefined && <span><i className="legende-trait legende-bande" /> ±1 écart-type</span>}
        <span className="discret">Survolez une barre : nombre de séances.</span>
      </figcaption>
    </figure>
  );
}

/** Nuage (rendement de l'indice, rendement du portefeuille) et droite de régression y = α + βx. */
function NuageBeta({ b }: { b: Beta }) {
  const xs = b.points.map((p) => p[0]);
  const ys = b.points.map((p) => p[1]);
  const borne = Math.max(...xs.map(Math.abs), ...ys.map(Math.abs), 1e-6);
  const sx = (v: number) => (v / borne) * (L / 2 - 12) + L / 2;
  const sy = (v: number) => H / 2 - (v / borne) * (H / 2 - 8);
  const droite = (v: number) => b.alpha_jour + b.beta * v;
  return (
    <figure className="graphe-risque">
      <svg viewBox={`0 0 ${L} ${H}`} role="img" aria-label={`Nuage de ${b.jours} séances : rendement du portefeuille selon celui du ${b.indice}, pente ${nombre(b.beta, 2)}`}>
        <line x1={0} x2={L} y1={sy(0)} y2={sy(0)} className="graphe-axe" />
        <line x1={sx(0)} x2={sx(0)} y1={0} y2={H} className="graphe-axe" />
        {b.points.map(([px, py], i) => (
          <circle key={i} cx={sx(px)} cy={sy(py)} r={2} className="graphe-point"><title>{`${b.indice} : ${pct(px, 2)} · portefeuille : ${pct(py, 2)}`}</title></circle>
        ))}
        <line x1={sx(-borne)} y1={sy(droite(-borne))} x2={sx(borne)} y2={sy(droite(borne))} className="graphe-droite" />
      </svg>
      <figcaption className="legende-risque">
        <span>Horizontal : rendement du {b.indice} · vertical : rendement du portefeuille, par séance.</span>
        <span><i className="legende-trait legende-cvar" /> pente = bêta</span>
      </figcaption>
    </figure>
  );
}

function Barres({ lignes, note }: { lignes: { libelle: string; part: number }[]; note?: string }) {
  return (
    <div className="barres-fiche">
      {lignes.map((l) => (
        <div key={l.libelle} className="barre-fiche" title={`${l.libelle} : ${pct(l.part, 1)}`}>
          <span className="barre-nom">{l.libelle}</span>
          <span className="barre-piste"><span className="barre-rempli" style={{ width: `${Math.min(1, Math.max(0, l.part)) * 100}%` }} /></span>
          <span className="barre-valeur">{pct(l.part, 1)}</span>
        </div>
      ))}
      {note && <p className="aide">{note}</p>}
    </div>
  );
}

function TableCovariance({ c }: { c: NonNullable<Analyse["covariances"]> }) {
  const n = Math.min(c.symboles.length, 8);
  const court = (s: string) => s.replace("-USD", "").replace("=F", "");
  return (
    <div className="table-defilante">
      <table className="tableau tableau-compact">
        <caption className="aide">Covariances des rendements de séance, en 10⁻⁴ (unité : rendement²). La diagonale est la variance de chaque actif.</caption>
        <thead><tr><th scope="col"><span className="sr-only">Actif</span></th>{c.symboles.slice(0, n).map((s) => <th key={s} scope="col">{court(s)}</th>)}</tr></thead>
        <tbody>
          {c.symboles.slice(0, n).map((a, i) => (
            <tr key={a}>
              <th scope="row">{court(a)}</th>
              {c.matrice[i].slice(0, n).map((v, j) => <td key={j} className={i === j ? "discret" : v > 0 ? "gain" : v < 0 ? "perte" : ""}>{nombre(v * 1e4, 2)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function fiches(a: Analyse): Record<Cle, Fiche> {
  const r = a.risque;
  const p = a.performance;
  const b = a.beta;
  const sansDonnees = <p className="vide">Pas encore assez d&apos;historique : détenez des positions et avancez dans le temps (au moins 30 séances communes).</p>;
  const lectureBeta = !b ? "" : b.beta > 1.05 ? "Le portefeuille amplifie les mouvements de l'indice : il pourrait baisser plus fort que le marché."
    : b.beta < -0.05 ? "Le portefeuille a tendance à aller à contre-sens de l'indice."
      : b.beta < 0.95 ? "Le portefeuille amortit les mouvements de l'indice (liquidités ou actifs peu liés au marché)."
        : "Le portefeuille suit à peu près les mouvements de l'indice.";
  return {
    ecart_type: {
      titre: "Écart-type et volatilité historique", nature: "risque",
      valeur: r?.ecart_type_jour != null ? `${pct(r.ecart_type_jour, 2)} par séance · ${pct(r.volatilite_annuelle_seances, 1)} par an` : "–",
      formule: "σ = √( Σ (rᵢ − r̄)² / (n − 1) )\nσ annuelle = σ × √252",
      interpretation: "Mesure la dispersion des rendements autour de leur moyenne : plus elle est haute, plus la valeur du portefeuille varie fort, dans les deux sens.",
      calcul: `Rendements de séance du portefeuille ACTUEL (poids d'aujourd'hui) sur ${r?.jours ?? "–"} séances passées communes à vos actifs ; écart-type d'échantillon (n − 1), annualisé avec 252 séances.`,
      simple: "Un écart-type de 1 % par séance signifie qu'une variation de ±1 % en une journée est banale.",
      visuel: r?.distribution && r.ecart_type_jour != null ? <Histogramme d={r.distribution} sigma={r.ecart_type_jour} libelle="Distribution des rendements de séance avec la bande d'un écart-type" /> : sansDonnees,
    },
    var: {
      titre: "Value at Risk (VaR 95 %, un jour)", nature: "risque",
      valeur: r ? `−${pct(r.var, 2)} · ${nombre(r.var_montant, 2)} USD` : "–",
      formule: "VaR₉₅ = − quantile à 5 % des rendements\n(exprimée en perte positive)",
      interpretation: "Lors de 95 % des séances passées, la perte n'a pas dépassé ce montant. Elle ne dit rien des 5 % de pires séances.",
      calcul: "VaR historique : aucune loi de probabilité supposée, on lit directement le quantile des rendements passés du portefeuille actuel.",
      simple: "Une séance sur vingt, environ, pourrait faire perdre plus que ce chiffre.",
      visuel: r?.distribution ? <Histogramme d={r.distribution} varPerte={r.var} cvarPerte={r.cvar} libelle="Distribution des rendements avec la VaR et la CVaR" /> : sansDonnees,
    },
    cvar: {
      titre: "Conditional VaR (CVaR 95 %, un jour)", nature: "risque",
      valeur: r ? `−${pct(r.cvar, 2)} · ${nombre(r.cvar_montant, 2)} USD` : "–",
      formule: "CVaR₉₅ = moyenne des pertes ≥ VaR₉₅",
      interpretation: "La perte moyenne pendant les 5 % de pires séances : la VaR dit où commence la zone dangereuse, la CVaR dit jusqu'où elle va en moyenne.",
      calcul: "Moyenne des pertes historiques supérieures ou égales à la VaR (barres en couleur de perte à gauche de la ligne VaR).",
      simple: "Les très mauvais jours, la perte moyenne a été de cet ordre.",
      visuel: r?.distribution ? <Histogramme d={r.distribution} varPerte={r.var} cvarPerte={r.cvar} libelle="Queue de distribution au-delà de la VaR" /> : sansDonnees,
    },
    sharpe: {
      titre: "Ratio de Sharpe", nature: "performance",
      valeur: p.sharpe != null ? nombre(p.sharpe, 2) : "–",
      formule: "Sharpe = (R annualisé − r sans risque) / σ annualisée\n(r sans risque posé à 0)",
      interpretation: "Rendement obtenu par unité de risque. Au-dessus de 1, le risque pris a été bien rémunéré ; sous 0, le portefeuille a perdu.",
      calcul: `Calculé sur la courbe de valeur réelle de votre portefeuille (${p.points_courbe} points, au moins 10 nécessaires), en tenant compte de l'écart de temps entre deux points.`,
      simple: "Il répond à la question : le gain valait-il les secousses subies ?",
      visuel: p.sharpe != null ? <Barres lignes={[{ libelle: "Votre Sharpe", part: Math.max(0, p.sharpe) / 3 }, { libelle: "Repère : 1", part: 1 / 3 }]} note="Échelle de 0 à 3. Un Sharpe négatif est affiché vide." /> : sansDonnees,
    },
    drawdown: {
      titre: "Drawdown maximal", nature: "risque",
      valeur: pct(p.drawdown_max, 2),
      formule: "DDₜ = (pic jusqu'à t − Vₜ) / pic jusqu'à t\nDD max = max DDₜ",
      interpretation: "La pire chute subie depuis un sommet. Elle mesure la douleur réelle d'un investisseur entré au pire moment.",
      calcul: "Sur la courbe de valeur du portefeuille depuis le début de la simulation (voir « Valeur au fil du temps »).",
      simple: "Le pire moment vécu : de combien la valeur est tombée depuis son plus haut.",
      visuel: <Barres lignes={[{ libelle: "Maximal", part: p.drawdown_max }, { libelle: "Actuel", part: p.drawdown_courant }]} />,
    },
    beta: {
      titre: `Bêta par rapport au ${b?.indice ?? "S&P 500"}`, nature: "risque",
      valeur: b ? `${nombre(b.beta, 2)} (corrélation ${nombre(b.correlation, 2)})` : "–",
      formule: "β = Cov(r_portefeuille, r_indice) / Var(r_indice)\nα = r̄_portefeuille − β × r̄_indice",
      interpretation: `${lectureBeta} Un bêta de 1,5 signifie : si l'indice perd 1 %, le portefeuille a perdu en moyenne 1,5 %.`,
      calcul: b ? `Régression sur ${b.jours} séances passées communes : covariance ${nombre(b.covariance * 1e4, 3)}·10⁻⁴, variance de l'indice ${nombre(b.variance_marche * 1e4, 3)}·10⁻⁴, alpha ${pct(b.alpha_jour, 3)} par séance.` : "Rendements de séance du portefeuille actuel et de l'indice, sur les dates où les deux cotent (au moins 30).",
      simple: "Le bêta dit si votre portefeuille bouge plus ou moins fort que le marché.",
      visuel: b ? <NuageBeta b={b} /> : sansDonnees,
    },
    covariance: {
      titre: "Covariance et corrélation entre actifs", nature: "risque",
      valeur: a.covariances ? `${a.covariances.symboles.length} actifs` : "–",
      formule: "Cov(X, Y) = Σ (xᵢ − x̄)(yᵢ − ȳ) / (n − 1)\nρ = Cov(X, Y) / (σ_X × σ_Y), entre −1 et +1",
      interpretation: "Une covariance positive : les deux actifs montent et baissent ensemble, la diversification est faible. La corrélation est la même information ramenée entre −1 et +1 (voir la carte des corrélations).",
      calcul: "Rendements de séance des actifs détenus, alignés sur les jours où tous cotent.",
      simple: "Deux actifs qui bougent ensemble ne se protègent pas l'un l'autre.",
      visuel: a.covariances ? <TableCovariance c={a.covariances} /> : <p className="vide">Détenez au moins deux actifs avec 30 séances d&apos;historique commun.</p>,
    },
    secteurs: {
      titre: "Exposition sectorielle et concentration (HHI)", nature: "risque",
      valeur: a.concentration_detail ? `HHI ${nombre(a.concentration_detail.hhi, 2)} · ${nombre(a.concentration_detail.nb_effectif, 1)} positions effectives` : "–",
      formule: "HHI = Σ wᵢ²   (wᵢ = poids dans la partie investie)\nnombre effectif = 1 / HHI",
      interpretation: "Le HHI vaut 1 avec une seule position et 1/n avec n positions égales. Au-dessus de 0,25, le portefeuille est concentré : une crise sur un actif ou un secteur pèse lourd.",
      calcul: "Poids de chaque position et de chaque secteur dans la partie investie (liquidités exclues).",
      simple: "Plus vos œufs sont dans le même panier, plus ce chiffre est haut.",
      visuel: a.concentration_detail ? <Barres lignes={a.concentration_detail.secteurs.map((s) => ({ libelle: s.secteur, part: s.part }))} note="Seuils pédagogiques : 40 % (attention) et 60 % (danger) pour un secteur." /> : <p className="vide">Aucune position investie.</p>,
    },
    rsi: {
      titre: "RSI (Relative Strength Index)", nature: "technique",
      valeur: "par actif",
      formule: "RSI = 100 − 100 / (1 + RS)\nRS = moyenne des hausses / moyenne des baisses (14 séances, lissage de Wilder)",
      interpretation: "Le RSI mesure la vitesse récente des hausses par rapport aux baisses (momentum). Il ne mesure PAS l'ampleur des pertes possibles : un RSI de 30 ne dit rien de la VaR. Au-dessus de 70 ou sous 30, un retournement est possible, jamais certain.",
      calcul: "Calculé sur les clôtures de chaque actif ; affiché sous le graphique en chandeliers de la fiche de l'actif.",
      simple: "C'est un thermomètre de l'élan d'un prix, pas une mesure du danger pour votre portefeuille.",
      visuel: <p className="aide">Ouvrez un actif depuis <Link href="/actions">Actions</Link> et cochez « RSI » sous le graphique.</p>,
    },
  };
}

const ORDRE: Cle[] = ["ecart_type", "var", "cvar", "drawdown", "beta", "covariance", "secteurs", "sharpe", "rsi"];
const COURT: Record<Cle, string> = {
  ecart_type: "Écart-type", var: "VaR", cvar: "CVaR", drawdown: "Drawdown", beta: "Bêta",
  covariance: "Covariance", secteurs: "Secteurs (HHI)", sharpe: "Sharpe", rsi: "RSI (technique)",
};

export default function FichesRisque({ analyse }: { analyse: Analyse | null }) {
  const { mode } = useMarche();
  const [choix, setChoix] = useState<Cle>("ecart_type");
  if (!analyse) return <section className="panneau"><p className="chargement">Chargement des fiches…</p></section>;
  const f = fiches(analyse)[choix];
  return (
    <section className="panneau fiches-risque" aria-labelledby="titre-fiches">
      <header className="panneau-tete"><h2 id="titre-fiches">Comprendre chaque indicateur</h2></header>
      <div className="fiches-choix" role="group" aria-label="Choisir un indicateur">
        {ORDRE.map((c) => <button key={c} type="button" aria-pressed={choix === c} className={c === "rsi" ? "fiche-technique" : undefined} onClick={() => setChoix(c)}>{COURT[c]}</button>)}
      </div>
      <article className="fiche" aria-live="polite">
        <header className="fiche-tete">
          <h3>{f.titre}</h3>
          <span className={`badge-nature badge-${f.nature}`}>{NATURE[f.nature]}</span>
        </header>
        <p className="fiche-valeur">{f.valeur}</p>
        <div className="fiche-corps">
          <div>
            <h4>Formule</h4>
            <pre className="formule">{f.formule}</pre>
            <h4>Interprétation</h4>
            <p>{f.interpretation}</p>
            <h4>Mode de calcul</h4>
            <p>{f.calcul}</p>
            {mode === "apprenant" && <><h4>En clair</h4><p>{f.simple}</p></>}
          </div>
          <div>
            <h4>Visualisation</h4>
            {f.visuel}
          </div>
        </div>
      </article>
    </section>
  );
}
