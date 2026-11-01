"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ErreurApi, jetonRafraichissement } from "@/lib/api";
import { dateHeure, libelleAppareil } from "@/lib/format";
import type { SessionAppareil } from "@/lib/types";
import { useMarche } from "./Contexte";
import ProfilRisque from "./ProfilRisque";

function Securite() {
  const [ancien, setAncien] = useState("");
  const [nouveau, setNouveau] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; texte: string } | null>(null);
  const [envoi, setEnvoi] = useState(false);

  async function changer(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setEnvoi(true);
    try {
      await api("/api/v1/moi/mot-de-passe", { methode: "POST", corps: { ancien, nouveau, refresh_token: jetonRafraichissement() } });
      setAncien(""); setNouveau("");
      setMessage({ ok: true, texte: "Mot de passe modifié. Vos autres appareils ont été déconnectés ; celui-ci reste connecté." });
    } catch (err) {
      setMessage({ ok: false, texte: err instanceof ErreurApi ? err.message : "Le mot de passe n'a pas pu être modifié." });
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <form onSubmit={changer} className="formulaire-compte">
      <div className="champ">
        <label htmlFor="ancien-mdp">Mot de passe actuel</label>
        <input id="ancien-mdp" type="password" autoComplete="current-password" value={ancien} onChange={(e) => setAncien(e.target.value)} required />
      </div>
      <div className="champ">
        <label htmlFor="nouveau-mdp">Nouveau mot de passe</label>
        <input id="nouveau-mdp" type="password" autoComplete="new-password" minLength={10} value={nouveau} onChange={(e) => setNouveau(e.target.value)} required aria-describedby="aide-mdp" />
        <p id="aide-mdp" className="aide">10 caractères au minimum, avec au moins une lettre et un chiffre. Une phrase facile à retenir fonctionne très bien.</p>
      </div>
      {message && <p className={message.ok ? "message-ok" : "erreur"} role={message.ok ? "status" : "alert"}>{message.texte}</p>}
      <button className="btn btn-principal btn-auto" type="submit" disabled={envoi || !ancien || nouveau.length < 10}>Changer le mot de passe</button>
    </form>
  );
}

function Appareils() {
  const { deconnecter } = useMarche();
  const [sessions, setSessions] = useState<SessionAppareil[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async () => {
    try {
      setSessions(await api<SessionAppareil[]>("/api/v1/moi/sessions", { methode: "POST", corps: { refresh_token: jetonRafraichissement() } }));
    } catch (e) {
      setErreur(e instanceof Error ? e.message : "Lecture impossible.");
    }
  }, []);
  useEffect(() => { void charger(); }, [charger]);

  async function terminer(famille: string) {
    try { await api(`/api/v1/moi/sessions/${encodeURIComponent(famille)}`, { methode: "DELETE" }); await charger(); }
    catch (e) { setErreur(e instanceof Error ? e.message : "Action impossible."); }
  }
  async function toutFermer() {
    if (!window.confirm("Déconnecter tous vos appareils, y compris celui-ci ?")) return;
    try { await api("/api/v1/moi/deconnexion-partout", { methode: "POST" }); } catch { /* la session est de toute façon révoquée */ }
    deconnecter();
  }

  return (
    <div>
      <p className="aide">Chaque navigateur connecté à votre compte apparaît ici. Si vous ne reconnaissez pas un appareil, déconnectez-le puis changez votre mot de passe.</p>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {sessions === null ? <p className="vide">Chargement…</p> : (
        <ul className="appareils">
          {sessions.map((s) => (
            <li key={s.famille}>
              <div>
                <p><strong>{libelleAppareil(s.agent)}</strong> {s.courante && <span className="pastille">Cet appareil</span>}</p>
                <p className="discret">Connecté depuis le {dateHeure(s.debut)} · dernière activité {dateHeure(s.derniere_activite)}{s.ip ? ` · ${s.ip}` : ""}</p>
              </div>
              {!s.courante && <button className="btn" onClick={() => void terminer(s.famille)}>Déconnecter</button>}
            </li>
          ))}
        </ul>
      )}
      <button className="btn" onClick={() => void toutFermer()} style={{ marginTop: "0.75rem" }}>Me déconnecter partout</button>
    </div>
  );
}

function Donnees() {
  const { reinitialiser } = useMarche();
  const [erreur, setErreur] = useState<string | null>(null);

  async function exporter() {
    setErreur(null);
    try {
      const d = await api<unknown>("/api/v1/moi/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url; a.download = "mes-donnees-salle-de-marche.json"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setErreur(e instanceof Error ? e.message : "Export impossible."); }
  }
  async function repartir() {
    if (window.confirm("Repartir de zéro ? Vos ordres, positions et l'historique de valeur seront effacés ; le capital et la date de départ sont réinitialisés. Votre compte et votre profil de risque sont conservés.")) await reinitialiser();
  }

  return (
    <div className="actions-compte">
      <div>
        <h3>Exporter mes données</h3>
        <p className="aide">Un fichier avec votre profil, vos ordres, vos positions et l&apos;historique de valeur de votre portefeuille.</p>
        <button className="btn" onClick={() => void exporter()}>Télécharger (JSON)</button>
      </div>
      <div>
        <h3>Repartir de zéro</h3>
        <p className="aide">Efface votre simulation pour recommencer avec le capital de départ. Cette action est définitive.</p>
        <button className="btn btn-danger" onClick={() => void repartir()}>Réinitialiser ma simulation</button>
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
    </div>
  );
}

export default function PageCompte() {
  const { utilisateur, majUtilisateur } = useMarche();
  return (
    <main className="page page-etroite">
      <header className="page-tete">
        <div>
          <h1>Mon compte</h1>
          <p className="aide">{utilisateur.nom} · {utilisateur.email} · rôle : {utilisateur.role}</p>
        </div>
      </header>
      <section className="panneau" id="profil" aria-labelledby="t-profil">
        <header className="panneau-tete"><h2 id="t-profil">Profil de risque</h2></header>
        <ProfilRisque utilisateur={utilisateur} onEnregistre={majUtilisateur} />
      </section>
      <section className="panneau" aria-labelledby="t-appareils">
        <header className="panneau-tete"><h2 id="t-appareils">Appareils connectés</h2></header>
        <Appareils />
      </section>
      <section className="panneau" aria-labelledby="t-mdp">
        <header className="panneau-tete"><h2 id="t-mdp">Mot de passe</h2></header>
        <Securite />
      </section>
      <section className="panneau" aria-labelledby="t-donnees">
        <header className="panneau-tete"><h2 id="t-donnees">Mes données</h2></header>
        <Donnees />
      </section>
    </main>
  );
}
