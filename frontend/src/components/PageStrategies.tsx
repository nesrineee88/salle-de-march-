"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { nombre, pct, pctSigne } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import type { MetriquesBacktest, ResultatBacktest, StrategieCatalogue } from "@/lib/types";
import { useMarche } from "./Contexte";
import CourbesStrategies, { styleSerie } from "./CourbesStrategies";

const LIBELLE_PARAM: Record<string, { libelle: string; pas: number }> = {
  courte: { libelle: "Moyenne courte (jours)", pas: 1 },
  longue: { libelle: "Moyenne longue (jours)", pas: 1 },
  periode: { libelle: "Période de calcul (jours)", pas: 1 },
  bas: { libelle: "Seuil bas : on achète en dessous", pas: 1 },
  haut: { libelle: "Seuil haut : on vend au-dessus", pas: 1 },
  rapide: { libelle: "Moyenne rapide (jours)", pas: 1 },
  lente: { libelle: "Moyenne lente (jours)", pas: 1 },
  signal: { libelle: "Ligne de signal (jours)", pas: 1 },
  ecarts: { libelle: "Largeur des bandes (écarts-types)", pas: 0.1 },
  jours: { libelle: "Fenêtre de comparaison (jours)", pas: 1 },
};

const PAR_DEFAUT = ["croisement_sma", "rsi", "macd"];

type Periode = "metriques" | "premiere_moitie" | "seconde_moitie";
const PERIODES: { cle: Periode; libelle: string }[] = [
  { cle: "metriques", libelle: "Période complète" },
  { cle: "premiere_moitie", libelle: "Première moitié" },
  { cle: "seconde_moitie", libelle: "Seconde moitié" },
];

const COLONNES: { cle: keyof MetriquesBacktest; libelle: string; aide: string; format: (v: number | null) => string; ton?: boolean }[] = [
  { cle: "rendement_total", libelle: "Rendement total", aide: "Combien la stratégie a gagné ou perdu sur la période, frais compris.", format: (v) => pctSigne(v, 1), ton: true },
  { cle: "rendement_annuel", libelle: "Par an", aide: "Le même résultat ramené à une année, pour comparer des périodes de longueurs différentes.", format: (v) => pctSigne(v, 1), ton: true },
  { cle: "volatilite", libelle: "Volatilité", aide: "L'ampleur des variations quotidiennes, ramenée à un an. Plus elle est haute, plus le parcours est agité.", format: (v) => pct(v, 1) },
  { cle: "drawdown_max", libelle: "Pire baisse", aide: "La plus grande chute depuis un sommet, pendant la période.", format: (v) => (v === null ? "–" : v > 1e-9 ? `▼ −${pct(v, 1)}` : pct(v, 1)) },
  { cle: "sharpe", libelle: "Sharpe", aide: "Rendement obtenu pour chaque unité de volatilité. Au-dessus de 1, c'est généralement jugé bon ; en dessous de 0, la stratégie a perdu.", format: (v) => nombre(v, 2) },
  { cle: "sortino", libelle: "Sortino", aide: "Comme Sharpe, mais ne compte que les mauvaises variations.", format: (v) => nombre(v, 2) },
  { cle: "calmar", libelle: "Calmar", aide: "Rendement annuel divisé par la pire baisse.", format: (v) => nombre(v, 2) },
  { cle: "taux_reussite", libelle: "Trades gagnants", aide: "Part des allers-retours qui ont rapporté de l'argent (une position encore ouverte à la fin est comptée à son dernier cours). Un taux bas n'est pas un défaut si les gains sont gros.", format: (v) => pct(v, 0) },
  { cle: "temps_investi", libelle: "Temps investi", aide: "Part des jours où la stratégie détenait l'actif.", format: (v) => pct(v, 0) },
  { cle: "aller_retours", libelle: "Allers-retours", aide: "Nombre d'achats suivis d'une vente (l'achat-conservation en compte un seul). Chaque aller-retour coûte des frais.", format: (v) => (v === null ? "–" : String(v)) },
];

const JOUR_FR = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
function jourFr(iso: string | null): string { return iso ? JOUR_FR.format(Date.parse(`${iso}T00:00:00Z`)) : "–"; }

function ton(v: number | null): "gain" | "perte" | undefined { return v === null ? undefined : v > 0 ? "gain" : v < 0 ? "perte" : undefined; }

export default function PageStrategies() {
  const { actifs, inst, mode } = useMarche();
  const { donnees: catalogue, erreur: erreurCatalogue } = useLecture<StrategieCatalogue[]>("/api/v1/backtest/strategies", 3_600_000);
  const negociables = useMemo(() => actifs.filter((a) => a.tradable && a.disponible), [actifs]);

  const [symbole, setSymbole] = useState("");
  const [debut, setDebut] = useState("");
  const [cout, setCout] = useState("");
  const [choix, setChoix] = useState<Record<string, boolean>>(() => Object.fromEntries(PAR_DEFAUT.map((n) => [n, true])));
  const [params, setParams] = useState<Record<string, Record<string, string>>>({});
  const [resultat, setResultat] = useState<ResultatBacktest | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [masquees, setMasquees] = useState<Set<string>>(new Set());
  const [periode, setPeriode] = useState<Periode>("metriques");

  useEffect(() => {
    if (!symbole && negociables.length > 0) setSymbole(negociables.find((a) => a.symbole === "AAPL")?.symbole ?? negociables[0].symbole);
  }, [negociables, symbole]);

  const strategies = (catalogue ?? []).filter((s) => s.nom !== "achat_conservation");
  const nbChoisies = strategies.filter((s) => choix[s.nom]).length;

  async function lancer(e: React.FormEvent) {
    e.preventDefault();
    if (!symbole || nbChoisies === 0) return;
    setEnCours(true); setErreur(null);
    try {
      const corps = {
        symbole,
        strategies: strategies.filter((s) => choix[s.nom]).map((s) => ({
          nom: s.nom,
          parametres: Object.fromEntries(Object.entries(params[s.nom] ?? {}).filter(([, v]) => v.trim() !== "" && Number.isFinite(Number(v.replace(",", ".")))).map(([k, v]) => [k, Number(v.replace(",", "."))])),
        })),
        debut: debut || null,
        cout_bps: cout.trim() === "" ? null : Number(cout.replace(",", ".")),
      };
      if (corps.cout_bps !== null && !Number.isFinite(corps.cout_bps)) throw new ErreurApi(422, "Le coût par transaction doit être un nombre (en points de base).");
      const r = await api<ResultatBacktest>("/api/v1/backtest", { methode: "POST", corps });
      setResultat(r); setMasquees(new Set());
    } catch (exc) {
      setErreur(exc instanceof Error ? exc.message : "Le calcul a échoué.");
    } finally {
      setEnCours(false);
    }
  }

  function basculer(nom: string) {
    setMasquees((m) => { const n = new Set(m); if (n.has(nom)) n.delete(nom); else n.add(nom); return n; });
  }

  const ordre = resultat?.strategies.filter((s) => s.nom !== "achat_conservation").map((s) => s.nom) ?? [];

  return (
    <main className="page">
      <header className="page-tete">
        <h1>Stratégies et backtesting</h1>
        <p className="aide">
          Un backtest rejoue une règle d&apos;achat et de vente sur le passé pour voir ce qu&apos;elle aurait donné. Ici, seul le passé de votre date simulée
          {inst ? ` (${new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeZone: "UTC" }).format(new Date(inst.instant))})` : ""} est utilisé : vous ne verrez jamais le futur.
          L&apos;achat-conservation (acheter et ne rien faire) est toujours affiché : c&apos;est la référence à battre.
        </p>
      </header>

      <form className="panneau" onSubmit={lancer} aria-labelledby="titre-config">
        <header className="panneau-tete"><h2 id="titre-config">1. Que voulez-vous tester ?</h2></header>
        <div className="strat-champs">
          <div className="champ">
            <label htmlFor="strat-actif">Actif</label>
            <select id="strat-actif" value={symbole} onChange={(e) => setSymbole(e.target.value)}>
              {negociables.map((a) => <option key={a.symbole} value={a.symbole}>{a.symbole} · {a.nom}</option>)}
            </select>
          </div>
          <div className="champ">
            <label htmlFor="strat-debut">Début du test (facultatif)</label>
            <input id="strat-debut" type="date" value={debut} onChange={(e) => setDebut(e.target.value)} />
          </div>
          <div className="champ">
            <label htmlFor="strat-cout">Coût par transaction, en points de base (facultatif)</label>
            <input id="strat-cout" inputMode="decimal" placeholder="Automatique (frais + écart du marché)" value={cout} onChange={(e) => setCout(e.target.value)} />
          </div>
        </div>

        <fieldset className="strat-liste">
          <legend className="sous-titre">Stratégies à comparer (de 1 à 7)</legend>
          {erreurCatalogue && <p className="erreur" role="alert">{erreurCatalogue}</p>}
          {strategies.map((s) => (
            <div key={s.nom} className="strat-carte">
              <label className="strat-titre">
                <input type="checkbox" checked={!!choix[s.nom]} onChange={(e) => setChoix({ ...choix, [s.nom]: e.target.checked })} /> <strong>{s.libelle}</strong>
              </label>
              <p className="aide">{s.description}</p>
              {choix[s.nom] && Object.keys(s.parametres).length > 0 && (
                <details className="strat-params">
                  <summary>Réglages (facultatif)</summary>
                  <div className="strat-champs">
                    {Object.entries(s.parametres).map(([cle, defaut]) => {
                      const info = LIBELLE_PARAM[cle] ?? { libelle: cle, pas: 1 };
                      const id = `p-${s.nom}-${cle}`;
                      return (
                        <div className="champ" key={cle}>
                          <label htmlFor={id}>{info.libelle}</label>
                          <input id={id} inputMode="decimal" placeholder={`${defaut} (par défaut)`} value={params[s.nom]?.[cle] ?? ""}
                            onChange={(e) => setParams({ ...params, [s.nom]: { ...(params[s.nom] ?? {}), [cle]: e.target.value } })} />
                        </div>
                      );
                    })}
                  </div>
                </details>
              )}
            </div>
          ))}
        </fieldset>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <button className="btn btn-principal strat-lancer" type="submit" disabled={enCours || !symbole || nbChoisies === 0}>
          {enCours ? "Calcul en cours…" : `Lancer la comparaison (${nbChoisies} stratégie${nbChoisies > 1 ? "s" : ""})`}
        </button>
      </form>

      {resultat && (
        <>
          <section className="panneau" aria-labelledby="titre-courbes">
            <header className="panneau-tete">
              <h2 id="titre-courbes">2. Ce qu&apos;auraient valu 100 investis sur {resultat.symbole}</h2>
              <span className="discret">Du {jourFr(resultat.debut)} au {jourFr(resultat.fin)} · coût {nombre(resultat.cout_bps, 1)} points de base par transaction</span>
            </header>
            <ul className="strat-legende" aria-label="Légende : cliquez pour masquer ou afficher une courbe">
              {resultat.strategies.map((s) => {
                const st = styleSerie(s.nom, ordre.indexOf(s.nom));
                const final = s.courbe.valeurs[s.courbe.valeurs.length - 1] - 1;
                const cache = masquees.has(s.nom);
                return (
                  <li key={s.nom}>
                    <button type="button" aria-pressed={!cache} onClick={() => basculer(s.nom)} className="strat-legende-bouton">
                      <svg width="30" height="10" aria-hidden="true"><line x1="0" x2="30" y1="5" y2="5" stroke={st.couleur} strokeWidth="2.5" strokeDasharray={st.trait || undefined} opacity={cache ? 0.3 : 1} /></svg>
                      <span className={cache ? "strat-cache" : undefined}>{s.libelle}</span>
                      <strong className={ton(final)}>{pctSigne(final, 1)}</strong>
                    </button>
                  </li>
                );
              })}
            </ul>
            <CourbesStrategies strategies={resultat.strategies} masquees={masquees} />
          </section>

          <section className="panneau panneau-tableau" aria-labelledby="titre-mesures">
            <header className="panneau-tete strat-tete-tableau"><h2 id="titre-mesures">3. Les chiffres, stratégie par stratégie</h2></header>
            <div className="onglets" role="tablist" aria-label="Période des chiffres">
              {PERIODES.map((p) => <button key={p.cle} role="tab" aria-selected={periode === p.cle} className="onglet" onClick={() => setPeriode(p.cle)}>{p.libelle}</button>)}
            </div>
            <div className="tableau-defile" role="tabpanel">
              <table className="tableau tableau-strat">
                <caption className="sr-only">Mesures de performance et de risque pour chaque stratégie sur la {PERIODES.find((p) => p.cle === periode)!.libelle.toLowerCase()}</caption>
                <thead>
                  <tr>
                    <th scope="col">Stratégie</th>
                    {COLONNES.map((c) => <th scope="col" key={c.cle} title={c.aide}>{c.libelle}</th>)}
                    <th scope="col" title="Position à la dernière clôture connue : investi ou en liquidités">Aujourd&apos;hui</th>
                  </tr>
                </thead>
                <tbody>
                  {resultat.strategies.map((s) => {
                    const m = s[periode];
                    const st = styleSerie(s.nom, ordre.indexOf(s.nom));
                    return (
                      <tr key={s.nom}>
                        <th scope="row" className="strat-nom">
                          <svg width="22" height="8" aria-hidden="true"><line x1="0" x2="22" y1="4" y2="4" stroke={st.couleur} strokeWidth="2.5" strokeDasharray={st.trait || undefined} /></svg>
                          {s.libelle}{s.nom === "achat_conservation" && <small className="discret"> · référence</small>}
                        </th>
                        {COLONNES.map((c) => {
                          const v = m[c.cle] as number | null;
                          return <td key={c.cle} className={c.ton ? ton(v) : undefined}>{c.ton && v !== null && v !== 0 ? (v > 0 ? "▲ " : "▼ ") : ""}{c.format(v)}</td>;
                        })}
                        <td>{s.nom === "achat_conservation" ? "Investi" : s.signal_actuel >= 0.5 ? "Investi" : "Liquidités"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {mode === "apprenant" && (
              <details className="strat-aide">
                <summary>Comment lire ces chiffres ?</summary>
                <dl>
                  {COLONNES.map((c) => <div key={c.cle}><dt>{c.libelle}</dt><dd>{c.aide}</dd></div>)}
                </dl>
              </details>
            )}
          </section>

          <section className="panneau" aria-labelledby="titre-prudence">
            <header className="panneau-tete"><h2 id="titre-prudence">À garder en tête</h2></header>
            <ul className="strat-prudence">
              {resultat.avertissements.map((a) => <li key={a}>{a}</li>)}
              <li>Chaque ordre est supposé exécuté à l&apos;ouverture du lendemain du signal, avec les coûts indiqués. Le signal du jour n&apos;utilise que les clôtures déjà connues.</li>
              <li>Si une stratégie gagne sur la période complète mais perd sur l&apos;une des deux moitiés, son résultat dépend probablement du moment choisi plutôt que de la règle.</li>
            </ul>
          </section>
        </>
      )}
    </main>
  );
}
