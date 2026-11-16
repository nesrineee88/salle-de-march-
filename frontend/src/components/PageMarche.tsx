"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { prix, variation } from "@/lib/format";
import { AIDE, enregistrerChoix, lireChoix } from "@/lib/indicateurs";
import { enregistrerDessins, lireDessins, type Outil } from "@/lib/technique";
import type { Carnet as CarnetT, CleIndicateur, Classe, Dessin, Indicateurs, ReponseBougies, Unite } from "@/lib/types";
import BarreIndicateurs from "./BarreIndicateurs";
import Bas from "./Bas";
import Carnet from "./Carnet";
import { useMarche } from "./Contexte";
import Graphique, { type ModeTrace } from "./Graphique";
import OutilsTechniques from "./OutilsTechniques";
import Marches from "./Marches";
import { Star } from "lucide-react";
import { EVENEMENT_ACTIF, symboleDansAdresse } from "@/lib/actif";
import { useSuivis } from "@/lib/suivis";
import Protection from "./Protection";
import Ticket from "./Ticket";

const DEFAUT: Record<string, string> = { action: "AAPL", crypto: "BTC-USD", matiere: "GC=F" };
const TITRES: Record<string, string> = { action: "Actions", crypto: "Cryptomonnaies", matiere: "Matières premières" };
const enc = encodeURIComponent;

export default function PageMarche({ classe }: { classe: Classe }) {
  const { inst, actifs, pf, ordres, execs, mode, envoyer, annuler, utilisateur } = useMarche();
  const { estSuivi, basculer: basculerSuivi } = useSuivis(utilisateur.email);
  const [selection, setSelection] = useState<string>(() => symboleDansAdresse() ?? DEFAUT[classe]);
  const [donnees, setDonnees] = useState<ReponseBougies | null>(null);
  const [unite, setUnite] = useState<Unite>("1j");
  const [outils, setOutils] = useState<Outil[]>([]);
  const [modeTrace, setModeTrace] = useState<ModeTrace>("aucun");
  const [dessins, setDessins] = useState<Dessin[]>([]);
  const uniteRef = useRef(unite);
  uniteRef.current = unite;
  const [carnet, setCarnet] = useState<CarnetT | null>(null);
  const [indic, setIndic] = useState<Indicateurs | null>(null);
  const [choix, setChoix] = useState<CleIndicateur[]>([]);
  const selectionRef = useRef(selection);
  selectionRef.current = selection;

  const classes = useMemo<Classe[]>(() => (classe === "action" ? ["action", "indice"] : [classe]), [classe]);

  const lire = useCallback(async () => {
    const s = selectionRef.current, u = uniteRef.current;
    const [h, c, i] = await Promise.all([
      api<ReponseBougies>(`/api/v1/bougies/${enc(s)}?unite=${u}&barres=300`).catch(() => null),
      api<CarnetT>(`/api/v1/carnet/${enc(s)}`).catch(() => null),
      api<Indicateurs>(`/api/v1/indicateurs/${enc(s)}?barres=30`).catch(() => null),      // ATR journalier de l'en-tête
    ]);
    if (s === selectionRef.current && u === uniteRef.current) { setDonnees(h); setCarnet(c); setIndic(i); }
  }, []);

  useEffect(() => {
    void lire();
    const t = setInterval(() => { if (document.visibilityState === "visible") void lire(); }, 2500);
    return () => clearInterval(t);
  }, [lire, selection, unite]);

  useEffect(() => { setDessins(lireDessins(selection)); }, [selection]);
  const ajouterDessin = (d: Dessin) => setDessins((avant) => { const l = [...avant, d]; enregistrerDessins(selection, l); return l; });
  const effacerDessins = () => { setDessins([]); enregistrerDessins(selection, []); };

  // si le symbole par défaut n'a pas de données, on prend le premier disponible du marché
  useEffect(() => {
    if (!inst) return;
    const dispo = inst.cotations.filter((c) => classes.includes(actifs.find((a) => a.symbole === c.symbole)?.classe as Classe));
    if (dispo.length > 0 && !dispo.some((c) => c.symbole === selection)) setSelection(dispo[0].symbole);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inst, actifs, classe]);

  useEffect(() => { setChoix(lireChoix()); }, []);
  const changerChoix = (c: CleIndicateur[]) => { setChoix(c); enregistrerChoix(c); };

  const choisir = (s: string) => { setDonnees(null); setCarnet(null); setIndic(null); setSelection(s); };
  const changerUnite = (u: Unite) => { setDonnees(null); setUnite(u); };

  // Le bandeau de cours, la recherche et les suivis demandent un actif par un événement quand on est déjà sur la bonne page.
  useEffect(() => {
    const surActif = (e: Event) => {
      const symbole = (e as CustomEvent<string>).detail;
      const a = actifs.find((x) => x.symbole === symbole);
      if (a && classes.includes(a.classe)) choisir(symbole);
    };
    window.addEventListener(EVENEMENT_ACTIF, surActif);
    return () => window.removeEventListener(EVENEMENT_ACTIF, surActif);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actifs, classes]);

  const actif = actifs.find((a) => a.symbole === selection);
  const cotation = inst?.cotations.find((c) => c.symbole === selection);
  const base = cotation?.reference ?? cotation?.derniere_cloture ?? null;
  const v = cotation && base ? (cotation.prix - base) / Math.abs(base) : null;
  const bougies = donnees && donnees.symbole === selection ? donnees.bougies : [];
  const derniere = bougies[bougies.length - 1];
  const atr = indic && indic.symbole === selection ? [...(indic.series.atr ?? [])].reverse().find((v) => v !== null && v !== undefined) ?? null : null;
  // le marché "Actions" ne liste pas les positions des autres marchés dans le bas de page, mais le portefeuille reste unique
  const positionsDuMarche = pf ? { ...pf, positions: pf.positions.filter((p) => classes.includes(actifs.find((a) => a.symbole === p.symbole)?.classe as Classe)) } : null;
  const symbolesDuMarche = new Set(actifs.filter((a) => classes.includes(a.classe)).map((a) => a.symbole));

  return (
    <div className="page-marche">
      <Marches actifs={actifs} cotations={inst?.cotations ?? []} classes={classes} selection={selection} onSelect={choisir} titre={TITRES[classe]} />

      <main className="centre">
        <section className="graphique" aria-label="Graphique">
          <div className="graphique-tete">
            {actif && cotation ? (
              <>
                <h1><span className="graphique-symbole">{actif.symbole}</span> <span className="graphique-nom">{actif.nom}</span></h1>
                <p className="graphique-prix">{prix(cotation.prix)} <small>{actif.devise}</small></p>
                <p className={`graphique-var ${v !== null && v > 0 ? "gain" : v !== null && v < 0 ? "perte" : ""}`}>
                  {v !== null && (v > 0 ? "▲ " : v < 0 ? "▼ " : "")}{variation(v)}{" "}
                  <small>{cotation.statut === "ouvert" ? "depuis la dernière clôture" : "sur la dernière séance"}</small>
                </p>
                <p className="graphique-etat">
                  <span className={cotation.statut === "ouvert" ? "etat-ouvert" : "etat-ferme"}>{cotation.statut === "ouvert" ? "Marché ouvert" : "Marché fermé"}</span>
                  {cotation.origine === "tick_simule" && <span title="Les bougies sont réelles ; les mouvements dans la journée sont simulés à partir de la bougie du jour.">Mouvement intrajournalier simulé</span>}
                  {atr !== null && (
                    <span title={mode === "apprenant" ? AIDE.atr : undefined}>
                      ATR {indic?.parametres.atr ?? 14} : {prix(atr)}{cotation.prix ? ` (${variation(atr / Math.abs(cotation.prix)).replace("+", "")})` : ""}
                    </span>
                  )}
                </p>
                <button type="button" className="btn btn-icone-texte graphique-suivre" aria-pressed={estSuivi(actif.symbole)} onClick={() => basculerSuivi(actif.symbole)}
                  title={estSuivi(actif.symbole) ? "Retirer de Mes suivis" : "Ajouter à Mes suivis"}>
                  <Star size={16} aria-hidden="true" fill={estSuivi(actif.symbole) ? "currentColor" : "none"} /> {estSuivi(actif.symbole) ? "Suivi" : "Suivre"}
                </button>
              </>
            ) : <h1>Choisissez un actif</h1>}
          </div>
          {inst?.horloge.en_pause && !inst.termine && (
            <p className="bandeau-pause" role="status">La simulation est à l&apos;arrêt. Appuyez sur « Lancer », ou choisissez une date sur la frise.</p>
          )}
          <OutilsTechniques unite={unite} onUnite={changerUnite} outils={outils} onOutils={setOutils} modeTrace={modeTrace} onModeTrace={setModeTrace}
            nbDessins={dessins.length} onEffacer={effacerDessins} donnees={donnees && donnees.symbole === selection ? donnees : null} mode={mode} />
          <BarreIndicateurs choix={choix} onChange={changerChoix} mode={mode} parametres={donnees?.parametres ?? indic?.parametres ?? null} />
          {bougies.length > 0
            ? <Graphique bougies={bougies} symbole={selection} unite={unite} indicateurs={donnees?.indicateurs ?? null} choix={choix}
                niveaux={donnees?.niveaux ?? null} outils={outils} dessins={dessins} modeTrace={modeTrace} onDessin={ajouterDessin} />
            : <p className="vide">{donnees ? "Pas encore de bougies à cette date : avancez dans le temps." : "Chargement du graphique…"}</p>}
          {derniere?.en_formation && <p className="graphique-note">La dernière bougie est en cours de formation.</p>}
          {actif?.classe === "action" && (
            <p className="graphique-note">Prix ajustés des dividendes et des divisions d&apos;actions (source Yahoo Finance) : ils peuvent différer des cours affichés à l&apos;époque.</p>
          )}
        </section>

        <Bas pf={positionsDuMarche} ordres={ordres.filter((o) => symbolesDuMarche.has(o.symbole))} executions={execs.filter((e) => symbolesDuMarche.has(e.symbole))}
          onSelect={choisir} onAnnuler={(id) => void annuler(id)} />
      </main>

      <aside className="droite">
        <Ticket actif={actif} cotation={cotation} pf={pf} mode={mode} onEnvoyer={envoyer} />
        <Protection actif={actif} />
        <Carnet carnet={carnet} mode={mode} />
      </aside>
    </div>
  );
}
