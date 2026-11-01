"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { dateHeure } from "@/lib/format";
import type { LigneAudit, Role, Utilisateur } from "@/lib/types";
import AdminActualites from "./AdminActualites";
import AdminCrises from "./AdminCrises";
import { AdminDonnees, AdminPerformances, AdminStatistiques } from "./AdminStats";

const ONGLETS = [
  { cle: "utilisateurs", libelle: "Utilisateurs" },
  { cle: "statistiques", libelle: "Statistiques" },
  { cle: "performances", libelle: "Performances" },
  { cle: "crises", libelle: "Crises" },
  { cle: "actualites", libelle: "Actualités" },
  { cle: "donnees", libelle: "Données et IA" },
  { cle: "audit", libelle: "Journal d'audit" },
] as const;
type Onglet = (typeof ONGLETS)[number]["cle"];

const ROLES: Role[] = ["apprenant", "trader", "formateur", "admin"];

export default function Admin() {
  const [utilisateurs, setUtilisateurs] = useState<Utilisateur[]>([]);
  const [audit, setAudit] = useState<LigneAudit[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);
  const [onglet, setOnglet] = useState<Onglet>("utilisateurs");

  const charger = useCallback(async () => {
    try {
      const [u, a] = await Promise.all([
        api<Utilisateur[]>("/api/v1/admin/utilisateurs"),
        api<LigneAudit[]>("/api/v1/admin/audit?limite=100"),
      ]);
      setUtilisateurs(u);
      setAudit(a);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : "Chargement impossible.");
    }
  }, []);

  useEffect(() => { void charger(); }, [charger]);

  async function modifier(id: number, corps: { role?: Role; actif?: boolean }) {
    setErreur(null);
    try {
      await api(`/api/v1/admin/utilisateurs/${id}`, { methode: "PATCH", corps });
      await charger();
    } catch (e) {
      setErreur(e instanceof ErreurApi ? e.message : "Modification impossible.");
    }
  }

  return (
    <main className="page admin">
      <h1>Administration</h1>
      <div className="onglets" role="tablist" aria-label="Sections de l'administration">
        {ONGLETS.map((o) => <button key={o.cle} role="tab" aria-selected={onglet === o.cle} className="onglet" onClick={() => setOnglet(o.cle)}>{o.libelle}</button>)}
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {onglet === "statistiques" && <AdminStatistiques />}
      {onglet === "performances" && <AdminPerformances />}
      {onglet === "donnees" && <AdminDonnees />}
      {onglet === "crises" && <AdminCrises />}
      {onglet === "actualites" && <AdminActualites />}
      {onglet === "utilisateurs" && <section>
        <h2>Utilisateurs</h2>
        <table className="tableau">
          <thead><tr><th>Nom</th><th>E-mail</th><th>Rôle</th><th>Profil de risque</th><th>Dernière connexion</th><th>Compte actif</th></tr></thead>
          <tbody>
            {utilisateurs.map((u) => (
              <tr key={u.id}>
                <td>{u.nom}</td><td>{u.email}</td>
                <td>
                  <label className="sr-only" htmlFor={`role-${u.id}`}>Rôle de {u.nom}</label>
                  <select id={`role-${u.id}`} value={u.role} onChange={(e) => modifier(u.id, { role: e.target.value as Role })}>
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td>{u.profil_risque ? `${u.profil_risque.categorie} (${u.profil_risque.perte_max_toleree_pct} %)` : "non renseigné"}</td>
                <td>{u.derniere_connexion ? dateHeure(u.derniere_connexion) : "–"}</td>
                <td><input type="checkbox" checked={u.actif} aria-label={`Compte actif : ${u.nom}`} onChange={(e) => modifier(u.id, { actif: e.target.checked })} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>}
      {onglet === "audit" && <section>
        <h2>Journal d&apos;audit</h2>
        <table className="tableau">
          <thead><tr><th>Date (UTC)</th><th>Action</th><th>Utilisateur</th><th>Détails</th><th>Adresse IP</th></tr></thead>
          <tbody>
            {audit.map((l) => (
              <tr key={l.id}>
                <td>{dateHeure(l.horodatage)}</td><td>{l.action}</td><td>{l.utilisateur_id ?? "–"}</td>
                <td>{l.details ? JSON.stringify(l.details) : ""}</td><td>{l.ip ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>}
    </main>
  );
}
