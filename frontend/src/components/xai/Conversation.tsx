"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { dateCourte } from "@/lib/format";
import { useXAI, type Preuve } from "./ContexteXAI";

export function PreuveXAI({ preuve }: { preuve: Preuve }) {
  const maximum = Math.max(1e-12, ...preuve.barres.map((b) => Math.abs(b.valeur)));
  return (
    <div className="xai-preuve">
      <p className="xai-methode"><small>Méthode</small><strong>{preuve.methode}</strong></p>
      {preuve.barres.length > 0 && (
        <ul className="xai-barres">
          {preuve.barres.map((b, i) => (
            <li key={`${i}-${b.nom}`}>
              <span>{b.nom}</span><strong>{b.valeur < 0 && !/^[−-]/.test(b.affiche) ? `−${b.affiche}` : b.affiche}</strong>
              <i aria-hidden="true"><em data-sens={b.valeur < 0 ? "negatif" : undefined} style={{ width: `${(Math.abs(b.valeur) / maximum) * 100}%` }} /></i>
            </li>
          ))}
        </ul>
      )}
      {preuve.donnees.length > 0 && <ul className="xai-donnees">{preuve.donnees.map((d, i) => <li key={`${i}-${d}`}>{d}</li>)}</ul>}
      <p className="xai-limite">Limite&nbsp;: {preuve.limite}</p>
    </div>
  );
}

export function Fil({ avecPreuve, naviguer }: { avecPreuve: boolean; naviguer?: () => void }) {
  const { fil, demander, attente } = useXAI();
  const ref = useRef<HTMLDivElement>(null);
  const derniere = fil.length ? fil[fil.length - 1].id : null;
  useEffect(() => {
    const cadre = ref.current;
    if (!cadre) return;
    const derniers = cadre.querySelectorAll<HTMLElement>(".xai-question");
    const derniere = derniers[derniers.length - 1];
    // la dernière question en haut : une réponse longue se lit depuis son début
    cadre.scrollTop = derniere ? derniere.offsetTop - 6 : 0;
  }, [fil]);

  return (
    <div ref={ref} className="xai-fil" aria-live="polite">
      <div className="xai-msg xai-bot">
        <p>Bonjour. Posez une question sur la plateforme&nbsp;: je réponds avec vos chiffres et je montre mon raisonnement.</p>
        <small className="xai-date">Règles explicables, sans modèle de langage ni internet.</small>
      </div>
      {fil.map((e) => (
        <div key={e.id} className="xai-echange">
          <p className="xai-msg xai-question">{e.question}</p>
          <div className="xai-msg xai-bot" data-erreur={e.erreur ? "" : undefined}>
            <p>{e.erreur ?? e.reponse?.texte ?? "Je calcule…"}</p>
            {e.reponse && <small className="xai-date">Calculé au {dateCourte(e.reponse.instant)}</small>}
            {avecPreuve && e.reponse && (
              <details>
                <summary>Pourquoi cette réponse&nbsp;?</summary>
                <PreuveXAI preuve={e.reponse.preuve} />
              </details>
            )}
            {e.reponse?.lien && <Link className="xai-lien" href={e.reponse.lien.href} onClick={naviguer}>{e.reponse.lien.libelle}</Link>}
          </div>
          {e.id === derniere && e.reponse?.suivantes && e.reponse.suivantes.length > 0 && (
            <div className="xai-suites" role="group" aria-label="Questions de suite">
              {e.reponse.suivantes.map((q) => (
                <button key={q} type="button" disabled={attente} onClick={() => void demander(q)}>{q}</button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function Suggestions() {
  const { suggestions, demander, attente, expliquerPage } = useXAI();
  return (
    <div className="xai-suggestions" role="group" aria-label="Questions proposées">
      <button type="button" className="xai-page-bouton" disabled={attente} onClick={() => void expliquerPage()}>Explique cette page</button>
      {suggestions.map((q) => <button key={q} type="button" disabled={attente} onClick={() => void demander(q)}>{q}</button>)}
    </div>
  );
}

export function Saisie({ focus = false }: { focus?: boolean }) {
  const { demander, attente } = useXAI();
  const [question, setQuestion] = useState("");
  const champ = useRef<HTMLInputElement>(null);
  useEffect(() => { if (focus) champ.current?.focus(); }, [focus]);

  function envoyer(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || attente) return;
    void demander(question);
    setQuestion("");
  }
  return (
    <form className="xai-saisie" onSubmit={envoyer}>
      <input ref={champ} value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={300} autoComplete="off"
        placeholder="Posez votre question" aria-label="Votre question" />
      <button type="submit" disabled={attente || !question.trim()}>Envoyer</button>
    </form>
  );
}
