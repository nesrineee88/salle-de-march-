"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { prix, variation } from "@/lib/format";
import { AIDE, enregistrerChoix, lireChoix } from "@/lib/indicateurs";
import { enregistrerDessins, lireDessins, type Outil } from "@/lib/technique";
import type { Carnet as CarnetT, CleIndicateur, Classe, Dessin, Indicateurs, ReponseBougies, Unite } from "@/lib/types";
import BarreIndicateurs from "./BarreIndicateurs";
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
import BlocRepliable from "./ui/BlocRepliable";

const DEFAUT: Record<string, string> = { action: "AAPL", crypto: "BTC-USD", matiere: "GC=F" };
const TITRES: Record<string, string> = { action: "Actions", crypto: "Cryptomonnaies", matiere: "Matières premières" };
const enc = encodeURIComponent;

export default function PageMarche({ classe }: { classe: Classe }) {
  const { inst, actifs, pf, mode, envoyer, utilisateur } = useMarche();
  const router = useRouter();
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
  const [erreurMarche, setErreurMarche] = useState<string | null>(null);
  const selectionRef = useRef(selection);
  selectionRef.current = selection;

  const classes = useMemo<Classe[]>(() => (classe === "action" ? ["action", "indice"] : [classe]), [classe]);

  const lire = useCallback(async () => {
    const s = selectionRef.current, u = uniteRef.current;
    const [h, c, i] = await Promise.allSettled([
      api<ReponseBougies>(`/api/v1/bougies/${enc(s)}?unite=${u}&barres=300`),
      api<CarnetT>(`/api/v1/carnet/${enc(s)}`),
      api<Indicateurs>(`/api/v1/indicateurs/${enc(s)}?barres=30`),      // ATR journalier de l'en-tête
    ]);
    if (s === selectionRef.current && u === uniteRef.current) {
      if (h.status === "fulfilled") setDonnees(h.value);
      if (c.status === "fulfilled") setCarnet(c.value);
      if (i.status === "fulfilled") setIndic(i.value);
      const erreurs = [h, c, i].flatMap((resultat) => resultat.status === "rejected"
        ? [resultat.reason instanceof Error ? resultat.reason.message : "Lecture impossible."] : []);
      setErreurMarche(erreurs.length ? `Certaines données n'ont pas pu être actualisées; les dernières valeurs sont conservées. ${erreurs.join(" · ")}` : null);
    }
  }, []);

  useEffect(() => {
    let active = true;
    let enCours = false;
    let minuteur: number | undefined;
    const programmer = () => { minuteur = window.setTimeout(() => void executer(), 2500); };
    const executer = async () => {
      if (!active || enCours) return;
      if (document.visibilityState !== "visible") { programmer(); return; }
      enCours = true;
      try { await lire(); }
      finally {
        enCours = false;
        if (active) programmer();
      }
    };
    const retourVisible = () => {
      if (document.visibilityState === "visible" && !enCours) {
        if (minuteur !== undefined) window.clearTimeout(minuteur);
        void executer();
      }
    };
    void executer();
    document.addEventListener("visibilitychange", retourVisible);
    return () => {
      active = false;
      if (minuteur !== undefined) window.clearTimeout(minuteur);
      document.removeEventListener("visibilitychange", retourVisible);
    };
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

  const choisir = (s: string) => { setDonnees(null); setCarnet(null); setIndic(null); setErreurMarche(null); setSelection(s); };
  const changerUnite = (u: Unite) => { setDonnees(null); setErreurMarche(null); setUnite(u); };

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
  return (
    <main className="page-marche">
      <header className="marche-selection">
        <label htmlFor="classe-marche">Marché</label>
        <select id="classe-marche" value={classe} onChange={(e) => router.push(`/marche?classe=${e.target.value}`)}>
          <option value="action">Actions</option>
          <option value="crypto">Cryptomonnaies</option>
          <option value="matiere">Matières premières</option>
        </select>
      </header>
      <div className="marche-zones">
        <Marches actifs={actifs} cotations={inst?.cotations ?? []} classes={classes} selection={selection} onSelect={choisir} titre={TITRES[classe]} />
        <section className="centre">
          <div className="graphique">
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
              <p className="bandeau-pause" role="status">Simulation en pause. Lancez-la avec ▶ ou choisissez une date dans le calendrier.</p>
            )}
            {erreurMarche && <p className="bandeau erreur" role="alert">{erreurMarche}</p>}
            {bougies.length > 0
              ? <Graphique bougies={bougies} symbole={selection} unite={unite} indicateurs={donnees?.indicateurs ?? null} choix={choix}
                  niveaux={donnees?.niveaux ?? null} outils={outils} dessins={dessins} modeTrace={modeTrace} onDessin={ajouterDessin} />
              : <p className="vide">{donnees ? "Pas encore de bougies à cette date : avancez dans le temps." : "Chargement du graphique…"}</p>}
            {derniere?.en_formation && <p className="graphique-note">La dernière bougie est en cours de formation.</p>}
            {actif?.classe === "action" && (
              <p className="graphique-note">Prix ajustés des dividendes et des divisions d&apos;actions (source Yahoo Finance) : ils peuvent différer des cours affichés à l&apos;époque.</p>
            )}
          </div>
        </section>
        <aside className="droite">
          <Ticket actif={actif} cotation={cotation} pf={pf} mode={mode} onEnvoyer={envoyer} />
          <BlocRepliable titre="Avancé" aide="Outils pour aller plus loin : protections automatiques, carnet d'ordres simulé et indicateurs techniques."
            cleMemoire="marche-avance">
            <OutilsTechniques unite={unite} onUnite={changerUnite} outils={outils} onOutils={setOutils} modeTrace={modeTrace} onModeTrace={setModeTrace}
              nbDessins={dessins.length} onEffacer={effacerDessins} donnees={donnees && donnees.symbole === selection ? donnees : null} mode={mode} />
            <BarreIndicateurs choix={choix} onChange={changerChoix} mode={mode} parametres={donnees?.parametres ?? indic?.parametres ?? null} />
            <Protection actif={actif} />
            <Carnet carnet={carnet} mode={mode} />
          </BlocRepliable>
          <Link className="lien voir-portefeuille" href="/portefeuille">Voir mon portefeuille</Link>
        </aside>
      </div>
    </main>
  );
}
