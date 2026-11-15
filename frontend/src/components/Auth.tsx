"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart3, Eye, EyeOff, GraduationCap, ShieldCheck } from "lucide-react";
import { connexion, erreurOauth, ErreurApi, fournisseursOauth, inscription } from "@/lib/api";
import { dateCourte } from "@/lib/format";
import { REPERES } from "@/lib/reperes";
import type { Utilisateur } from "@/lib/types";
import BoutonTheme from "./BoutonTheme";

function Google() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z" />
      <path fill="#FBBC05" d="M10.5 28.7c-.5-1.5-.8-3-.8-4.7s.3-3.2.8-4.7l-7.9-6.1C.9 16.4 0 20.1 0 24s.9 7.6 2.6 10.8l7.9-6.1z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
    </svg>
  );
}
function GitHub() {
  return (
    <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.5 7.5 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

/** Force du mot de passe : on compte les règles du serveur (10 caractères, lettre, chiffre) puis la variété. */
function force(mdp: string): { niveau: 0 | 1 | 2 | 3 | 4; regles: { ok: boolean; texte: string }[] } {
  const regles = [
    { ok: mdp.length >= 10, texte: "10 caractères minimum" },
    { ok: /[a-zA-Z]/.test(mdp), texte: "Une lettre" },
    { ok: /\d/.test(mdp), texte: "Un chiffre" },
  ];
  const base = regles.filter((r) => r.ok).length;
  const bonus = (mdp.length >= 14 ? 1 : 0) + (/[^a-zA-Z0-9]/.test(mdp) && /[A-Z]/.test(mdp) ? 1 : 0);
  const niveau = (base < 3 ? Math.min(base, 1) : Math.min(2 + bonus, 4)) as 0 | 1 | 2 | 3 | 4;
  return { niveau: mdp ? niveau : 0, regles };
}
const NOMS_FORCE = ["", "Faible", "Correct", "Bon", "Très bon"];

const ATOUTS = [
  { icone: BarChart3, titre: "Six ans de marchés à rejouer", texte: "Actions, crypto et matières premières, du 1er janvier 2018 au 30 octobre 2026. Vous choisissez la date et la vitesse." },
  { icone: GraduationCap, titre: "Apprenez sans risque", texte: "Capital virtuel, ordres réalistes, stress tests et formation guidée : les erreurs ne coûtent rien." },
  { icone: ShieldCheck, titre: "Un compte sécurisé", texte: "Mots de passe hachés, sessions révocables, journal d'audit. Connexion avec Google ou GitHub possible." },
];

export default function Auth({ onConnecte }: { onConnecte: (u: Utilisateur) => void }) {
  const [mode, setMode] = useState<"connexion" | "inscription">("connexion");
  const [email, setEmail] = useState("");
  const [nom, setNom] = useState("");
  const [mdp, setMdp] = useState("");
  const [voir, setVoir] = useState(false);
  const [majuscules, setMajuscules] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const [fournisseurs, setFournisseurs] = useState<string[] | null>(null);

  useEffect(() => {
    setErreur(erreurOauth());
    void fournisseursOauth().then(setFournisseurs);
  }, []);

  const f = useMemo(() => force(mdp), [mdp]);

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

  const social = (cle: "google" | "github", libelle: string, icone: React.ReactNode) => {
    const dispo = fournisseurs?.includes(cle) ?? false;
    return dispo ? (
      <a className="btn btn-social" href={`/api/v1/auth/oauth/${cle}/debut`}>{icone} {libelle}</a>
    ) : (
      <button type="button" className="btn btn-social" disabled title="Pas encore configuré sur ce serveur (voir GUIDE_CONNEXION_SOCIALE.md)">{icone} {libelle}</button>
    );
  };

  return (
    <main className="auth">
      <div className="auth-theme"><BoutonTheme /></div>
      <section className="auth-recit">
        <p className="marque">Salle de marché</p>
        <h1>Apprenez les marchés en les rejouant.</h1>
        <p className="auth-intro">Un simulateur de salle de marché pour comprendre, tester et décider, avec de l&apos;argent virtuel.</p>
        <ul className="auth-atouts">
          {ATOUTS.map(({ icone: Icone, titre, texte }) => (
            <li key={titre}>
              <span className="auth-atout-icone"><Icone size={20} aria-hidden="true" /></span>
              <div><strong>{titre}</strong><p className="discret">{texte}</p></div>
            </li>
          ))}
        </ul>
        <ol className="auth-reperes" aria-label="Moments à rejouer">
          {REPERES.slice(0, 4).map((r) => (
            <li key={r.date}>
              <time dateTime={r.date}>{dateCourte(`${r.date}T00:00:00`)}</time>
              <span>{r.titre}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="auth-formulaire">
        <div className="auth-carte">
          <h2>{mode === "connexion" ? "Bon retour" : "Créer votre compte"}</h2>
          <p className="discret">{mode === "connexion" ? "Connectez-vous pour reprendre votre simulation." : "Gratuit, en quelques secondes. Aucun vrai argent n'est en jeu."}</p>

          <div className="auth-sociaux">
            {social("google", "Continuer avec Google", <Google />)}
            {social("github", "Continuer avec GitHub", <GitHub />)}
          </div>
          <p className="auth-ou"><span>ou avec votre e-mail</span></p>

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
              <div className="champ-mdp">
                <input id="mdp" type={voir ? "text" : "password"} value={mdp} onChange={(e) => setMdp(e.target.value)}
                  onKeyUp={(e) => setMajuscules(e.getModifierState("CapsLock"))} onBlur={() => setMajuscules(false)}
                  autoComplete={mode === "connexion" ? "current-password" : "new-password"} aria-describedby={mode === "inscription" ? "aide-mdp" : undefined} required />
                <button type="button" className="btn-icone" onClick={() => setVoir(!voir)} aria-label={voir ? "Masquer le mot de passe" : "Afficher le mot de passe"} aria-pressed={voir}>
                  {voir ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
                </button>
              </div>
              {majuscules && <p className="aide" role="status">Le verrouillage des majuscules est activé.</p>}
              {mode === "inscription" && (
                <div id="aide-mdp" className="force">
                  <div className="force-barre" aria-hidden="true">{[1, 2, 3, 4].map((n) => <i key={n} data-actif={f.niveau >= n} data-niveau={f.niveau} />)}</div>
                  <p className="aide">{mdp ? `Force : ${NOMS_FORCE[f.niveau]}. ` : ""}{f.regles.map((r) => `${r.ok ? "✓" : "○"} ${r.texte}`).join("  ")}</p>
                </div>
              )}
            </div>
            {erreur && <p className="erreur" role="alert">{erreur}</p>}
            <button className="btn btn-principal btn-large" type="submit" disabled={envoi}>
              {envoi ? "Un instant…" : mode === "connexion" ? "Se connecter" : "Créer mon compte"}
            </button>
          </form>

          <p className="auth-bascule">
            {mode === "connexion" ? "Pas encore de compte ? " : "Déjà inscrit ? "}
            <button type="button" className="lien" onClick={() => { setMode(mode === "connexion" ? "inscription" : "connexion"); setErreur(null); }}>
              {mode === "connexion" ? "Créer un compte" : "Se connecter"}
            </button>
          </p>
          <p className="aide auth-mentions">Outil pédagogique : ce simulateur ne donne aucun conseil en investissement.</p>
        </div>
      </section>
    </main>
  );
}
