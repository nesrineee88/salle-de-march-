"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { montant, nombre, pct, pctSigne } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import type { PerformanceAdmin, StatsAdmin } from "@/lib/types";

const Kpi = ({ libelle, valeur, detail }: { libelle: string; valeur: string; detail?: string }) => (
  <div className="indicateur"><span className="indicateur-libelle">{libelle}</span><span className="indicateur-valeur">{valeur}</span>{detail && <span className="indicateur-detail">{detail}</span>}</div>
);

export function AdminStatistiques() {
  const { donnees: s, erreur } = useLecture<StatsAdmin>("/api/v1/admin/statistiques", 15_000);
  if (erreur) return <p className="erreur" role="alert">{erreur}</p>;
  if (!s) return <p className="vide">Chargement…</p>;
  return (
    <div className="admin-crises">
      <div className="kpis">
        <Kpi libelle="Utilisateurs" valeur={String(s.utilisateurs.total)} detail={`${s.utilisateurs.actifs} actifs · ${s.utilisateurs.nouveaux_7_jours} nouveaux cette semaine · ${s.utilisateurs.connectes_7_jours} connectés`} />
        <Kpi libelle="Exécutions" valeur={String(s.trading.executions)} detail={`${montant(s.trading.frais_totaux)} de frais · ${s.trading.regles_actives} règles actives`} />
        <Kpi libelle="Portefeuilles actifs" valeur={String(s.trading.comptes_avec_historique)} detail="avec au moins un jour simulé" />
        <Kpi libelle="Crises et actualités" valeur={`${s.crises.scenarios_actifs} / ${s.crises.scenarios}`} detail={`${s.crises.actualites} actualités dont ${s.crises.actualites_fictives} fictives`} />
      </div>
      <div className="grille-2">
        <section className="panneau"><header className="panneau-tete"><h2>Rôles</h2></header>
          <table className="tableau tableau-gauche"><tbody>{Object.entries(s.utilisateurs.par_role).map(([r, n]) => <tr key={r}><td>{r}</td><td>{n}</td></tr>)}</tbody></table>
          <h3 className="sous-titre">Ordres par statut</h3>
          <table className="tableau tableau-gauche"><tbody>{Object.entries(s.trading.ordres_par_statut).map(([r, n]) => <tr key={r}><td>{r}</td><td>{n}</td></tr>)}</tbody></table>
        </section>
        <section className="panneau"><header className="panneau-tete"><h2>Actifs les plus échangés</h2></header>
          {s.trading.actifs_les_plus_echanges.length ? <table className="tableau tableau-gauche"><tbody>{s.trading.actifs_les_plus_echanges.map((a) => <tr key={a.symbole}><td>{a.symbole}</td><td>{a.executions} exécutions</td></tr>)}</tbody></table> : <p className="vide">Aucune exécution pour l&apos;instant.</p>}
        </section>
      </div>
      <section className="panneau panneau-tableau"><header className="panneau-tete strat-tete-tableau"><h2>Formation</h2></header>
        <div className="tableau-defile"><table className="tableau tableau-gauche"><thead><tr><th>Leçon</th><th>Réussites</th><th>Score moyen</th></tr></thead>
          <tbody>{s.formation.map((f) => <tr key={f.id}><td>{f.titre}</td><td>{f.reussites}</td><td>{f.score_moyen === null ? "–" : pct(f.score_moyen, 0)}</td></tr>)}</tbody></table></div>
      </section>
    </div>
  );
}

export function AdminDonnees() {
  const { donnees: s, relire } = useLecture<StatsAdmin>("/api/v1/admin/statistiques", 15_000);
  const [message, setMessage] = useState<string | null>(null);
  const [enCours, setEnCours] = useState<string | null>(null);
  async function entrainer(route: string, cle: string) {
    setEnCours(cle); setMessage(null);
    try { await api(route, { methode: "POST" }); setMessage("Modèle ré-entraîné."); await relire(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Entraînement impossible."); } finally { setEnCours(null); }
  }
  if (!s) return <p className="vide">Chargement…</p>;
  const d = s.donnees;
  return (
    <div className="admin-crises">
      <section className="panneau"><header className="panneau-tete"><h2>Données de marché</h2></header>
        <p>{d.actifs_charges} actifs chargés sur {d.actifs_total}, du {d.debut} au {d.fin}.</p>
        {d.synthetiques && <p className="avertissement">Données de démonstration générées au hasard : lancez <code>python -m pipeline tout</code> pour les vraies.</p>}
        <p>Mode Direct : {d.direct_actif ? (d.direct_demo ? "activé, flux de DÉMONSTRATION (prix inventés)" : "activé (bêta)") : "désactivé"}{d.flux_direct?.derniere_maj ? ` · dernière mise à jour ${d.flux_direct.derniere_maj}` : ""}{d.flux_direct?.erreur ? ` · erreur : ${d.flux_direct.erreur}` : ""}</p>
      </section>
      <section className="panneau panneau-tableau"><header className="panneau-tete strat-tete-tableau"><h2>Modèles d&apos;IA enregistrés</h2></header>
        {message && <p className="info" role="status" style={{ padding: "0 1.1rem" }}>{message}</p>}
        <div className="tableau-defile"><table className="tableau tableau-gauche"><thead><tr><th>Modèle</th><th>Jeu de données</th><th>Mesure</th><th><span className="sr-only">Action</span></th></tr></thead>
          <tbody>{s.modeles.map((m) => (
            <tr key={m.cle}><td>{m.titre}</td><td>{m.present ? (m.source === "synthetique" ? "SYNTHÉTIQUE (inventé)" : "Réel (Kaggle)") : "Pas encore entraîné"}</td>
              <td>{m.present && m.valeur != null ? `${m.mesure} : ${nombre(m.valeur, 3)}` : "–"}</td>
              <td><button className="btn" onClick={() => void entrainer(m.route_entrainement, m.cle)} disabled={enCours !== null}>{enCours === m.cle ? "Entraînement…" : "Ré-entraîner"}</button></td></tr>
          ))}</tbody></table></div>
        <p className="aide" style={{ padding: "0.75rem 1.1rem" }}>Pour passer du jeu synthétique au jeu réel, placez les fichiers Kaggle dans <code>data/externes</code> (cs-training.csv, freMTPL2freq.csv, freMTPL2sev.csv) puis ré-entraînez.</p>
      </section>
      <section className="panneau"><header className="panneau-tete"><h2>Paramètres de simulation</h2></header>
        <dl className="mini-indicateurs">
          <div><dt>Capital initial</dt><dd>{montant(s.parametres.capital_initial)}</dd></div>
          <div><dt>Vitesse par défaut</dt><dd>×{s.parametres.facteur_vitesse_par_defaut}</dd></div>
          <div><dt>Frais (points de base)</dt><dd>{Object.entries(s.parametres.frais_points_de_base).map(([k, v]) => `${k} ${v}`).join(" · ")}</dd></div>
          <div><dt>Écart acheteur-vendeur (pb)</dt><dd>{Object.entries(s.parametres.ecart_points_de_base).map(([k, v]) => `${k} ${v}`).join(" · ")}</dd></div>
          <div><dt>Session de connexion</dt><dd>{s.parametres.duree_jeton_acces_minutes} min / {s.parametres.duree_session_jours} j</dd></div>
          <div><dt>Verrouillage après</dt><dd>{s.parametres.echecs_avant_verrouillage} échecs</dd></div>
        </dl>
        <p className="aide">{s.parametres.note}</p>
      </section>
    </div>
  );
}

export function AdminPerformances() {
  const { donnees } = useLecture<PerformanceAdmin[]>("/api/v1/admin/performances", 15_000);
  return (
    <section className="panneau panneau-tableau"><header className="panneau-tete strat-tete-tableau"><h2>Performance des utilisateurs</h2></header>
      <div className="tableau-defile"><table className="tableau tableau-gauche">
        <caption className="sr-only">Rendement et pire baisse de chaque utilisateur</caption>
        <thead><tr><th>Nom</th><th>Rôle</th><th>Profil</th><th>Valeur</th><th>Rendement</th><th>Pire baisse</th><th>Score</th><th>Date simulée</th></tr></thead>
        <tbody>{(donnees ?? []).map((u) => (
          <tr key={u.id}><td>{u.nom}{!u.actif && <span className="discret"> (désactivé)</span>}</td><td>{u.role}</td><td>{u.profil_risque ?? "–"}</td>
            <td>{u.portefeuille ? montant(u.portefeuille.valeur) : "–"}</td><td>{u.portefeuille ? pctSigne(u.portefeuille.rendement, 1) : "–"}</td>
            <td>{u.portefeuille ? pct(u.portefeuille.drawdown, 1) : "–"}</td><td>{u.portefeuille ? nombre(u.portefeuille.score, 2) : "–"}</td><td>{u.portefeuille?.date_simulee ?? "–"}</td></tr>
        ))}</tbody></table></div>
    </section>
  );
}
