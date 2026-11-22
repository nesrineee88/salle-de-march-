"use client";

import { useState } from "react";
import { Maximize, Play } from "lucide-react";
import { entier } from "@/lib/format";
import Affiche from "./Affiche";
import type { AccueilJeu, Acte, CleDifficulte, ModeJeu, Plan } from "./types";

export interface Demarrage { mode: ModeJeu; film: string | null; difficulte: CleDifficulte; plan: Plan | null }

interface Props {
  accueil: AccueilJeu;
  envoi: boolean;
  demarrer: (d: Demarrage) => void;
  reprendre: (id: string) => void;
  abandonner: (id: string) => void;
  pleinEcran: () => void;
}

export default function Accueil({ accueil, envoi, demarrer, reprendre, abandonner, pleinEcran }: Props) {
  const [film, setFilm] = useState(() => accueil.films.find((f) => f.disponible)?.id ?? "mystere");
  const [jury, setJury] = useState(false);
  const [perte, setPerte] = useState<number | null>(null);
  const [reaction, setReaction] = useState<Acte | null>(null);
  const [difficulte, setDifficulte] = useState<CleDifficulte>("acteur");

  const mystere = film === "mystere";
  const choisi = accueil.films.find((f) => f.id === film);
  const mode: ModeJeu = mystere ? "mystere" : jury ? "jury" : "solo";
  const sansPlan = mode === "jury";
  const manque = sansPlan ? null : perte === null ? "Choisissez votre perte maximale." : reaction === null ? "Choisissez votre réaction en cas de krach." : null;

  const lancer = () => demarrer({
    mode, film: mystere ? null : film, difficulte,
    plan: !sansPlan && perte !== null && reaction !== null ? { perte_max: perte, reaction } : null,
  });

  return (
    <div className="obscure-accueil">
      <header className="obscure-tete">
        <div>
          <p className="obscure-surtitre">Le jeu de Séance</p>
          <h1>La Salle Obscure</h1>
          <p>Une vraie crise est projetée. Le public, c’est le marché : il se lève quand il a peur. Resterez-vous assis ?</p>
        </div>
        <button type="button" className="obscure-bouton" onClick={pleinEcran}><Maximize size={16} aria-hidden="true" />Plein écran</button>
      </header>

      {accueil.reprise && (
        <div className="obscure-reprise" role="status">
          <p>Une projection est en pause : <strong>{accueil.reprise.titre}</strong>. En débuter une autre l’abandonne.</p>
          <button type="button" className="obscure-bouton" onClick={() => abandonner(accueil.reprise!.id)}>Abandonner</button>
          <button type="button" className="obscure-bouton obscure-bouton-fort" onClick={() => reprendre(accueil.reprise!.id)}>Reprendre</button>
        </div>
      )}

      <div className="obscure-affiches" role="group" aria-label="Choisir un film">
        {accueil.films.map((f) => (
          <button key={f.id} type="button" className="obscure-affiche" data-film={f.id} aria-pressed={film === f.id} disabled={!f.disponible} onClick={() => setFilm(f.id)}>
            <Affiche film={f.id} />
            <span className="obscure-affiche-texte">
              <small>{f.sujet}</small><strong>{f.titre}</strong>
              <em>{f.indisponible ?? (f.meilleur !== null ? `Meilleure note ${f.meilleur}` : "Vrais cours")}</em>
            </span>
          </button>
        ))}
        <button type="button" className="obscure-affiche" data-film="mystere" aria-pressed={mystere} disabled={!accueil.mystere.disponible}
          onClick={() => { setFilm("mystere"); setJury(false); }}>
          <Affiche film="mystere" />
          <span className="obscure-affiche-texte">
            <small>Séance mystère, classée</small><strong>Bobine Sans Titre</strong>
            <em>{accueil.mystere.meilleur !== null ? `Meilleure note ${accueil.mystere.meilleur}` : "Dates et noms masqués"}</em>
          </span>
        </button>
      </div>

      <section className="obscure-billet" aria-label="Votre séance">
        <div className="obscure-billet-film">
          <small>{mystere ? "Séance mystère" : choisi?.sujet}</small>
          <h2>{mystere ? "Bobine Sans Titre" : choisi?.titre}</h2>
          <p>{mystere ? "Aucune date, aucun nom. Devinez la crise au générique." : choisi?.accroche}</p>
          {choisi && (
            <p className="obscure-intensite">
              Intensité
              <span role="img" aria-label={`${choisi.intensite} sur 5`}>
                {[1, 2, 3, 4, 5].map((i) => <i key={i} data-plein={i <= choisi.intensite || undefined} />)}
              </span>
            </p>
          )}
          <p className="obscure-petit">{entier(accueil.capital)} USD fictifs, sans lien avec votre portefeuille. Un ordre part à l’ouverture suivante.</p>
          {mystere ? (
            <p className="obscure-petit">{accueil.mystere.classable ? "Film tiré parmi les trois. La note est classée si vous ne l’aviez jamais vu : réponse au générique." : "Vous avez déjà vu tous les films : cette séance reste hors classement."}</p>
          ) : (
            <div className="obscure-qui" role="group" aria-label="Qui décide">
              <button type="button" aria-pressed={!jury} onClick={() => setJury(false)}>Je joue</button>
              <button type="button" aria-pressed={jury} onClick={() => setJury(true)}>Le jury décide</button>
            </div>
          )}
        </div>

        {sansPlan ? (
          <div className="obscure-billet-plan obscure-jury">
            <h3>Le jury décide</h3>
            <p>Le film s’arrête trois fois. Le jury choisit devant la salle et vous cliquez, ou tapez 1, 2, 3 ou 4.</p>
            <p>Au générique, le montage rejoue chacune de ses décisions.</p>
            <p className="obscure-petit">Démonstration hors classement, sans note : on ne note pas quelqu’un sur le plan d’un autre.</p>
          </div>
        ) : (
          <div className="obscure-billet-plan">
            <h3>Votre plan, avant le film</h3>
            <fieldset>
              <legend>Je ne veux pas perdre plus de</legend>
              <div className="obscure-pertes">
                {accueil.pertes_max.map((p) => <button key={p} type="button" data-perte={p} aria-pressed={perte === p} onClick={() => setPerte(p)}>{p} %</button>)}
              </div>
            </fieldset>
            <fieldset>
              <legend>Si un krach arrive, je vais</legend>
              <div className="obscure-reactions">
                {accueil.reactions.map((r) => (
                  <button key={r.acte} type="button" data-reaction={r.acte} title={r.detail} aria-pressed={reaction === r.acte} onClick={() => setReaction(r.acte)}>{r.nom}</button>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend>Difficulté</legend>
              <div className="obscure-niveaux">
                {accueil.difficultes.map((d) => (
                  <button key={d.cle} type="button" title={d.detail} aria-pressed={difficulte === d.cle} onClick={() => setDifficulte(d.cle)}>{d.nom}</button>
                ))}
              </div>
              <p className="obscure-petit">{accueil.difficultes.find((d) => d.cle === difficulte)?.detail}</p>
            </fieldset>
          </div>
        )}

        <button type="button" className="obscure-debuter" disabled={envoi || manque !== null} onClick={lancer}>
          <span><Play size={22} fill="currentColor" aria-hidden="true" />{envoi ? "Préparation…" : "Débuter"}</span>
          {manque && <small>{manque}</small>}
        </button>
      </section>

      <div className="obscure-bas">
        <section>
          <h2>Classement des séances mystère</h2>
          {accueil.classement.length === 0 ? <p className="obscure-petit">Personne n’est encore classé.</p> : (
            <ol className="obscure-classement">
              {accueil.classement.map((l) => (
                <li key={l.rang}><span>{l.rang}</span><strong>{l.nom}</strong><small>{l.parties} séance{l.parties > 1 ? "s" : ""}</small><b>{l.note}</b></li>
              ))}
            </ol>
          )}
        </section>
        <section>
          <h2>Comment la note est calculée</h2>
          <ul className="obscure-regles">
            <li><strong>40 %</strong>Résultat contre votre double, qui ne touche à rien</li>
            <li><strong>35 %</strong>Protection : votre pire baisse</li>
            <li><strong>25 %</strong>Respect de votre propre plan</li>
          </ul>
          <p className="obscure-petit">Plan tenu à moins de 50 % : note plafonnée à 55. Cours réels figés (Yahoo Finance, ajustés des dividendes). Événements rédigés de mémoire, à vérifier.</p>
        </section>
      </div>
    </div>
  );
}
