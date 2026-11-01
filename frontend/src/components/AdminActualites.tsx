"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import type { Actualite } from "@/lib/types";

const LIBELLE_SOURCE: Record<string, string> = { historique: "Repère historique", fictif: "Fictive", scenario: "Fictive (crise)", import: "Importée" };

export default function AdminActualites() {
  const [liste, setListe] = useState<Actualite[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [date, setDate] = useState("");
  const [titre, setTitre] = useState("");
  const [texte, setTexte] = useState("");
  const [symboles, setSymboles] = useState("");

  const charger = useCallback(async () => {
    try { setListe(await api<Actualite[]>("/api/v1/admin/actualites")); }
    catch (e) { setErreur(e instanceof Error ? e.message : "Chargement impossible."); }
  }, []);
  useEffect(() => { void charger(); }, [charger]);

  async function creer(e: React.FormEvent) {
    e.preventDefault(); setErreur(null); setInfo(null);
    try {
      await api("/api/v1/admin/actualites", { methode: "POST", corps: { date, titre, texte, symboles: symboles.split(/[\s,;]+/).filter(Boolean).map((s) => s.toUpperCase()) } });
      setTitre(""); setTexte(""); setSymboles("");
      await charger();
    } catch (exc) { setErreur(exc instanceof ErreurApi ? exc.message : "Création impossible."); }
  }
  async function reperes() {
    setErreur(null); setInfo(null);
    try { const r = await api<{ ajoutees: number }>("/api/v1/admin/actualites/reperes", { methode: "POST" }); setInfo(`${r.ajoutees} repère(s) historique(s) ajouté(s).`); await charger(); }
    catch (exc) { setErreur(exc instanceof Error ? exc.message : "Chargement impossible."); }
  }
  async function basculer(a: Actualite) {
    try { await api(`/api/v1/admin/actualites/${a.id}`, { methode: "PATCH", corps: { actif: !a.actif } }); await charger(); }
    catch (exc) { setErreur(exc instanceof Error ? exc.message : "Modification impossible."); }
  }
  async function supprimer(a: Actualite) {
    if (!window.confirm(`Supprimer l'actualité « ${a.titre} » ?`)) return;
    try { await api(`/api/v1/admin/actualites/${a.id}`, { methode: "DELETE" }); await charger(); }
    catch (exc) { setErreur(exc instanceof Error ? exc.message : "Suppression impossible."); }
  }

  return (
    <div className="admin-crises">
      <p className="aide">
        Une actualité est visible par les utilisateurs à partir de 08:00 le jour de parution (jamais avant : le jour de parution, la séance n&apos;est pas terminée).
        Les repères historiques ont été rédigés de mémoire par l&apos;assistant : relisez-les avant une présentation. Les actualités fictives sont toujours signalées comme telles.
      </p>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {info && <p className="info" role="status">{info}</p>}
      <section className="panneau" aria-labelledby="titre-nouvelle-actu">
        <header className="panneau-tete"><h2 id="titre-nouvelle-actu">Ajouter une actualité fictive</h2><button type="button" className="lien" onClick={reperes}>Charger les repères historiques manquants</button></header>
        <form onSubmit={creer}>
          <div className="strat-champs">
            <div className="champ"><label htmlFor="a-date">Date de parution</label><input id="a-date" type="date" required value={date} onChange={(e) => setDate(e.target.value)} /></div>
            <div className="champ"><label htmlFor="a-titre">Titre</label><input id="a-titre" required minLength={3} maxLength={200} value={titre} onChange={(e) => setTitre(e.target.value)} /></div>
            <div className="champ"><label htmlFor="a-sym">Actifs concernés (vide = marché en général)</label><input id="a-sym" placeholder="AAPL, BTC-USD" value={symboles} onChange={(e) => setSymboles(e.target.value)} /></div>
          </div>
          <div className="champ"><label htmlFor="a-texte">Texte (facultatif)</label><input id="a-texte" maxLength={1200} value={texte} onChange={(e) => setTexte(e.target.value)} /></div>
          <button className="btn btn-principal strat-lancer" type="submit">Ajouter</button>
        </form>
      </section>
      <section className="panneau panneau-tableau" aria-labelledby="titre-actus">
        <header className="panneau-tete strat-tete-tableau"><h2 id="titre-actus">Actualités ({liste.length})</h2></header>
        <div className="tableau-defile">
          <table className="tableau tableau-gauche">
            <thead><tr><th>Date</th><th>Titre</th><th>Actifs</th><th>Origine</th><th>Sentiment</th><th>Visible</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {liste.map((a) => (
                <tr key={a.id}>
                  <td>{a.date}</td><td className="cellule-large">{a.titre}</td><td>{a.symboles.length ? a.symboles.join(", ") : "marché"}</td>
                  <td>{LIBELLE_SOURCE[a.type_source] ?? a.type_source}</td>
                  <td>{a.sentiment.etiquette === "positif" ? "▲ positif" : a.sentiment.etiquette === "negatif" ? "▼ négatif" : "neutre"}</td>
                  <td><input type="checkbox" checked={a.actif} aria-label={`Actualité visible : ${a.titre}`} onChange={() => basculer(a)} /></td>
                  <td><button className="lien" onClick={() => supprimer(a)}>Supprimer</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
