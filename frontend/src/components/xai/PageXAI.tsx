"use client";

import { useXAI } from "./ContexteXAI";
import { Fil, PreuveXAI, Saisie, Suggestions } from "./Conversation";

export default function PageXAI() {
  const { fil } = useXAI();
  const derniere = [...fil].reverse().find((e) => e.reponse)?.reponse;
  return (
    <main className="xai-page">
      <section className="xai-colonne">
        <header>
          <h1>Assistant XAI</h1>
          <p>Il répond, et il prouve.</p>
        </header>
        <Fil avecPreuve />
        <Suggestions />
        <Saisie />
      </section>
      <aside className="xai-pourquoi" aria-label="Pourquoi cette réponse">
        <h2>Pourquoi cette réponse</h2>
        {derniere ? <PreuveXAI preuve={derniere.preuve} /> : (
          <p className="xai-vide">Posez une question&nbsp;: la méthode, les données, la part de chaque facteur et la limite s’affichent ici.</p>
        )}
      </aside>
    </main>
  );
}
