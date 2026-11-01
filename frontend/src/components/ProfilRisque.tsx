"use client";

import { useEffect, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import type { ProfilRisque as Profil, Question, Utilisateur } from "@/lib/types";

interface Props {
  utilisateur: Utilisateur;
  onEnregistre: (u: Utilisateur) => void;
}

/** Questionnaire de profil de risque, affiché directement dans la page Compte. */
export default function ProfilRisque({ utilisateur, onEnregistre }: Props) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [avertissement, setAvertissement] = useState("");
  const [reponses, setReponses] = useState<Record<string, number>>(utilisateur.profil_risque?.reponses ?? {});
  const [resultat, setResultat] = useState<Profil | null>(utilisateur.profil_risque);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    api<{ questions: Question[]; avertissement: string }>("/api/v1/profil-risque/questionnaire")
      .then((r) => { setQuestions(r.questions); setAvertissement(r.avertissement); })
      .catch((e) => setErreur(e.message));
  }, []);

  const complet = questions.length > 0 && questions.every((q) => reponses[q.id]);

  async function enregistrer(e: React.FormEvent) {
    e.preventDefault();
    setErreur(null);
    setEnvoi(true);
    try {
      const p = await api<Profil>("/api/v1/moi/profil-risque", { methode: "POST", corps: { reponses } });
      setResultat(p);
      onEnregistre(await api<Utilisateur>("/api/v1/moi"));
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : "Le profil n'a pas pu être enregistré.");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <div>
      <p className="aide">{avertissement || "Outil pédagogique, pas un conseil en investissement."} Votre perte maximale tolérée sert ensuite à comparer vos portefeuilles aux scénarios de crise.</p>
      {resultat && (
        <p className="message-ok" role="status">
          Profil actuel : <strong>{resultat.categorie}</strong>, perte maximale tolérée {resultat.perte_max_toleree_pct} %.
        </p>
      )}
      <form onSubmit={enregistrer}>
        {questions.map((q, i) => (
          <fieldset key={q.id} className="question">
            <legend>{i + 1}. {q.texte}</legend>
            {q.choix.map((c, k) => (
              <label key={c} className="choix">
                <input type="radio" name={q.id} checked={reponses[q.id] === k + 1} onChange={() => setReponses({ ...reponses, [q.id]: k + 1 })} />
                <span>{c}</span>
              </label>
            ))}
          </fieldset>
        ))}
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <button className="btn btn-principal btn-auto" type="submit" disabled={!complet || envoi}>{envoi ? "Enregistrement…" : "Enregistrer mon profil"}</button>
      </form>
    </div>
  );
}
