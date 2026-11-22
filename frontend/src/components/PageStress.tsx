"use client";

import { useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { useLecture } from "@/lib/hooks";
import { ChoixCrise, ParametresAppliques, pcCourt, resumeParametres } from "./stress/Communs";
import Comparer from "./stress/Comparer";
import Detail from "./stress/Detail";
import {
  LIBELLE_TYPE, TYPE_COURT, dateFr, type CleIntensite, type CleType, type Comparaison, type ListeBanquesReelles, type TypeBanque,
} from "./stress/types";

type Mode = "une" | "comparer";
interface Demande { mode: Mode; banques: string[]; type: CleType; intensite: CleIntensite; lgd: number | null }
const cleDemande = (d: Demande) => JSON.stringify([d.mode, [...d.banques].sort(), d.type, d.intensite, d.lgd]);

export default function PageStress() {
  const { donnees: liste, erreur } = useLecture<ListeBanquesReelles>("/api/v1/stress/reelles/banques", 3_600_000);
  const [mode, setMode] = useState<Mode>("comparer");
  const [banque, setBanque] = useState("aljazira");
  const [cochees, setCochees] = useState<string[] | null>(null);          // null : toutes
  const [type, setType] = useState<CleType>("recession");
  const [intensite, setIntensite] = useState<CleIntensite>("severe");
  const [lgdImposee, setLgdImposee] = useState(false);
  const [lgd, setLgd] = useState(0.45);
  const [resultat, setResultat] = useState<{ demande: Demande; comp: Comparaison } | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreurCalcul, setErreurCalcul] = useState<string | null>(null);

  const toutes = liste?.banques.map((b) => b.cle) ?? [];
  const selection = cochees ?? toutes;
  const demande: Demande = { mode, banques: mode === "une" ? [banque] : selection, type, intensite, lgd: lgdImposee ? lgd : null };
  const pret = mode === "une" ? !!banque : selection.length >= 2;
  const perime = resultat !== null && cleDemande(resultat.demande) !== cleDemande(demande);
  const prevu = liste?.catalogue.types.find((t) => t.cle === type)?.intensites[intensite];

  async function lancer(d: Demande = demande) {
    setEnCours(true); setErreurCalcul(null);
    try {
      const comp = await api<Comparaison>("/api/v1/stress/reelles/comparer", {
        methode: "POST", corps: { type: d.type, intensite: d.intensite, lgd: d.lgd, banques: d.banques },
      });
      setResultat({ demande: d, comp });
      const doux = !matchMedia("(prefers-reduced-motion: reduce)").matches;
      requestAnimationFrame(() => document.getElementById("stress-resultat")?.scrollIntoView({ block: "start", behavior: doux ? "smooth" : "auto" }));
    } catch (e) {
      setErreurCalcul(e instanceof ErreurApi ? e.message : "Simulation impossible.");
    } finally {
      setEnCours(false);
    }
  }
  function cocher(cle: string) {
    setCochees(selection.includes(cle) ? selection.filter((c) => c !== cle) : [...selection, cle]);
  }
  function cocherGroupe(t: TypeBanque | "toutes") {
    setCochees(t === "toutes" ? null : liste!.banques.filter((b) => b.type === t).map((b) => b.cle));
  }
  function simulerSeule(cle: string) {
    setMode("une"); setBanque(cle);
    void lancer({ ...demande, mode: "une", banques: [cle] });
  }

  const r = liste?.resume;
  const lgdPct = Math.round(lgd * 100);

  return (
    <main className="stress">
      <header className="stress-titre">
        <div>
          <h1>Stress testing bancaire</h1>
          <p>Choisissez une banque ou plusieurs, une crise et son intensité, et voyez si leur capital tient quand les prêts font défaut.</p>
        </div>
        {r && (
          <div className="stress-badges">
            <span className="stress-badge stress-badge-reel" role="note">
              Données réelles · {r.dates_arrete.map(dateFr).join(", ")} · {r.nb} banques{r.pays.join("") === "SA" ? " saoudiennes" : ""}
            </span>
            {r.nb_relues < r.nb && <span className="stress-tag stress-tag-coussin">{r.nb - r.nb_relues} sur {r.nb} à relire</span>}
          </div>
        )}
      </header>

      {erreur && <p className="stress-erreur" role="alert">Les banques réelles ne se chargent pas : {erreur}</p>}
      {!liste && !erreur && <p className="stress-etat" role="status">Chargement des banques…</p>}

      {liste && (
        <>
          <section className="stress-panneau stress-reglage" aria-labelledby="stress-titre-reglage">
            <h2 id="stress-titre-reglage" className="sr-only">Préparer la simulation</h2>

            <div className="stress-etape">
              <p className="stress-etape-titre"><i aria-hidden="true">1</i> Quelles banques ?</p>
              <div className="stress-bascule" role="radiogroup" aria-label="Une banque ou une comparaison">
                <button type="button" role="radio" aria-checked={mode === "une"} onClick={() => setMode("une")}>Une banque</button>
                <button type="button" role="radio" aria-checked={mode === "comparer"} onClick={() => setMode("comparer")}>Comparer</button>
              </div>
              {mode === "une" ? (
                <label className="stress-champ">
                  <span className="sr-only">Banque</span>
                  <select value={banque} onChange={(e) => setBanque(e.target.value)}>
                    {(["islamique", "conventionnelle"] as TypeBanque[]).map((t) => (
                      <optgroup key={t} label={LIBELLE_TYPE[t]}>
                        {liste.banques.filter((b) => b.type === t).map((b) => <option key={b.cle} value={b.cle}>{b.nom}</option>)}
                      </optgroup>
                    ))}
                  </select>
                </label>
              ) : (
                <>
                  <div className="stress-raccourcis">
                    <button type="button" onClick={() => cocherGroupe("toutes")}>Toutes</button>
                    <button type="button" onClick={() => cocherGroupe("islamique")}>Islamiques</button>
                    <button type="button" onClick={() => cocherGroupe("conventionnelle")}>Conventionnelles</button>
                  </div>
                  <fieldset className="stress-coches">
                    <legend className="sr-only">Banques à comparer</legend>
                    {liste.banques.map((b) => (
                      <label key={b.cle}>
                        <input type="checkbox" checked={selection.includes(b.cle)} onChange={() => cocher(b.cle)} />
                        <span>{b.nom}</span><small>{TYPE_COURT[b.type]}</small>
                      </label>
                    ))}
                  </fieldset>
                  {selection.length < 2 && <p className="stress-aide" role="status">Cochez au moins deux banques pour comparer.</p>}
                </>
              )}
            </div>

            <div className="stress-etape">
              <p className="stress-etape-titre"><i aria-hidden="true">2</i> Quelle crise ?</p>
              <ChoixCrise catalogue={liste.catalogue} type={type} intensite={intensite} choisirType={setType} choisirIntensite={setIntensite} />
              {prevu && (
                <p className="stress-choque">
                  <b>Ce qui est choqué :</b> {resumeParametres(lgdImposee ? { ...prevu, lgd: { ...prevu.lgd, valeur: lgd } } : prevu)}.
                  {" "}Origine de chaque valeur dans le résultat.
                </p>
              )}
              <details className="stress-avance-lgd">
                <summary>Réglage avancé : imposer la LGD</summary>
                <label className="stress-case-a-cocher">
                  <input type="checkbox" checked={lgdImposee} onChange={(e) => setLgdImposee(e.target.checked)} />
                  <span>Remplacer la LGD du scénario ({pcCourt(prevu?.lgd.valeur ?? 0.45)})</span>
                </label>
                <label className="stress-champ stress-curseur">
                  <span>LGD imposée : <b>{lgdPct} %</b></span>
                  <input type="range" min={liste.catalogue.lgd_min * 100} max={liste.catalogue.lgd_max * 100} step={5} value={lgdPct}
                    disabled={!lgdImposee} onChange={(e) => setLgd(Number(e.target.value) / 100)} aria-valuetext={`${lgdPct} %`} />
                </label>
              </details>
            </div>

            <div className="stress-lancer">
              <button type="button" className="btn btn-principal" onClick={() => void lancer()} disabled={!pret || enCours}>
                {enCours ? "Simulation…" : "Lancer la simulation"}
              </button>
              {perime && <p className="stress-aide" role="status">Les réglages ont changé : relancez pour mettre le résultat à jour.</p>}
            </div>
          </section>

          {erreurCalcul && <p className="stress-erreur" role="alert">{erreurCalcul}</p>}

          <div id="stress-resultat" className={`stress-vue${perime ? " stress-perime" : ""}`} aria-live="polite">
            {!resultat && !enCours && <p className="stress-vide">Choisissez vos banques, une crise et son intensité, puis lancez la simulation.</p>}
            {resultat && (resultat.demande.mode === "une"
              ? <Detail r={resultat.comp.resultats[0]} banque={liste.banques.find((b) => b.cle === resultat.comp.resultats[0].cle)!} />
              : <Comparer comp={resultat.comp} ouvrir={simulerSeule} />)}
            {resultat?.comp.parametres && <ParametresAppliques p={resultat.comp.parametres} />}
          </div>

        </>
      )}
    </main>
  );
}
