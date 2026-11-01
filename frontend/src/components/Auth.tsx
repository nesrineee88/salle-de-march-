"use client";

import { useState } from "react";
import { connexion, ErreurApi, inscription } from "@/lib/api";
import { dateCourte } from "@/lib/format";
import { REPERES } from "@/lib/reperes";
import type { Utilisateur } from "@/lib/types";
import BoutonTheme from "./BoutonTheme";

export default function Auth({ onConnecte }: { onConnecte: (u: Utilisateur) => void }) {
  const [mode, setMode] = useState<"connexion" | "inscription">("connexion");
  const [email, setEmail] = useState("");
  const [nom, setNom] = useState("");
  const [mdp, setMdp] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  async function soumettre(e: React.FormEvent) {
    e.preventDefault();
    setErreur(null);
    setEnvoi(true);
    try {
      if (mode === "inscription") await inscription(email, nom, mdp);
      onConnecte(await connexion(email, mdp));
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : "Une erreur inattendue est survenue.");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <main className="auth">
      <div className="auth-theme"><BoutonTheme /></div>
      <section className="auth-recit">
        <p className="marque">Salle de marché</p>
        <h1>Rejouez six ans de marchés.</h1>
        <p className="auth-intro">
          Actions, cryptomonnaies et matières premières, du 1er janvier 2018 au 30 octobre 2026. Vous choisissez la
          date, la vitesse et vos ordres. L&apos;argent est virtuel, les erreurs ne coûtent rien.
        </p>
        <ol className="auth-reperes" aria-label="Moments à rejouer">
          {REPERES.map((r) => (
            <li key={r.date}>
              <time dateTime={r.date}>{dateCourte(`${r.date}T00:00:00`)}</time>
              <span>{r.titre}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="auth-formulaire">
        <div className="onglets" role="tablist" aria-label="Accès au compte">
          <button role="tab" aria-selected={mode === "connexion"} className="onglet" onClick={() => setMode("connexion")}>
            Se connecter
          </button>
          <button role="tab" aria-selected={mode === "inscription"} className="onglet" onClick={() => setMode("inscription")}>
            Créer un compte
          </button>
        </div>

        <form onSubmit={soumettre} noValidate>
          {mode === "inscription" && (
            <div className="champ">
              <label htmlFor="nom">Nom affiché</label>
              <input id="nom" value={nom} onChange={(e) => setNom(e.target.value)} autoComplete="nickname" required />
            </div>
          )}
          <div className="champ">
            <label htmlFor="email">Adresse e-mail</label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
          </div>
          <div className="champ">
            <label htmlFor="mdp">Mot de passe</label>
            <input
              id="mdp"
              type="password"
              value={mdp}
              onChange={(e) => setMdp(e.target.value)}
              autoComplete={mode === "connexion" ? "current-password" : "new-password"}
              aria-describedby={mode === "inscription" ? "aide-mdp" : undefined}
              required
            />
            {mode === "inscription" && (
              <p id="aide-mdp" className="aide">10 caractères minimum, avec au moins une lettre et un chiffre.</p>
            )}
          </div>
          {erreur && <p className="erreur" role="alert">{erreur}</p>}
          <button className="btn btn-principal" type="submit" disabled={envoi}>
            {envoi ? "Un instant…" : mode === "connexion" ? "Se connecter" : "Créer mon compte"}
          </button>
        </form>
      </section>
    </main>
  );
}
