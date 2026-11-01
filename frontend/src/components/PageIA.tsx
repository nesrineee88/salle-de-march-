"use client";

import { useMemo, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { nombre, pct, pctSigne } from "@/lib/format";
import type { AgentIA, AnomaliesIA, MetriquesAgent, OptimiseurIA, PredictionIA, RegimesIA } from "@/lib/types";
import { useMarche } from "./Contexte";

function Bloc<T>({ titre, aide, lancer, libelle, rendre }: { titre: string; aide: string; lancer: () => Promise<T>; libelle: string; rendre: (d: T) => React.ReactNode }) {
  const [d, setD] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const { mode } = useMarche();
  async function go() {
    setEnCours(true); setErr(null);
    try { setD(await lancer()); } catch (e) { setD(null); setErr(e instanceof ErreurApi ? e.message : "Calcul impossible."); } finally { setEnCours(false); }
  }
  return (
    <section className="panneau" aria-label={titre}>
      <header className="panneau-tete"><h2>{titre}</h2></header>
      {mode === "apprenant" && <p className="aide">{aide}</p>}
      <button className="btn btn-principal strat-lancer" onClick={go} disabled={enCours}>{enCours ? "Calcul en cours…" : libelle}</button>
      {err && <p className="erreur" role="alert">{err}</p>}
      {d && <div style={{ marginTop: "0.9rem" }}>{rendre(d)}</div>}
    </section>
  );
}

const ligneMetrique = (m: MetriquesAgent) => [pctSigne(m.rendement_total, 1), pct(m.volatilite, 1), nombre(m.sharpe, 2), pct(m.drawdown_max, 1), pct(m.temps_investi, 0), String(m.aller_retours)];

export default function PageIA() {
  const { actifs, utilisateur } = useMarche();
  const negociables = useMemo(() => actifs.filter((a) => a.tradable && a.disponible), [actifs]);
  const [symbole, setSymbole] = useState("");
  const s = symbole || negociables.find((a) => a.symbole === "AAPL")?.symbole || negociables[0]?.symbole || "";
  const q = encodeURIComponent(s);

  if (utilisateur.role === "apprenant") {
    return <main className="page page-etroite"><h1>Intelligence artificielle</h1><p className="aide">Ces outils sont réservés aux rôles trader, formateur et administrateur. Demandez à un administrateur de changer votre rôle.</p></main>;
  }
  return (
    <main className="page">
      <header className="page-tete">
        <h1>Intelligence artificielle sur les marchés</h1>
        <p className="aide">Des modèles appris sur le passé de l&apos;actif choisi, jusqu&apos;à votre date simulée seulement. Chaque résultat est comparé à une référence simple et donné avec sa marge d&apos;erreur : sur des prix journaliers, la plupart des modèles ne font pas mieux que le hasard, et c&apos;est une information utile.</p>
      </header>
      <div className="champ" style={{ maxWidth: "30rem" }}>
        <label htmlFor="ia-actif">Actif étudié</label>
        <select id="ia-actif" value={s} onChange={(e) => setSymbole(e.target.value)}>{negociables.map((a) => <option key={a.symbole} value={a.symbole}>{a.symbole} · {a.nom}</option>)}</select>
      </div>
      <div className="grille-2">
        <Bloc<PredictionIA> key={`p${s}`} titre="Prédire le sens de la prochaine séance" aide="Le modèle apprend sur le passé et prédit la séance suivante, jour après jour, sans jamais voir ce qu'il prédit (marche avant)." libelle="Évaluer et prédire"
          lancer={() => api<PredictionIA>(`/api/v1/ia/predire/${q}`)} rendre={(d) => (
            <>
              <p className="z-score">{pct(d.proba_hausse, 0)}</p>
              <p className="aide">Probabilité estimée que la prochaine séance soit haussière (modèle logistique, données jusqu&apos;au {d.dernier_jour}).</p>
              <table className="tableau tableau-gauche">
                <caption className="sr-only">Précision de chaque modèle en marche avant</caption>
                <thead><tr><th>Modèle</th><th>Précision</th><th>± marge (95 %)</th></tr></thead>
                <tbody>{d.resultats.map((r) => <tr key={r.cle}><td>{r.nom}{r.cle === d.meilleur ? " ★" : ""}</td><td>{pct(r.precision, 1)}</td><td>±{pct(r.marge, 1)}</td></tr>)}</tbody>
              </table>
              <p className={`statut ${d.dans_le_bruit ? "alerte-texte" : "gain"}`}>{d.dans_le_bruit ? "!" : "✓"} {d.conclusion}</p>
              <p className="aide">Évalué sur {d.n_test} séances. Ce qui pèse dans la prédiction du jour :</p>
              <ul className="strat-prudence">{d.contributions.slice(0, 4).map((c) => <li key={c.variable}>{c.libelle} : {c.contribution > 0 ? "▲ pousse vers la hausse" : "▼ pousse vers la baisse"} ({nombre(c.contribution, 2)})</li>)}</ul>
            </>
          )} />
        <Bloc<RegimesIA> key={`r${s}`} titre="Régime de marché" aide="Un algorithme regroupe les périodes qui se ressemblent (rendement et volatilité sur 20 jours) en trois états." libelle="Détecter le régime"
          lancer={() => api<RegimesIA>(`/api/v1/ia/regimes/${q}`)} rendre={(d) => (
            <>
              <p className="z-score" style={{ fontSize: "2rem" }}>{d.regime_actuel}</p>
              <p className="aide">Depuis {d.depuis_jours} séance(s).</p>
              <table className="tableau tableau-gauche">
                <caption className="sr-only">Les trois régimes détectés</caption>
                <thead><tr><th>Régime</th><th>Part du temps</th><th>Rendement annualisé</th><th>Volatilité</th></tr></thead>
                <tbody>{d.regimes.map((r) => <tr key={r.regime}><td>{r.regime}</td><td>{pct(r.part, 0)}</td><td>{pctSigne(r.rendement_annualise, 0)}</td><td>{pct(r.volatilite_annualisee, 0)}</td></tr>)}</tbody>
              </table>
              <p className="aide">{d.note}</p>
            </>
          )} />
        <Bloc<AnomaliesIA> key={`a${s}`} titre="Jours anormaux" aide="Un jour est anormal quand son rendement ou son volume s'écarte beaucoup de l'ordinaire de l'année écoulée." libelle="Chercher les anomalies"
          lancer={() => api<AnomaliesIA>(`/api/v1/ia/anomalies/${q}`)} rendre={(d) => (
            <>
              <p>{d.nb} jour(s) anormal(aux) sur les {d.fenetre} dernières séances.</p>
              {d.anomalies.length > 0 && (
                <table className="tableau tableau-gauche">
                  <caption className="sr-only">Jours anormaux</caption>
                  <thead><tr><th>Jour</th><th>Rendement</th><th>Nature</th></tr></thead>
                  <tbody>{d.anomalies.map((a) => <tr key={a.jour}><td>{a.jour}</td><td className={a.rendement >= 0 ? "gain" : "perte"}>{a.rendement >= 0 ? "▲ " : "▼ "}{pctSigne(a.rendement, 1)}</td><td>{a.type}</td></tr>)}</tbody>
                </table>
              )}
              <p className="aide">{d.note}</p>
            </>
          )} />
        <Bloc<AgentIA> key={`g${s}`} titre="Agent de trading (apprentissage par renforcement)" aide="Un agent apprend par essais et erreurs quand rester investi ou sortir. Il est entraîné sur le passé ancien et jugé uniquement sur la période récente." libelle="Entraîner et juger l'agent"
          lancer={() => api<AgentIA>(`/api/v1/ia/agent/${q}`)} rendre={(d) => (
            <>
              <p className="aide">Entraîné du {d.entrainement.debut} au {d.entrainement.fin}, jugé du {d.test.debut} au {d.test.fin} ({d.test.jours} séances), coût {nombre(d.cout_bps, 1)} points de base par changement.</p>
              <table className="tableau tableau-gauche">
                <caption className="sr-only">Agent contre achat-conservation sur la période de test</caption>
                <thead><tr><th>Stratégie</th><th>Rendement</th><th>Volatilité</th><th>Sharpe</th><th>Pire baisse</th><th>Investi</th><th>Allers-retours</th></tr></thead>
                <tbody>
                  <tr><td>Agent</td>{ligneMetrique(d.agent).map((x, i) => <td key={i}>{x}</td>)}</tr>
                  <tr><td>Achat-conservation</td>{ligneMetrique(d.achat_conservation).map((x, i) => <td key={i}>{x}</td>)}</tr>
                </tbody>
              </table>
              <details className="strat-aide" style={{ padding: "0.5rem 0" }}>
                <summary>Ce que l&apos;agent a appris (9 situations)</summary>
                <table className="tableau tableau-gauche"><thead><tr><th>Situation</th><th>S&apos;il est dehors</th><th>S&apos;il est investi</th></tr></thead>
                  <tbody>{d.politique.map((p) => <tr key={p.etat}><td>{p.etat}</td><td>{p.hors_marche}</td><td>{p.investi}</td></tr>)}</tbody></table>
              </details>
              <p className="aide">{d.note}</p>
            </>
          )} />
      </div>
      <Bloc<OptimiseurIA> titre="Optimiser mon portefeuille" aide="Compare votre répartition à deux répartitions de référence : la variance minimale (le moins de risque possible) et la parité de risque (chaque position contribue autant au risque)." libelle="Analyser mes positions"
        lancer={() => api<OptimiseurIA>("/api/v1/ia/optimiser")} rendre={(d) => (
          <>
            <ul className="strat-prudence">{d.recommandations.map((r) => <li key={r}>{r}</li>)}</ul>
            <table className="tableau tableau-gauche">
              <caption className="sr-only">Poids actuels et poids de référence</caption>
              <thead><tr><th>Position</th><th>Poids actuel</th><th>Part du risque</th><th>Variance minimale</th><th>Parité de risque</th></tr></thead>
              <tbody>{d.lignes.map((l) => <tr key={l.symbole}><td>{l.symbole}</td><td>{pct(l.poids_actuel, 0)}</td><td>{pct(l.contribution_risque, 0)}</td><td>{pct(l.poids_variance_minimale, 0)}</td><td>{pct(l.poids_parite_risque, 0)}</td></tr>)}</tbody>
            </table>
            <p className="aide">{d.note}</p>
          </>
        )} />
    </main>
  );
}
