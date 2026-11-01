"use client";

import Link from "next/link";
import { useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { nombre, pct, pctSigne } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import type { CorrectionLecon, DetailLecon, LigneClasse, LigneLigue, ListeLecons } from "@/lib/types";
import { useMarche } from "./Contexte";

function Lecon({ id, retour }: { id: string; retour: () => void }) {
  const { donnees: d, erreur } = useLecture<DetailLecon>(`/api/v1/formation/lecons/${id}`, 3_600_000);
  const [choix, setChoix] = useState<Record<number, number>>({});
  const [corr, setCorr] = useState<CorrectionLecon | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function envoyer(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      const reponses = (d?.questions ?? []).map((q) => (choix[q.index] === undefined ? null : choix[q.index]));
      setCorr(await api<CorrectionLecon>(`/api/v1/formation/lecons/${id}/repondre`, { methode: "POST", corps: { reponses } }));
    } catch (exc) { setErr(exc instanceof ErreurApi ? exc.message : "Envoi impossible."); }
  }
  if (erreur) return <p className="erreur" role="alert">{erreur}</p>;
  if (!d) return <p className="vide">Chargement…</p>;
  return (
    <>
      <button className="lien" onClick={retour}>← Toutes les leçons</button>
      <article className="panneau">
        <header className="panneau-tete"><h2>{d.titre}</h2><span className="discret">{d.niveau} · {d.minutes} min</span></header>
        {d.sections.map((s) => <section key={s.titre}><h3 className="titre-section">{s.titre}</h3><p>{s.texte}</p></section>)}
      </article>
      <section className="panneau" aria-labelledby="titre-exo">
        <header className="panneau-tete"><h2 id="titre-exo">À faire dans le simulateur</h2></header>
        <ul className="strat-prudence">{d.exercices.map((x) => <li key={x.texte}>{x.texte} <Link href={x.lien}>{x.libelle}</Link></li>)}</ul>
      </section>
      <form className="panneau" onSubmit={envoyer} aria-labelledby="titre-quiz">
        <header className="panneau-tete"><h2 id="titre-quiz">Quiz ({d.questions.length} questions)</h2><span className="discret">Réussite à partir de {pct(d.seuil_reussite, 0)}</span></header>
        {d.questions.map((q) => {
          const c = corr?.corrections[q.index];
          return (
            <fieldset key={q.index} className="quiz-question" disabled={!!corr}>
              <legend>{q.index + 1}. {q.enonce}</legend>
              {q.choix.map((txt, i) => (
                <label key={i} className={c ? (i === c.bonne_reponse ? "quiz-juste" : i === c.repondu ? "quiz-faux" : undefined) : undefined}>
                  <input type="radio" name={`q${q.index}`} checked={choix[q.index] === i} onChange={() => setChoix({ ...choix, [q.index]: i })} /> {txt}
                  {c && i === c.bonne_reponse && <strong> ✓ bonne réponse</strong>}{c && i === c.repondu && i !== c.bonne_reponse && <strong> ✕ votre réponse</strong>}
                </label>
              ))}
              {c && <p className="aide">{c.explication}</p>}
            </fieldset>
          );
        })}
        {err && <p className="erreur" role="alert">{err}</p>}
        {corr ? (
          <>
            <p className={`statut ${corr.reussie ? "gain" : "alerte-texte"}`} role="status">{corr.reussie ? "✓ Leçon réussie" : "! Pas encore"} : {corr.bonnes} bonne(s) réponse(s) sur {corr.total}.</p>
            <button type="button" className="btn" onClick={() => { setCorr(null); setChoix({}); }}>Réessayer</button>
          </>
        ) : <button className="btn btn-principal strat-lancer" type="submit">Corriger</button>}
      </form>
    </>
  );
}

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

export default function PageFormation() {
  const { utilisateur } = useMarche();
  const [vue, setVue] = useState<"lecons" | "ligue" | "classe">("lecons");
  const [ouverte, setOuverte] = useState<string | null>(null);
  const { donnees, relire } = useLecture<ListeLecons>("/api/v1/formation/lecons", 15_000);
  const gestion = utilisateur.role === "formateur" || utilisateur.role === "admin";

  async function activer(id: string, actif: boolean) {
    await api(`/api/v1/formation/lecons/${id}/activation`, { methode: "PATCH", corps: { actif } });
    await relire();
  }
  return (
    <main className="page">
      <header className="page-tete">
        <h1>Formation</h1>
        <p className="aide">Des leçons courtes, des quiz corrigés par le serveur et des exercices à faire dans le simulateur.
          {donnees && ` Vous avez réussi ${donnees.progression.lecons_reussies} leçon(s) sur ${donnees.progression.lecons_actives}.`}</p>
      </header>
      <div className="onglets" role="tablist" aria-label="Formation">
        <button role="tab" aria-selected={vue === "lecons"} className="onglet" onClick={() => { setVue("lecons"); setOuverte(null); }}>Leçons</button>
        <button role="tab" aria-selected={vue === "ligue"} className="onglet" onClick={() => setVue("ligue")}>Ligue</button>
        {gestion && <button role="tab" aria-selected={vue === "classe"} className="onglet" onClick={() => setVue("classe")}>Ma classe</button>}
      </div>
      {vue === "ligue" && <Ligue />}
      {vue === "classe" && gestion && <Classe />}
      {vue === "lecons" && (ouverte ? <Lecon id={ouverte} retour={() => { setOuverte(null); void relire(); }} /> : (
        <div className="grille-3">
          {(donnees?.lecons ?? []).map((l) => (
            <article key={l.id} className={`panneau lecon-carte${l.active ? "" : " lecon-inactive"}`}>
              <header className="panneau-tete"><h2>{l.titre}</h2></header>
              <p className="aide">{l.niveau} · {l.minutes} min · {l.nb_questions} questions</p>
              <p>{l.resume}</p>
              <p className={`statut ${l.reussie ? "gain" : "discret"}`}>{l.reussie ? `✓ Réussie (${pct(l.meilleur_score ?? 0, 0)})` : l.tentatives ? `Essayée ${l.tentatives} fois, meilleur score ${pct(l.meilleur_score ?? 0, 0)}` : "Pas encore essayée"}</p>
              <div className="direct-actions">
                <button className="btn btn-principal" style={{ width: "auto", marginTop: 0 }} onClick={() => setOuverte(l.id)} disabled={!l.active && !gestion}>{l.reussie ? "Revoir" : "Commencer"}</button>
                {gestion && <label className="discret"><input type="checkbox" checked={l.active} onChange={(e) => void activer(l.id, e.target.checked)} /> Visible</label>}
              </div>
            </article>
          ))}
        </div>
      ))}
    </main>
  );
}
