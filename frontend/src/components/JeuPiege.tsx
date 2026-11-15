"use client";

import { useState } from "react";
import { Check, RotateCcw, X } from "lucide-react";
import { useJeux } from "@/lib/jeux";
import { PIEGES } from "@/lib/pieges";
import { useMarche } from "./Contexte";

/** Mini-jeu : chaque situation cache une erreur de gestion classique. 20 points au premier essai, 10 au second, 0 ensuite. */
export default function JeuPiege() {
  const { utilisateur } = useMarche();
  const { etat, enregistrerPiege } = useJeux(utilisateur.email);
  const [n, setN] = useState(() => Math.max(0, PIEGES.findIndex((p) => etat.pieges[p.id] === undefined)));
  const [essais, setEssais] = useState<number[]>([]);
  const [fini, setFini] = useState(false);

  const p = PIEGES[n] ?? PIEGES[0];
  const trouve = essais.includes(p.piege);
  const gagne = (nbEssais: number) => (nbEssais === 1 ? 20 : nbEssais === 2 ? 10 : 0);
  const total = PIEGES.reduce((s, x) => s + (etat.pieges[x.id] ?? 0), 0);
  const faits = PIEGES.filter((x) => etat.pieges[x.id] !== undefined).length;

  function choisir(k: number) {
    if (trouve || essais.includes(k)) return;
    const suite = [...essais, k];
    setEssais(suite);
    if (k === p.piege) enregistrerPiege(p.id, gagne(suite.length));
  }
  function suivant() {
    setEssais([]);
    if (n + 1 >= PIEGES.length) setFini(true); else setN(n + 1);
  }

  if (fini) {
    return (
      <section className="panneau resultat-lecon">
        <div className="anneau" style={{ ["--p" as string]: `${Math.round((total / (PIEGES.length * 20)) * 100)}%` }} data-reussi={total >= PIEGES.length * 12}><strong>{total}</strong></div>
        <h2>{total >= PIEGES.length * 12 ? "Œil de lynx" : "Bon début"}</h2>
        <p className="discret">{total} points sur {PIEGES.length * 20} possibles. Rejouez pour améliorer votre score : le meilleur résultat de chaque situation est conservé.</p>
        <button type="button" className="btn btn-principal btn-icone-texte" style={{ width: "auto" }} onClick={() => { setFini(false); setN(0); setEssais([]); }}><RotateCcw size={16} aria-hidden="true" /> Rejouer</button>
      </section>
    );
  }

  return (
    <section className="jeu" aria-labelledby="jeu-titre">
      <header className="jeu-tete">
        <div><h2 id="jeu-titre">Repère le piège</h2><p className="aide">Chaque situation contient une erreur de gestion. Trouvez-la en un minimum d&apos;essais.</p></div>
        <p className="jeu-score" aria-live="polite"><strong>{total}</strong> pts · {faits}/{PIEGES.length} situations</p>
      </header>
      <div className="lecon-progres" role="progressbar" aria-valuemin={0} aria-valuemax={PIEGES.length} aria-valuenow={n + 1} aria-label={`Situation ${n + 1} sur ${PIEGES.length}`}><i style={{ width: `${((n + 1) / PIEGES.length) * 100}%` }} /></div>

      <article className="panneau lecon-ecran" key={p.id}>
        <p className="lecon-surtitre">Situation {n + 1} · {p.titre}</p>
        <p className="lecon-idee">{p.situation}</p>
        {p.tableau && (
          <table className="tableau jeu-tableau">
            <thead><tr>{p.tableau.entetes.map((h) => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>{p.tableau.lignes.map((l) => <tr key={l[0]}>{l.map((c, k) => <td key={k}>{c}</td>)}</tr>)}</tbody>
          </table>
        )}
        <h3 className="jeu-question">{p.question}</h3>
        <div className="lecon-choix">
          {p.choix.map((c, k) => {
            const essaye = essais.includes(k);
            const etat = essaye ? (k === p.piege ? "juste" : "faux") : "neutre";
            return (
              <div key={k} className="jeu-choix" data-etat={etat}>
                <button type="button" className="lecon-option" disabled={trouve || essaye} onClick={() => choisir(k)} aria-pressed={essaye}>
                  <span className="lecon-lettre" aria-hidden="true">{essaye ? (k === p.piege ? <Check size={14} /> : <X size={14} />) : "ABCD"[k]}</span>{c.texte}
                </button>
                {essaye && <p className="aide jeu-explication" role="status">{c.explication}</p>}
              </div>
            );
          })}
        </div>
        {trouve && (
          <div className="jeu-bilan" role="status">
            <p><strong>{essais.length === 1 ? "Du premier coup !" : `Trouvé en ${essais.length} essais.`}</strong> +{gagne(essais.length)} points.</p>
            <p className="lecon-retenir"><strong>À retenir :</strong> {p.retenir}</p>
            <button type="button" className="btn btn-principal" style={{ width: "auto", marginTop: "0.5rem" }} onClick={suivant}>{n + 1 >= PIEGES.length ? "Voir mon score" : "Situation suivante"}</button>
          </div>
        )}
      </article>
    </section>
  );
}
