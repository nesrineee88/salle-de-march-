"use client";

import { useEffect, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { nombre, pct } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import type { ExempleZ, ModelePDInfo, ResultatPD, ResultatZ } from "@/lib/types";
import { useMarche } from "./Contexte";

const CHAMPS_Z: { cle: string; libelle: string }[] = [
  { cle: "actif_courant", libelle: "Actif courant" }, { cle: "passif_courant", libelle: "Passif courant" }, { cle: "total_actif", libelle: "Total de l'actif" },
  { cle: "benefices_non_distribues", libelle: "Bénéfices non distribués" }, { cle: "ebit", libelle: "Résultat d'exploitation (EBIT)" },
  { cle: "capitaux_propres", libelle: "Capitaux propres" }, { cle: "total_dettes", libelle: "Total des dettes" }, { cle: "chiffre_affaires", libelle: "Chiffre d'affaires" },
];
const ZONES = {
  sain: { icone: "▲", titre: "Zone saine", classe: "gain" },
  grise: { icone: "!", titre: "Zone grise : à surveiller", classe: "alerte-texte" },
  detresse: { icone: "▼", titre: "Zone de détresse", classe: "perte" },
} as const;

function BarreSignee({ valeur, max }: { valeur: number; max: number }) {
  const largeur = Math.min(50, (Math.abs(valeur) / (max || 1)) * 50);
  return (
    <span className="barre-signee" aria-hidden="true">
      <span className={valeur >= 0 ? "bs-pos" : "bs-neg"} style={valeur >= 0 ? { left: "50%", width: `${largeur}%` } : { right: "50%", width: `${largeur}%` }} />
    </span>
  );
}

function OngletZ() {
  const { mode } = useMarche();
  const { donnees: exemples } = useLecture<ExempleZ[]>("/api/v1/credit/zscore/exemples", 3_600_000);
  const [modele, setModele] = useState<"z" | "z2">("z");
  const [valeurs, setValeurs] = useState<Record<string, string>>({});
  const [resultat, setResultat] = useState<ResultatZ | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  function charger(e: ExempleZ) { setValeurs(Object.fromEntries(Object.entries(e.comptes).map(([k, v]) => [k, String(v)]))); setResultat(null); setErreur(null); }
  async function calculer(ev: React.FormEvent) {
    ev.preventDefault(); setErreur(null);
    try {
      const corps: Record<string, unknown> = { modele };
      for (const c of CHAMPS_Z) corps[c.cle] = Number((valeurs[c.cle] ?? "").replace(",", "."));
      setResultat(await api<ResultatZ>("/api/v1/credit/zscore", { methode: "POST", corps }));
    } catch (e) { setResultat(null); setErreur(e instanceof ErreurApi ? e.message : "Calcul impossible."); }
  }
  const zone = resultat ? ZONES[resultat.zone] : null;
  const maxContribution = resultat ? Math.max(...resultat.contributions.map((c) => Math.abs(c.contribution))) : 1;

  return (
    <div className="grille-courbe">
      <form className="panneau" onSubmit={calculer}>
        <header className="panneau-tete"><h2>Bilan de l&apos;entreprise</h2></header>
        {mode === "apprenant" && <p className="aide">Le score Z d&apos;Altman combine cinq ratios comptables en un seul chiffre : plus il est bas, plus la faillite est probable. C&apos;est un repère statistique ancien, pas une promesse.</p>}
        <div className="crise-modeles" role="group" aria-label="Exemples fictifs">
          <span className="discret">Exemples fictifs :</span>
          {(exemples ?? []).map((e) => <button key={e.nom} type="button" className="puce" onClick={() => charger(e)}>{e.nom}</button>)}
        </div>
        <div className="champ">
          <label htmlFor="z-modele">Version du score</label>
          <select id="z-modele" value={modele} onChange={(e) => setModele(e.target.value as "z" | "z2")}>
            <option value="z">Z (1968) : industrielles cotées</option>
            <option value="z2">Z&apos;&apos; (1995) : non industrielles et émergentes</option>
          </select>
        </div>
        <div className="strat-champs">
          {CHAMPS_Z.map((c) => (
            <div className="champ" key={c.cle}><label htmlFor={`z-${c.cle}`}>{c.libelle}</label>
              <input id={`z-${c.cle}`} inputMode="decimal" required value={valeurs[c.cle] ?? ""} onChange={(e) => setValeurs({ ...valeurs, [c.cle]: e.target.value })} /></div>
          ))}
        </div>
        <p className="aide">{modele === "z" ? "Pour Z, les capitaux propres sont à la valeur de marché (capitalisation boursière)." : "Pour Z'', les capitaux propres sont à la valeur comptable ; le chiffre d'affaires n'est pas utilisé."}</p>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <button className="btn btn-principal strat-lancer" type="submit">Calculer le score</button>
      </form>

      <section className="panneau" aria-labelledby="titre-z">
        <header className="panneau-tete"><h2 id="titre-z">Résultat</h2></header>
        {resultat && zone ? (
          <>
            <p className={`z-score ${zone.classe}`}>{nombre(resultat.z, 2)}</p>
            <p className={`statut ${zone.classe}`}><span aria-hidden="true">{zone.icone}</span> {zone.titre}</p>
            <p className="aide">Sain au-dessus de {resultat.seuil_sain}, détresse en dessous de {resultat.seuil_detresse}.</p>
            <table className="tableau tableau-gauche">
              <caption className="sr-only">Contribution de chaque ratio au score</caption>
              <thead><tr><th>Ratio</th><th>Valeur</th><th>Poids</th><th>Contribution</th></tr></thead>
              <tbody>
                {resultat.contributions.map((c) => (
                  <tr key={c.ratio}><td>{c.libelle}</td><td>{nombre(c.valeur, 3)}</td><td>×{c.coefficient}</td>
                    <td><BarreSignee valeur={c.contribution} max={maxContribution} /> {nombre(c.contribution, 2)}</td></tr>
                ))}
              </tbody>
            </table>
          </>
        ) : <p className="vide">Choisissez un exemple ou saisissez un bilan, puis calculez.</p>}
      </section>
    </div>
  );
}

function OngletPD() {
  const { mode } = useMarche();
  const { donnees: modele, erreur: erreurModele } = useLecture<ModelePDInfo>("/api/v1/credit/pd/modele", 3_600_000);
  const [valeurs, setValeurs] = useState<Record<string, string>>({});
  const [resultat, setResultat] = useState<ResultatPD | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => { if (modele && Object.keys(valeurs).length === 0) setValeurs(Object.fromEntries(modele.variables.map((v) => [v.nom, String(Math.round(v.mediane * 100) / 100)]))); }, [modele, valeurs]);

  async function calculer(ev: React.FormEvent) {
    ev.preventDefault(); setErreur(null);
    try {
      const corps = { valeurs: Object.fromEntries(Object.entries(valeurs).map(([k, v]) => [k, Number(v.replace(",", "."))])) };
      setResultat(await api<ResultatPD>("/api/v1/credit/pd", { methode: "POST", corps }));
    } catch (e) { setResultat(null); setErreur(e instanceof ErreurApi ? e.message : "Calcul impossible."); }
  }
  const maxC = resultat ? Math.max(...resultat.contributions.map((c) => Math.abs(c.contribution))) : 1;

  if (erreurModele) return <p className="erreur" role="alert">{erreurModele}</p>;
  if (!modele) return <p className="vide">Chargement du modèle…</p>;
  return (
    <>
      <p className={modele.source === "synthetique" ? "bandeau avertissement" : "aide"} role="note">{modele.avertissement}</p>
      <div className="grille-courbe">
        <form className="panneau" onSubmit={calculer}>
          <header className="panneau-tete"><h2>Profil de l&apos;emprunteur</h2></header>
          {mode === "apprenant" && <p className="aide">La probabilité de défaut (PD) est la chance estimée qu&apos;un emprunteur ait un retard de paiement grave dans les deux ans. Les valeurs de départ sont les médianes du jeu de données.</p>}
          <div className="strat-champs">
            {modele.variables.map((v) => (
              <div className="champ" key={v.nom}><label htmlFor={`pd-${v.nom}`}>{v.libelle}</label>
                <input id={`pd-${v.nom}`} inputMode="decimal" value={valeurs[v.nom] ?? ""} aria-describedby={`aide-${v.nom}`} onChange={(e) => setValeurs({ ...valeurs, [v.nom]: e.target.value })} />
                <small id={`aide-${v.nom}`} className="discret">{v.aide} ({v.min} à {v.max})</small></div>
            ))}
          </div>
          {erreur && <p className="erreur" role="alert">{erreur}</p>}
          <button className="btn btn-principal strat-lancer" type="submit">Estimer la probabilité de défaut</button>
        </form>

        <section className="panneau" aria-labelledby="titre-pd">
          <header className="panneau-tete"><h2 id="titre-pd">Résultat</h2></header>
          {resultat ? (
            <>
              <p className="z-score">{pct(resultat.pd, 1)}</p>
              <p className="aide">Taux de défaut moyen du jeu de données : {pct(resultat.taux_defaut_moyen, 1)}. Cet emprunteur est {resultat.pd > resultat.taux_defaut_moyen ? "plus" : "moins"} risqué que la moyenne.</p>
              <table className="tableau tableau-gauche">
                <caption className="sr-only">Contribution de chaque variable (en log des chances)</caption>
                <thead><tr><th>Variable</th><th>Valeur</th><th>Effet sur le risque</th></tr></thead>
                <tbody>
                  {resultat.contributions.map((c) => (
                    <tr key={c.variable}><td>{c.libelle}</td><td>{nombre(c.valeur, 2)}</td>
                      <td><BarreSignee valeur={c.contribution} max={maxC} /> {c.contribution > 0 ? "▲ " : c.contribution < 0 ? "▼ " : ""}{nombre(c.contribution, 2)}</td></tr>
                  ))}
                </tbody>
              </table>
              <p className="aide">Un effet positif (▲) augmente la probabilité de défaut, un effet négatif (▼) la diminue. La somme des effets et du point de départ ({nombre(resultat.intercept, 2)}) donne exactement le log des chances ({nombre(resultat.logit, 2)}).</p>
            </>
          ) : <p className="vide">Renseignez le profil puis estimez.</p>}
        </section>
      </div>

      <section className="panneau panneau-tableau" aria-labelledby="titre-qualite">
        <header className="panneau-tete strat-tete-tableau"><h2 id="titre-qualite">Qualité du modèle (sur {modele.metriques.n_test.toLocaleString("fr-FR")} emprunteurs mis de côté)</h2></header>
        <dl className="mini-indicateurs">
          <div><dt>AUC, régression logistique</dt><dd>{nombre(modele.metriques.auc_logistique, 3)}</dd></div>
          <div><dt>AUC, arbres boostés (comparaison)</dt><dd>{nombre(modele.metriques.auc_arbres_boostes, 3)}</dd></div>
          <div><dt>Erreur de Brier (référence : {nombre(modele.metriques.brier_reference, 4)})</dt><dd>{nombre(modele.metriques.brier, 4)}</dd></div>
        </dl>
        <div className="tableau-defile">
          <table className="tableau">
            <caption className="sr-only">Calibration : probabilité prédite et taux observé par dixième de risque</caption>
            <thead><tr><th>Dixième de risque</th><th>PD moyenne prédite</th><th>Taux de défaut observé</th></tr></thead>
            <tbody>{modele.metriques.calibration.map((c) => <tr key={c.groupe}><td>{c.groupe}</td><td>{pct(c.pd_moyenne, 1)}</td><td>{pct(c.taux_observe, 1)}</td></tr>)}</tbody>
          </table>
        </div>
        {mode === "apprenant" && <p className="aide" style={{ padding: "0.75rem 1.1rem" }}>L&apos;AUC mesure si le modèle classe bien les emprunteurs (0,5 = hasard, 1 = parfait). La calibration vérifie que « 10 % prédit » correspond bien à environ 10 % de défauts observés.</p>}
      </section>
    </>
  );
}

export default function PageCredit() {
  const [onglet, setOnglet] = useState<"z" | "pd">("z");
  return (
    <main className="page">
      <header className="page-tete">
        <h1>Risque de crédit : score Z et probabilité de défaut</h1>
        <p className="aide">Deux outils pour juger la solidité d&apos;un emprunteur : le score Z d&apos;Altman (entreprises, à partir du bilan) et un modèle statistique de probabilité de défaut (particuliers, expliqué variable par variable).</p>
      </header>
      <div className="onglets" role="tablist" aria-label="Outil">
        <button role="tab" aria-selected={onglet === "z"} className="onglet" onClick={() => setOnglet("z")}>Score Z d&apos;Altman</button>
        <button role="tab" aria-selected={onglet === "pd"} className="onglet" onClick={() => setOnglet("pd")}>Probabilité de défaut (PD)</button>
      </div>
      {onglet === "z" ? <OngletZ /> : <OngletPD />}
    </main>
  );
}
