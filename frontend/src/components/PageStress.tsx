"use client";

import { useEffect, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { nombre, pct } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import type { ChocInverse, Comparaison, ComparaisonIA, ExplicationIA, FenetreChoc, ListeBanques, ResultatStress } from "@/lib/types";
import { useMarche } from "./Contexte";

const STATUT = {
  ok: { icone: "✓", titre: "Au-dessus du coussin (7 %)", classe: "gain" },
  sous_coussin: { icone: "!", titre: "Sous le coussin de 7 %", classe: "alerte-texte" },
  sous_minimum: { icone: "✕", titre: "Sous le minimum de 4,5 %", classe: "perte" },
} as const;

function BarreSignee({ valeur, max }: { valeur: number; max: number }) {
  const l = Math.min(50, (Math.abs(valeur) / (max || 1)) * 50);
  return <span className="barre-signee" aria-hidden="true"><span className={valeur >= 0 ? "bs-pos" : "bs-neg"} style={valeur >= 0 ? { left: "50%", width: `${l}%` } : { right: "50%", width: `${l}%` }} /></span>;
}
const pts = (v: number) => `${v > 0 ? "▲ +" : v < 0 ? "▼ −" : ""}${nombre(Math.abs(v), 2)} pt`;

export default function PageStress() {
  const { utilisateur, mode } = useMarche();
  const { donnees: liste, erreur } = useLecture<ListeBanques>("/api/v1/stress/banques", 3_600_000);
  const { donnees: hist } = useLecture<{ fenetres: FenetreChoc[] }>("/api/v1/stress/chocs-historiques", 3_600_000);
  const [chocs, setChocs] = useState<Record<string, number>>({ energie: -30, metaux_precieux: 0, metaux_industriels: -20, agricole: -10 });
  const [indice, setIndice] = useState(0);
  const [resultat, setResultat] = useState<ResultatStress | null>(null);
  const [comparaison, setComparaison] = useState<Comparaison | null>(null);
  const [inverse, setInverse] = useState<{ minimum: ChocInverse; coussin: ChocInverse } | null>(null);
  const [ia, setIa] = useState<ComparaisonIA | null>(null);
  const [expl, setExpl] = useState<ExplicationIA | null>(null);
  const [messageErreur, setMessageErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const avance = utilisateur.role !== "apprenant";

  const banque = liste?.banques[indice];
  const chocsFraction = () => Object.fromEntries(Object.entries(chocs).map(([k, v]) => [k, v / 100]));

  async function lancer<T>(f: () => Promise<T>): Promise<T | null> {
    setEnCours(true); setMessageErreur(null);
    try { return await f(); } catch (e) { setMessageErreur(e instanceof ErreurApi ? e.message : "Calcul impossible."); return null; } finally { setEnCours(false); }
  }
  useEffect(() => { setResultat(null); setInverse(null); setExpl(null); }, [indice]);

  async function simuler() {
    if (!banque) return;
    const r = await lancer(() => api<ResultatStress>("/api/v1/stress/simuler", { methode: "POST", corps: { banque, chocs: chocsFraction() } }));
    if (r) setResultat(r);
  }
  async function comparer() {
    const r = await lancer(() => api<Comparaison>("/api/v1/stress/comparer", { methode: "POST", corps: { chocs: chocsFraction() } }));
    if (r) setComparaison(r);
  }
  async function chercherInverse() {
    if (!banque) return;
    const r = await lancer(() => api<{ minimum: ChocInverse; coussin: ChocInverse }>("/api/v1/stress/inverse", { methode: "POST", corps: { banque } }));
    if (r) setInverse(r);
  }
  async function comparerIA() { const r = await lancer(() => api<ComparaisonIA>("/api/v1/stress/ia/comparaison", { methode: "POST" })); if (r) setIa(r); }
  async function expliquer() {
    if (!banque || !ia) return;
    const r = await lancer(() => api<ExplicationIA>("/api/v1/stress/ia/explication", { methode: "POST", corps: { banque, chocs: chocsFraction(), modele: ia.meilleur } }));
    if (r) setExpl(r);
  }
  function appliquerFenetre(f: FenetreChoc) {
    setChocs(Object.fromEntries((liste?.groupes ?? []).map((g) => [g.cle, Math.round((f.chocs[g.cle] ?? 0) * 100)])));
  }
  const maxCanal = resultat ? Math.max(...resultat.canaux.map((c) => Math.abs(c.perte)), 0.0001) : 1;
  const st = resultat ? STATUT[resultat.statut] : null;

  return (
    <main className="page">
      <header className="page-tete">
        <h1>Stress tests bancaires : conventionnel contre islamique</h1>
        <p className="aide">Que devient le ratio de fonds propres (CET1) d&apos;une banque si les matières premières s&apos;effondrent ou s&apos;envolent ? La banque conventionnelle prête aux producteurs et prend des positions ; la banque islamique finance par mourabaha, salam et istisna, et partage une partie des pertes avec ses déposants.</p>
      </header>
      {liste && <p className="bandeau avertissement" role="note">{liste.avertissement}</p>}
      {(erreur || messageErreur) && <p className="erreur" role="alert">{erreur ?? messageErreur}</p>}

      <section className="panneau" aria-labelledby="titre-chocs">
        <header className="panneau-tete"><h2 id="titre-chocs">1. Le choc sur les matières premières</h2></header>
        <div className="crise-modeles" role="group" aria-label="Chocs historiques mesurés sur les prix">
          <span className="discret">Mesurer sur l&apos;histoire :</span>
          {(hist?.fenetres ?? []).map((f) => <button key={f.cle} type="button" className="puce" onClick={() => appliquerFenetre(f)} title={f.notes.join(" ")}>{f.nom}</button>)}
        </div>
        <div className="strat-champs">
          {(liste?.groupes ?? []).map((g) => (
            <div className="champ" key={g.cle}>
              <label htmlFor={`choc-${g.cle}`}>{g.libelle} : {chocs[g.cle] > 0 ? "+" : ""}{chocs[g.cle]} %</label>
              <input id={`choc-${g.cle}`} type="range" min={-90} max={100} step={5} value={chocs[g.cle]} onChange={(e) => setChocs({ ...chocs, [g.cle]: Number(e.target.value) })} />
            </div>
          ))}
        </div>
        {mode === "apprenant" && <p className="aide">Les valeurs historiques sont mesurées sur les vrais prix du simulateur (la plus forte variation depuis le début de la période). Un prix négatif (WTI, avril 2020) est ignoré.</p>}
        <button className="btn btn-principal strat-lancer" onClick={comparer} disabled={enCours || !liste}>Comparer les 12 banques</button>
      </section>

      {comparaison && (
        <section className="panneau panneau-tableau" aria-labelledby="titre-comp">
          <header className="panneau-tete strat-tete-tableau"><h2 id="titre-comp">2. Qui résiste le mieux ?</h2></header>
          <dl className="mini-indicateurs" style={{ padding: "0 1.1rem" }}>
            {Object.entries(comparaison.par_type).map(([t, v]) => (
              <div key={t}><dt>{t === "islamique" ? "Banques islamiques" : "Banques conventionnelles"} : variation moyenne du CET1</dt><dd>{pts(v.variation_moyenne)} <span className="discret">(pire : {pts(v.pire)})</span></dd></div>
            ))}
          </dl>
          <div className="tableau-defile">
            <table className="tableau tableau-gauche">
              <caption className="sr-only">Ratio CET1 avant et après le choc, banque par banque</caption>
              <thead><tr><th>Banque</th><th>CET1 avant</th><th>CET1 après</th><th>Variation</th><th>Situation</th></tr></thead>
              <tbody>
                {comparaison.banques.map((b) => (
                  <tr key={b.banque}><td>{b.banque}</td><td>{pct(b.ratio_avant, 1)}</td><td>{pct(b.ratio_apres, 1)}</td><td className={b.variation_points < 0 ? "perte" : "gain"}>{pts(b.variation_points)}</td>
                    <td className={STATUT[b.statut].classe}>{STATUT[b.statut].icone} {STATUT[b.statut].titre}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="panneau" aria-labelledby="titre-detail">
        <header className="panneau-tete"><h2 id="titre-detail">3. D&apos;où viennent les pertes d&apos;une banque ?</h2></header>
        <div className="champ" style={{ maxWidth: "34rem" }}>
          <label htmlFor="banque">Banque</label>
          <select id="banque" value={indice} onChange={(e) => setIndice(Number(e.target.value))}>
            {(liste?.banques ?? []).map((b, i) => <option key={b.nom} value={i}>{b.nom}</option>)}
          </select>
        </div>
        <div className="direct-actions">
          <button className="btn btn-principal" style={{ width: "auto" }} onClick={simuler} disabled={enCours || !banque}>Appliquer le choc</button>
          <button className="btn" onClick={chercherInverse} disabled={enCours || !banque}>Quel choc la ferait tomber ?</button>
        </div>
        {resultat && st && (
          <div style={{ marginTop: "1rem" }}>
            <p className="z-score">{pct(resultat.ratio_apres, 1)} <span className="discret" style={{ fontSize: "1rem" }}>de CET1 juste après le choc (avant : {pct(resultat.ratio_avant, 1)}, {pts(resultat.variation_points)})</span></p>
            <p className="aide">Avec le résultat avant provisions d&apos;une année de plus ({nombre(resultat.resultat_periode, 2)} Md), le ratio serait de {pct(resultat.ratio_avec_resultat, 1)}. L&apos;impact immédiat n&apos;en tient volontairement pas compte.</p>
            <p className={`statut ${st.classe}`}><span aria-hidden="true">{st.icone}</span> {st.titre}</p>
            <table className="tableau tableau-gauche">
              <caption className="sr-only">Pertes par canal, en milliards</caption>
              <thead><tr><th>Canal</th><th>Perte (Md)</th><th>Détail</th></tr></thead>
              <tbody>
                {resultat.canaux.map((c) => (
                  <tr key={c.cle}><td className="cellule-large">{c.libelle}</td><td><BarreSignee valeur={c.perte} max={maxCanal} /> {nombre(c.perte, 2)}</td><td className="cellule-large discret">{c.explication}</td></tr>
                ))}
                <tr><th scope="row">Perte supportée par la banque</th><td>{nombre(resultat.perte_supportee, 2)}</td><td className="discret">Part de la perte prise en charge par la banque</td></tr>
              </tbody>
            </table>
            {mode === "apprenant" && <p className="aide">Une barre vers la droite (orange) est une perte, vers la gauche (bleu) un gain ou une perte absorbée par les déposants. Les actifs pondérés des risques sont supposés constants.</p>}
          </div>
        )}
        {inverse && (
          <ul className="strat-prudence" style={{ marginTop: "1rem" }}>
            <li>Minimum de Bâle III (4,5 %) : {inverse.minimum.message}</li>
            <li>Avec le coussin de conservation (7 %) : {inverse.coussin.message}</li>
          </ul>
        )}
      </section>

      {avance ? (
        <section className="panneau" aria-labelledby="titre-ia-stress">
          <header className="panneau-tete"><h2 id="titre-ia-stress">4. L&apos;apprentissage automatique reproduit-il le calcul ?</h2></header>
          <button className="btn btn-principal strat-lancer" onClick={comparerIA} disabled={enCours}>{enCours && !ia ? "Entraînement…" : "Comparer trois modèles"}</button>
          {ia && (
            <>
              <table className="tableau tableau-gauche" style={{ marginTop: "0.75rem" }}>
                <caption className="sr-only">Précision de chaque modèle sur des banques mises de côté</caption>
                <thead><tr><th>Modèle</th><th>R² (1 = parfait)</th><th>Erreur moyenne (points de CET1)</th></tr></thead>
                <tbody>{ia.comparaison.map((c) => <tr key={c.cle}><td>{c.nom}{c.cle === ia.meilleur ? " ★" : ""}</td><td>{nombre(c.r2, 3)}</td><td>{nombre(c.erreur_absolue_moyenne, 2)}</td></tr>)}</tbody>
              </table>
              <p className="aide">{ia.avertissement}</p>
              <h3 className="sous-titre">Variables les plus importantes (permutation, sur le meilleur modèle)</h3>
              <ol className="strat-prudence">{ia.importance.slice(0, 6).map((i) => <li key={i.variable}>{i.libelle} ({nombre(i.importance, 3)})</li>)}</ol>
              <button className="btn" onClick={expliquer} disabled={enCours || !banque}>Expliquer la prédiction pour la banque choisie</button>
              {expl && (
                <div style={{ marginTop: "0.75rem" }}>
                  <p>Le modèle prédit {pts(expl.prediction_points)} ; le modèle structurel donne {pts(expl.reference_structurelle_points)}.</p>
                  <table className="tableau tableau-gauche">
                    <caption className="sr-only">Effet de chaque variable sur la prédiction</caption>
                    <thead><tr><th>Variable</th><th>Valeur</th><th>Effet sur la variation du CET1 (points)</th></tr></thead>
                    <tbody>{expl.attributions.map((a) => <tr key={a.variable}><td>{a.libelle}</td><td>{nombre(a.valeur, 3)}</td><td><BarreSignee valeur={-a.effet} max={Math.max(...expl.attributions.map((x) => Math.abs(x.effet)))} /> {nombre(a.effet, 2)}</td></tr>)}</tbody>
                  </table>
                  <p className="aide">{expl.note}</p>
                </div>
              )}
            </>
          )}
        </section>
      ) : (
        <p className="aide">La comparaison de modèles d&apos;apprentissage automatique est réservée aux rôles trader, formateur et administrateur.</p>
      )}
    </main>
  );
}
