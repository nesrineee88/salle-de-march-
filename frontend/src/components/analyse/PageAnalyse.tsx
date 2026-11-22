"use client";

import { useMemo, useState } from "react";
import { useMarche } from "../Contexte";
import PageStrategies from "../PageStrategies";
import LectureSentiment from "./LectureSentiment";
import LectureTechnique from "./LectureTechnique";

const ONGLETS = [["technique", "Lecture technique"], ["sentiment", "Sentiment de la presse"], ["strategies", "Stratégies"]] as const;
type Onglet = (typeof ONGLETS)[number][0];

export default function PageAnalyse() {
  const { actifs } = useMarche();
  const negociables = useMemo(() => actifs.filter((a) => a.tradable && a.disponible), [actifs]);
  const [onglet, setOnglet] = useState<Onglet>("technique");
  const [choisi, setChoisi] = useState("");
  const symbole = choisi || negociables.find((a) => a.symbole === "AAPL")?.symbole || negociables[0]?.symbole || "";

  return (
    <div className="lecture">
      <header className="lecture-tete">
        <div>
          <h1>Analyse</h1>
          <p>Ce que disent les indicateurs et la presse sur un actif, et surtout : est-ce que ça a vraiment servi sur son passé ?</p>
        </div>
        {onglet !== "strategies" && (
          <label className="lecture-actif">
            <span>Actif</span>
            <select value={symbole} onChange={(e) => setChoisi(e.target.value)}>
              {negociables.map((a) => <option key={a.symbole} value={a.symbole}>{a.nom} · {a.symbole}</option>)}
            </select>
          </label>
        )}
      </header>
      <div className="seance-segments lecture-onglets" role="tablist" aria-label="Type d’analyse">
        {ONGLETS.map(([cle, nom]) => (
          <button key={cle} type="button" role="tab" aria-selected={onglet === cle} aria-pressed={onglet === cle} onClick={() => setOnglet(cle)}>{nom}</button>
        ))}
      </div>
      {onglet === "technique" && symbole && <LectureTechnique symbole={symbole} />}
      {onglet === "sentiment" && symbole && <LectureSentiment symbole={symbole} />}
      {onglet === "strategies" && <PageStrategies />}
      {onglet !== "strategies" && (
        <p className="lecture-petit">
          Analyse fondamentale : pas présentée. Les comptes officiels des entreprises (SEC) demandent une adresse de contact pour être collectés,
          et nous n’affichons pas de chiffres comptables inventés.
        </p>
      )}
    </div>
  );
}
