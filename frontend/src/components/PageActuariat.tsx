"use client";

import { useEffect, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { montant, nombre, pct } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import type { FacteurTarif, ModeleTarifInfo, ResultatCL, ResultatPrime } from "@/lib/types";
import { useMarche } from "./Contexte";

const DEFAUT: Record<string, string> = { VehPower: "7", VehAge: "5", DrivAge: "45", BonusMalus: "100", Density: "1000", VehGas: "Diesel", Area: "C" };

function Facteurs({ titre, f }: { titre: string; f: FacteurTarif[] }) {
  return (
    <div>
      <h3 className="sous-titre">{titre}</h3>
      <table className="tableau tableau-gauche">
        <caption className="sr-only">{titre}</caption>
        <thead><tr><th>Facteur</th><th>Effet par rapport au contrat moyen</th></tr></thead>
        <tbody>{f.slice(0, 5).map((x) => <tr key={x.variable}><td>{x.libelle}</td><td className={x.facteur > 1.005 ? "perte" : x.facteur < 0.995 ? "gain" : undefined}>{x.facteur > 1.005 ? "▲ " : x.facteur < 0.995 ? "▼ " : ""}×{nombre(x.facteur, 3)}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

function OngletPrime() {
  const { mode } = useMarche();
  const { donnees: modele, erreur: erreurModele } = useLecture<ModeleTarifInfo>("/api/v1/actuariat/modele", 3_600_000);
  const [v, setV] = useState<Record<string, string>>(DEFAUT);
  const [exposition, setExposition] = useState("1");
  const [frais, setFrais] = useState("20");
  const [marge, setMarge] = useState("5");
  const [r, setR] = useState<ResultatPrime | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  async function calculer(e: React.FormEvent) {
    e.preventDefault(); setErreur(null);
    try {
      const profil: Record<string, unknown> = {};
      for (const x of modele?.variables ?? []) profil[x.nom] = x.choix ? v[x.nom] : Number(v[x.nom].replace(",", "."));
      setR(await api<ResultatPrime>("/api/v1/actuariat/prime", { methode: "POST", corps: { profil, exposition: Number(exposition.replace(",", ".")), frais: Number(frais) / 100, marge: Number(marge) / 100 } }));
    } catch (exc) { setR(null); setErreur(exc instanceof ErreurApi ? exc.message : "Calcul impossible."); }
  }
  if (erreurModele) return <p className="erreur" role="alert">{erreurModele}</p>;
  if (!modele) return <p className="vide">Chargement du modèle…</p>;
  return (
    <>
      <p className={modele.source === "synthetique" ? "bandeau avertissement" : "aide"} role="note">{modele.avertissement}</p>
      <div className="grille-courbe">
        <form className="panneau" onSubmit={calculer}>
          <header className="panneau-tete"><h2>Profil du contrat</h2></header>
          {mode === "apprenant" && <p className="aide">La prime pure est ce que coûtera en moyenne le contrat (fréquence des sinistres × coût moyen). La prime commerciale y ajoute une marge de sécurité et les frais de l&apos;assureur.</p>}
          <div className="strat-champs">
            {modele.variables.map((x) => (
              <div className="champ" key={x.nom}>
                <label htmlFor={`a-${x.nom}`}>{x.libelle}</label>
                {x.choix ? (
                  <select id={`a-${x.nom}`} value={v[x.nom]} onChange={(e) => setV({ ...v, [x.nom]: e.target.value })}>{x.choix.map((c) => <option key={c}>{c}</option>)}</select>
                ) : (
                  <input id={`a-${x.nom}`} inputMode="decimal" value={v[x.nom]} onChange={(e) => setV({ ...v, [x.nom]: e.target.value })} aria-describedby={`b-${x.nom}`} />
                )}
                {!x.choix && <small id={`b-${x.nom}`} className="discret">de {x.min} à {x.max}</small>}
              </div>
            ))}
            <div className="champ"><label htmlFor="a-exp">Durée couverte (années, 0 à 1)</label><input id="a-exp" inputMode="decimal" value={exposition} onChange={(e) => setExposition(e.target.value)} /></div>
            <div className="champ"><label htmlFor="a-frais">Frais de l&apos;assureur (% de la prime)</label><input id="a-frais" inputMode="decimal" value={frais} onChange={(e) => setFrais(e.target.value)} /></div>
            <div className="champ"><label htmlFor="a-marge">Marge de sécurité (% de la prime pure)</label><input id="a-marge" inputMode="decimal" value={marge} onChange={(e) => setMarge(e.target.value)} /></div>
          </div>
          {erreur && <p className="erreur" role="alert">{erreur}</p>}
          <button className="btn btn-principal strat-lancer" type="submit">Calculer la prime</button>
        </form>
        <section className="panneau" aria-labelledby="titre-prime">
          <header className="panneau-tete"><h2 id="titre-prime">Résultat</h2></header>
          {r ? (
            <>
              <p className="z-score">{montant(r.prime_commerciale)}</p>
              <p className="aide">Prime commerciale pour la durée choisie. Probabilité d&apos;au moins un sinistre : <strong>{pct(r.probabilite_sinistre, 1)}</strong>.</p>
              <dl className="mini-indicateurs">
                <div><dt>Fréquence annuelle</dt><dd>{nombre(r.frequence_annuelle, 3)}</dd></div>
                <div><dt>Coût moyen d&apos;un sinistre</dt><dd>{montant(r.cout_moyen)}</dd></div>
                <div><dt>Prime pure</dt><dd>{montant(r.prime_pure)}</dd></div>
                <div><dt>Marge de sécurité</dt><dd>{montant(r.marge_securite)}</dd></div>
                <div><dt>Frais</dt><dd>{montant(r.frais)}</dd></div>
              </dl>
              <Facteurs titre="Ce qui pèse sur la fréquence" f={r.facteurs_frequence} />
              <Facteurs titre="Ce qui pèse sur le coût d'un sinistre" f={r.facteurs_cout} />
            </>
          ) : <p className="vide">Renseignez le profil puis calculez.</p>}
        </section>
      </div>
      <section className="panneau" aria-labelledby="titre-qual-tarif">
        <header className="panneau-tete"><h2 id="titre-qual-tarif">Qualité du modèle</h2></header>
        <dl className="mini-indicateurs">
          <div><dt>Déviance de la fréquence (référence : {nombre(modele.metriques.deviance_poisson_reference, 4)})</dt><dd>{nombre(modele.metriques.deviance_poisson, 4)}</dd></div>
          <div><dt>Déviance du coût (référence : {nombre(modele.metriques.deviance_gamma_reference, 4)})</dt><dd>{nombre(modele.metriques.deviance_gamma, 4)}</dd></div>
          <div><dt>Contrats et sinistres</dt><dd>{modele.metriques.n_contrats.toLocaleString("fr-FR")} · {modele.metriques.n_sinistres.toLocaleString("fr-FR")}</dd></div>
        </dl>
        <p className="aide">Une déviance plus basse que la référence signifie que le modèle fait mieux que d&apos;appliquer la moyenne à tout le monde.</p>
      </section>
    </>
  );
}

function OngletProvision() {
  const { mode } = useMarche();
  const [tri, setTri] = useState<(number | null)[][] | null>(null);
  const [r, setR] = useState<ResultatCL | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  useEffect(() => { api<{ triangle: (number | null)[][] }>("/api/v1/actuariat/provision/exemple").then((d) => setTri(d.triangle)).catch(() => undefined); }, []);

  function modifier(i: number, j: number, texte: string) {
    setTri((t) => t && t.map((l, a) => l.map((x, b) => (a === i && b === j ? (texte.trim() === "" ? null : Number(texte.replace(",", "."))) : x))));
  }
  async function calculer() {
    setErreur(null);
    try { setR(await api<ResultatCL>("/api/v1/actuariat/provision", { methode: "POST", corps: { triangle: tri } })); }
    catch (e) { setR(null); setErreur(e instanceof ErreurApi ? e.message : "Calcul impossible."); }
  }
  if (!tri) return <p className="vide">Chargement…</p>;
  const n = tri.length;
  return (
    <>
      <p className="bandeau avertissement" role="note">Triangle de départ INVENTÉ (règlements cumulés par année de survenance, en milliers). Modifiez les cases du triangle supérieur pour essayer vos propres chiffres.</p>
      {mode === "apprenant" && <p className="aide">Chaque ligne est une année où des sinistres sont survenus ; chaque colonne, une année de plus passée à les régler. Le Chain Ladder mesure comment les règlements grossissent d&apos;une colonne à l&apos;autre et l&apos;applique aux années encore incomplètes pour estimer ce qu&apos;il reste à payer : la provision.</p>}
      <div className="panneau tableau-defile" style={{ maxHeight: "none" }}>
        <table className="tableau tableau-gauche">
          <caption className="sr-only">Triangle de règlements cumulés</caption>
          <thead><tr><th>Survenance</th>{tri.map((_, j) => <th key={j}>Année {j}</th>)}</tr></thead>
          <tbody>
            {tri.map((l, i) => (
              <tr key={i}><th scope="row">Année {i + 1}</th>
                {l.map((x, j) => j <= n - 1 - i
                  ? <td key={j}><input aria-label={`Règlements cumulés, survenance ${i + 1}, développement ${j}`} className="case-triangle" inputMode="decimal" value={x ?? ""} onChange={(e) => modifier(i, j, e.target.value)} /></td>
                  : <td key={j} className="discret">{r ? nombre(r.triangle_complete[i][j], 0) : "·"}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <button className="btn btn-principal strat-lancer" onClick={calculer}>Calculer les provisions</button>
      </div>
      {r && (
        <section className="panneau panneau-tableau" aria-labelledby="titre-cl">
          <header className="panneau-tete strat-tete-tableau"><h2 id="titre-cl">Provision à constituer : {nombre(r.provision_totale, 0)}</h2></header>
          <p className="aide" style={{ padding: "0 1.1rem" }}>Facteurs de développement : {r.facteurs.map((f, j) => `${j}→${j + 1} : ×${nombre(f, 3)}`).join(" · ")}</p>
          <div className="tableau-defile">
            <table className="tableau tableau-gauche">
              <caption className="sr-only">Provision par année de survenance</caption>
              <thead><tr><th>Survenance</th><th>Déjà réglé</th><th>Coût final estimé</th><th>Provision</th></tr></thead>
              <tbody>{r.annees.map((a) => <tr key={a.annee}><td>Année {a.annee}</td><td>{nombre(a.dernier_connu, 0)}</td><td>{nombre(a.ultime, 0)}</td><td>{nombre(a.provision, 0)}</td></tr>)}</tbody>
            </table>
          </div>
          <p className="aide" style={{ padding: "0.75rem 1.1rem" }}>{r.limites}</p>
        </section>
      )}
    </>
  );
}

export default function PageActuariat() {
  const [onglet, setOnglet] = useState<"prime" | "provision">("prime");
  return (
    <main className="page">
      <header className="page-tete">
        <h1>Actuariat : prime d&apos;assurance et provisions</h1>
        <p className="aide">Deux calculs de base du métier : tarifer un contrat d&apos;assurance auto (prime, marge, probabilité de sinistre) et estimer ce qu&apos;il reste à payer sur les sinistres passés (provisionnement).</p>
      </header>
      <div className="onglets" role="tablist" aria-label="Outil">
        <button role="tab" aria-selected={onglet === "prime"} className="onglet" onClick={() => setOnglet("prime")}>Tarification</button>
        <button role="tab" aria-selected={onglet === "provision"} className="onglet" onClick={() => setOnglet("provision")}>Provisions (Chain Ladder)</button>
      </div>
      {onglet === "prime" ? <OngletPrime /> : <OngletProvision />}
    </main>
  );
}
