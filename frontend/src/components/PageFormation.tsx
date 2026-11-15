"use client";

import { useState } from "react";
import { Check, Flame, Gamepad2, GraduationCap, Lock, Play, Swords, Trophy } from "lucide-react";
import { api } from "@/lib/api";
import { nombre, pct, pctSigne } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import { niveauDepuis, useJeux } from "@/lib/jeux";
import type { LigneClasse, LigneLigue, ListeLecons, ResumeLecon } from "@/lib/types";
import { useMarche } from "./Contexte";
import DefiMars2020 from "./DefiMars2020";
import JeuPiege from "./JeuPiege";
import LeconInteractive from "./LeconInteractive";

function Ligue() {
  const [date, setDate] = useState("");
  const { donnees } = useLecture<{ classement: LigneLigue[]; regle: string }>(`/api/v1/formation/ligue${date ? `?jusqu_au=${date}` : ""}`, 10_000);
  return (
    <section className="panneau panneau-tableau" aria-labelledby="titre-ligue">
      <header className="panneau-tete strat-tete-tableau"><h2 id="titre-ligue">Ligue : rendement ajusté du risque</h2></header>
      <div className="champ" style={{ padding: "0 1.1rem", maxWidth: "26rem" }}>
        <label htmlFor="ligue-date">Juger tout le monde à la même date simulée (facultatif)</label>
        <input id="ligue-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </div>
      <p className="aide" style={{ padding: "0 1.1rem" }}>{donnees?.regle}</p>
      <div className="tableau-defile">
        {donnees && donnees.classement.length > 0 ? (
          <table className="tableau tableau-gauche">
            <caption className="sr-only">Classement de la ligue</caption>
            <thead><tr><th>Rang</th><th>Joueur</th><th>Score</th><th>Rendement</th><th>Pire baisse</th><th>Date simulée</th></tr></thead>
            <tbody>{donnees.classement.map((l) => <tr key={l.nom}><td>{l.rang}</td><td>{l.nom}</td><td>{nombre(l.score, 2)}</td>
              <td className={l.rendement >= 0 ? "gain" : "perte"}>{l.rendement >= 0 ? "▲ " : "▼ "}{pctSigne(l.rendement, 1)}</td><td>{pct(l.drawdown, 1)}</td><td>{l.date_simulee}</td></tr>)}</tbody>
          </table>
        ) : <p className="vide">Personne n&apos;est encore classé : il faut au moins 5 jours simulés avec un portefeuille.</p>}
      </div>
    </section>
  );
}

function Classe() {
  const { donnees } = useLecture<LigneClasse[]>("/api/v1/formation/classe", 10_000);
  return (
    <section className="panneau panneau-tableau" aria-labelledby="titre-classe">
      <header className="panneau-tete strat-tete-tableau"><h2 id="titre-classe">Ma classe</h2></header>
      <div className="tableau-defile">
        <table className="tableau tableau-gauche">
          <caption className="sr-only">Progression et portefeuille de chaque apprenant</caption>
          <thead><tr><th>Nom</th><th>Rôle</th><th>Profil de risque</th><th>Leçons réussies</th><th>Score moyen</th><th>Rendement</th><th>Pire baisse</th><th>Date simulée</th></tr></thead>
          <tbody>{(donnees ?? []).map((l) => (
            <tr key={l.id}><td>{l.nom}</td><td>{l.role}</td><td>{l.profil_risque ?? "non renseigné"}</td><td>{l.lecons_reussies} / {l.lecons_actives}</td><td>{l.score_moyen === null ? "–" : pct(l.score_moyen, 0)}</td>
              <td>{l.portefeuille ? pctSigne(l.portefeuille.rendement, 1) : "–"}</td><td>{l.portefeuille ? pct(l.portefeuille.drawdown, 1) : "–"}</td><td>{l.portefeuille?.date_simulee ?? "–"}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

const VUES = [
  { cle: "parcours", libelle: "Parcours", icone: GraduationCap },
  { cle: "jeu", libelle: "Repère le piège", icone: Gamepad2 },
  { cle: "defi", libelle: "Défi mars 2020", icone: Swords },
  { cle: "ligue", libelle: "Ligue", icone: Trophy },
] as const;
type Vue = (typeof VUES)[number]["cle"] | "classe";

/** Carte de progression : niveau, points, avancement vers le niveau suivant. */
function Progression({ lecons, pointsJeux }: { lecons: ResumeLecon[]; pointsJeux: number }) {
  const pointsLecons = lecons.reduce((s, l) => s + (l.reussie ? 100 + Math.round((l.meilleur_score ?? 0) * 50) : Math.round((l.meilleur_score ?? 0) * 30)), 0);
  const total = pointsLecons + pointsJeux;
  const n = niveauDepuis(total);
  const actives = lecons.filter((l) => l.active);
  const reussies = actives.filter((l) => l.reussie).length;
  return (
    <section className="panneau progression" aria-label="Ma progression">
      <div className="progression-niveau">
        <span className="progression-badge" aria-hidden="true">{n.numero}</span>
        <div>
          <p className="lecon-surtitre">Niveau {n.numero}</p>
          <h2>{n.nom}</h2>
        </div>
      </div>
      <div className="progression-barre" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(n.avancement * 100)} aria-label="Avancement vers le niveau suivant">
        <i style={{ width: `${Math.round(n.avancement * 100)}%` }} />
      </div>
      <p className="aide">{n.suivant ? `Encore ${n.restant} points pour devenir ${n.suivant}.` : "Niveau maximal atteint."}</p>
      <ul className="progression-stats">
        <li><strong>{total}</strong><span>points</span></li>
        <li><strong>{reussies}/{actives.length}</strong><span>leçons réussies</span></li>
        <li><strong>{pointsJeux}</strong><span>points de jeux</span></li>
      </ul>
    </section>
  );
}

function Parcours({ lecons, gestion, ouvrir, activer }: { lecons: ResumeLecon[]; gestion: boolean; ouvrir: (id: string) => void; activer: (id: string, actif: boolean) => Promise<void> }) {
  const visibles = lecons.filter((l) => l.active || gestion);
  const prochaine = visibles.find((l) => l.active && !l.reussie)?.id;
  return (
    <ol className="parcours" aria-label="Parcours de leçons">
      {visibles.map((l, i) => {
        const etat = l.reussie ? "faite" : l.id === prochaine ? "suivante" : l.active ? "libre" : "masquee";
        return (
          <li key={l.id} className="parcours-etape" data-etat={etat} data-cote={i % 2 === 0 ? "g" : "d"}>
            <span className="parcours-noeud" aria-hidden="true">{etat === "faite" ? <Check size={20} /> : etat === "masquee" ? <Lock size={18} /> : etat === "suivante" ? <Play size={18} fill="currentColor" /> : i + 1}</span>
            <article className="panneau parcours-carte">
              {etat === "suivante" && <span className="parcours-pastille">À faire maintenant</span>}
              <h3>{l.titre}</h3>
              <p className="aide">{l.niveau} · {l.minutes} min · {l.nb_questions} questions</p>
              <p>{l.resume}</p>
              <p className={`statut ${l.reussie ? "gain" : "discret"}`}>{l.reussie ? `✓ Réussie (${pct(l.meilleur_score ?? 0, 0)})` : l.tentatives ? `Meilleur score ${pct(l.meilleur_score ?? 0, 0)} en ${l.tentatives} essai(s)` : "Pas encore essayée"}</p>
              <div className="direct-actions">
                <button className="btn btn-principal" style={{ width: "auto", marginTop: 0 }} onClick={() => ouvrir(l.id)} disabled={!l.active && !gestion}>{l.reussie ? "Revoir" : l.tentatives ? "Reprendre" : "Commencer"}</button>
                {gestion && <label className="discret"><input type="checkbox" checked={l.active} onChange={(e) => void activer(l.id, e.target.checked)} /> Visible</label>}
              </div>
            </article>
          </li>
        );
      })}
    </ol>
  );
}

export default function PageFormation() {
  const { utilisateur } = useMarche();
  const { points: pointsJeux } = useJeux(utilisateur.email);
  const [vue, setVue] = useState<Vue>("parcours");
  const [ouverte, setOuverte] = useState<string | null>(null);
  const { donnees, relire } = useLecture<ListeLecons>("/api/v1/formation/lecons", 15_000);
  const gestion = utilisateur.role === "formateur" || utilisateur.role === "admin";

  async function activer(id: string, actif: boolean) {
    await api(`/api/v1/formation/lecons/${id}/activation`, { methode: "PATCH", corps: { actif } });
    await relire();
  }
  const changer = (v: Vue) => { setVue(v); setOuverte(null); };

  if (ouverte) {
    return <main className="page"><LeconInteractive id={ouverte} retour={() => { setOuverte(null); void relire(); }} /></main>;
  }
  return (
    <main className="page formation">
      <header className="page-tete">
        <h1>Formation</h1>
        <p className="aide">Apprenez en jouant : leçons courtes, quiz corrigés par le serveur, mini-jeu et défi dans le simulateur.</p>
      </header>

      {donnees && <Progression lecons={donnees.lecons} pointsJeux={pointsJeux} />}

      <div className="onglets formation-onglets" role="tablist" aria-label="Formation">
        {VUES.map(({ cle, libelle, icone: Icone }) => (
          <button key={cle} role="tab" aria-selected={vue === cle} className="onglet" onClick={() => changer(cle)}><Icone size={16} aria-hidden="true" /> {libelle}</button>
        ))}
        {gestion && <button role="tab" aria-selected={vue === "classe"} className="onglet" onClick={() => changer("classe")}><Flame size={16} aria-hidden="true" /> Ma classe</button>}
      </div>

      {vue === "parcours" && (donnees ? <Parcours lecons={donnees.lecons} gestion={gestion} ouvrir={setOuverte} activer={activer} /> : <p className="vide">Chargement…</p>)}
      {vue === "jeu" && <JeuPiege />}
      {vue === "defi" && <DefiMars2020 />}
      {vue === "ligue" && <Ligue />}
      {vue === "classe" && gestion && <Classe />}
    </main>
  );
}
