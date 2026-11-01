"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { pctSigne } from "@/lib/format";
import type { ListeScenarios, ModeleScenario, PorteeScenario, Scenario } from "@/lib/types";

const PORTEES: { cle: PorteeScenario; libelle: string }[] = [
  { cle: "tous", libelle: "Tous les actifs négociables" },
  { cle: "classe", libelle: "Une ou plusieurs classes d'actifs" },
  { cle: "secteur", libelle: "Un ou plusieurs secteurs" },
  { cle: "actifs", libelle: "Des actifs précis" },
];
const LIBELLE_CLASSE: Record<string, string> = { action: "Actions", crypto: "Cryptomonnaies", matiere: "Matières premières" };

function libellePortee(s: Scenario): string {
  if (s.portee_type === "tous") return "Tous les actifs";
  const valeurs = s.portee_type === "classe" ? s.portee_valeurs.map((v) => LIBELLE_CLASSE[v] ?? v) : s.portee_valeurs;
  return `${s.portee_type === "classe" ? "Classes" : s.portee_type === "secteur" ? "Secteurs" : "Actifs"} : ${valeurs.join(", ")}`;
}

export default function AdminCrises() {
  const [liste, setListe] = useState<ListeScenarios | null>(null);
  const [modeles, setModeles] = useState<ModeleScenario[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  const [nom, setNom] = useState("");
  const [description, setDescription] = useState("");
  const [debut, setDebut] = useState("");
  const [portee, setPortee] = useState<PorteeScenario>("classe");
  const [valeurs, setValeurs] = useState<string[]>([]);
  const [choc, setChoc] = useState("-30");
  const [recup, setRecup] = useState("0");
  const [duree, setDuree] = useState("0");
  const [annonce, setAnnonce] = useState("");

  const charger = useCallback(async () => {
    try {
      const [l, m] = await Promise.all([api<ListeScenarios>("/api/v1/admin/scenarios"), api<ModeleScenario[]>("/api/v1/admin/scenarios/modeles")]);
      setListe(l); setModeles(m);
      setDebut((d) => d || l.debut);
    } catch (e) { setErreur(e instanceof Error ? e.message : "Chargement impossible."); }
  }, []);
  useEffect(() => { void charger(); }, [charger]);

  function appliquerModele(m: ModeleScenario) {
    setNom(m.nom); setDescription(m.description); setPortee(m.portee_type); setValeurs(m.portee_valeurs);
    setChoc(String(m.choc_pct)); setRecup(String(m.recuperation_pct)); setDuree(String(m.duree_recuperation_jours)); setAnnonce(m.annonce);
    setInfo(null); setErreur(null);
  }

  const nombre = (t: string) => Number(t.replace(",", "."));

  async function creer(e: React.FormEvent) {
    e.preventDefault();
    setErreur(null); setInfo(null); setEnCours(true);
    try {
      const r = await api<{ avertissement: string }>("/api/v1/admin/scenarios", {
        methode: "POST",
        corps: {
          nom, description, date_debut: debut, portee_type: portee, portee_valeurs: portee === "tous" ? [] : valeurs,
          choc_pct: nombre(choc), recuperation_pct: nombre(recup), duree_recuperation_jours: Math.round(nombre(duree)), annonce: annonce.trim() || null,
        },
      });
      setInfo(`Crise créée et appliquée aux prix. ${r.avertissement}`);
      setNom(""); setDescription(""); setAnnonce("");
      await charger();
    } catch (exc) { setErreur(exc instanceof ErreurApi ? exc.message : "Création impossible."); }
    finally { setEnCours(false); }
  }

  async function basculer(s: Scenario) {
    setErreur(null);
    try { await api(`/api/v1/admin/scenarios/${s.id}`, { methode: "PATCH", corps: { actif: !s.actif } }); await charger(); }
    catch (exc) { setErreur(exc instanceof Error ? exc.message : "Modification impossible."); }
  }
  async function supprimer(s: Scenario) {
    if (!window.confirm(`Supprimer définitivement la crise « ${s.nom} » ? Les prix reviennent à leurs valeurs d'origine.`)) return;
    setErreur(null);
    try { await api(`/api/v1/admin/scenarios/${s.id}`, { methode: "DELETE" }); await charger(); }
    catch (exc) { setErreur(exc instanceof Error ? exc.message : "Suppression impossible."); }
  }

  function cocher(v: string, coche: boolean) {
    setValeurs((a) => (coche ? [...a, v] : a.filter((x) => x !== v)));
  }

  const choix: { valeur: string; libelle: string }[] =
    portee === "classe" ? (liste?.classes ?? []).map((c) => ({ valeur: c, libelle: LIBELLE_CLASSE[c] ?? c })) :
    portee === "secteur" ? (liste?.secteurs ?? []).map((s) => ({ valeur: s, libelle: s })) :
    portee === "actifs" ? (liste?.actifs ?? []).map((a) => ({ valeur: a.symbole, libelle: `${a.symbole} · ${a.nom}` })) : [];

  return (
    <div className="admin-crises">
      <p className="aide">
        Une crise modifie les prix de tous les utilisateurs à partir d&apos;une date de la période rejouée : un choc brutal à l&apos;ouverture, puis, si vous le
        souhaitez, un retour progressif. Les prix d&apos;origine ne sont jamais écrasés : désactiver ou supprimer la crise les restitue.
      </p>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {info && <p className="info" role="status">{info}</p>}

      <section className="panneau" aria-labelledby="titre-nouvelle-crise">
        <header className="panneau-tete"><h2 id="titre-nouvelle-crise">Injecter une crise</h2></header>
        <div className="crise-modeles" role="group" aria-label="Partir d'un modèle">
          <span className="discret">Partir d&apos;un modèle :</span>
          {modeles.map((m) => <button key={m.cle} type="button" className="puce" onClick={() => appliquerModele(m)} title={m.description}>{m.nom}</button>)}
        </div>
        <form onSubmit={creer}>
          <div className="strat-champs">
            <div className="champ"><label htmlFor="c-nom">Nom</label><input id="c-nom" value={nom} required minLength={2} maxLength={120} onChange={(e) => setNom(e.target.value)} /></div>
            <div className="champ"><label htmlFor="c-debut">Date du choc (période rejouée)</label>
              <input id="c-debut" type="date" required value={debut} min={liste?.debut} max={liste?.fin} onChange={(e) => setDebut(e.target.value)} /></div>
            <div className="champ"><label htmlFor="c-portee">Qui est touché ?</label>
              <select id="c-portee" value={portee} onChange={(e) => { setPortee(e.target.value as PorteeScenario); setValeurs([]); }}>
                {PORTEES.map((p) => <option key={p.cle} value={p.cle}>{p.libelle}</option>)}
              </select></div>
          </div>
          {choix.length > 0 && (
            <fieldset className="crise-choix">
              <legend className="sous-titre">À cocher</legend>
              {choix.map((c) => (
                <label key={c.valeur}><input type="checkbox" checked={valeurs.includes(c.valeur)} onChange={(e) => cocher(c.valeur, e.target.checked)} /> {c.libelle}</label>
              ))}
            </fieldset>
          )}
          <div className="strat-champs">
            <div className="champ"><label htmlFor="c-choc">Choc en % (−30 = chute de 30 %)</label><input id="c-choc" inputMode="decimal" required value={choc} onChange={(e) => setChoc(e.target.value)} /></div>
            <div className="champ"><label htmlFor="c-recup">Part du choc regagnée ensuite, en %</label><input id="c-recup" inputMode="decimal" value={recup} onChange={(e) => setRecup(e.target.value)} /></div>
            <div className="champ"><label htmlFor="c-duree">…sur combien de jours</label><input id="c-duree" inputMode="numeric" value={duree} onChange={(e) => setDuree(e.target.value)} /></div>
          </div>
          <div className="champ"><label htmlFor="c-desc">Description (facultatif)</label><input id="c-desc" value={description} maxLength={600} onChange={(e) => setDescription(e.target.value)} /></div>
          <div className="champ"><label htmlFor="c-annonce">Actualité fictive publiée le jour du choc (facultatif)</label><input id="c-annonce" value={annonce} maxLength={200} onChange={(e) => setAnnonce(e.target.value)} /></div>
          <button className="btn btn-principal strat-lancer" type="submit" disabled={enCours}>{enCours ? "Application…" : "Créer et appliquer la crise"}</button>
        </form>
      </section>

      <section className="panneau panneau-tableau" aria-labelledby="titre-crises-existantes">
        <header className="panneau-tete strat-tete-tableau"><h2 id="titre-crises-existantes">Crises existantes ({liste?.scenarios.length ?? 0})</h2></header>
        <div className="tableau-defile">
          {liste && liste.scenarios.length > 0 ? (
            <table className="tableau tableau-gauche">
              <thead><tr><th>Nom</th><th>Date</th><th>Périmètre</th><th>Choc</th><th>Récupération</th><th>Active</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {liste.scenarios.map((s) => (
                  <tr key={s.id}>
                    <td>{s.nom}</td><td>{s.date_debut}</td><td>{libellePortee(s)}{s.nb_actifs !== undefined ? ` (${s.nb_actifs} actifs)` : ""}</td>
                    <td className={s.choc_pct < 0 ? "perte" : "gain"}>{s.choc_pct < 0 ? "▼ " : "▲ "}{pctSigne(s.choc_pct / 100, 0)}</td>
                    <td>{s.recuperation_pct > 0 ? `${s.recuperation_pct} % en ${s.duree_recuperation_jours} j` : "aucune"}</td>
                    <td><input type="checkbox" checked={s.actif} aria-label={`Crise active : ${s.nom}`} onChange={() => basculer(s)} /></td>
                    <td><button className="lien" onClick={() => supprimer(s)}>Supprimer</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="vide">Aucune crise pour l&apos;instant : les prix sont ceux de l&apos;historique.</p>}
        </div>
      </section>
    </div>
  );
}
