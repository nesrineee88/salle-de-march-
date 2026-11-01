"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { prix, variation } from "@/lib/format";
import { AIDE, enregistrerChoix, lireChoix } from "@/lib/indicateurs";
import type { Barre, Carnet as CarnetT, CleIndicateur, Classe, Indicateurs } from "@/lib/types";
import BarreIndicateurs from "./BarreIndicateurs";
import Bas from "./Bas";
import Carnet from "./Carnet";
import { useMarche } from "./Contexte";
import Graphique from "./Graphique";
import Marches from "./Marches";
import Protection from "./Protection";
import Ticket from "./Ticket";

const DEFAUT: Record<string, string> = { action: "AAPL", crypto: "BTC-USD", matiere: "GC=F" };
const TITRES: Record<string, string> = { action: "Actions", crypto: "Cryptomonnaies", matiere: "Matières premières" };
const enc = encodeURIComponent;

export default function PageMarche({ classe }: { classe: Classe }) {
  const { inst, actifs, pf, ordres, execs, mode, envoyer, annuler } = useMarche();
  const [selection, setSelection] = useState<string>(DEFAUT[classe]);
  const [barres, setBarres] = useState<Barre[]>([]);
  const [carnet, setCarnet] = useState<CarnetT | null>(null);
  const [indic, setIndic] = useState<Indicateurs | null>(null);
  const [choix, setChoix] = useState<CleIndicateur[]>([]);
  const selectionRef = useRef(selection);
  selectionRef.current = selection;

  const classes = useMemo<Classe[]>(() => (classe === "action" ? ["action", "indice"] : [classe]), [classe]);

  const lire = useCallback(async () => {
    const s = selectionRef.current;
    const [h, c, i] = await Promise.all([
      api<Barre[]>(`/api/v1/historique/${enc(s)}?barres=300`).catch(() => [] as Barre[]),
      api<CarnetT>(`/api/v1/carnet/${enc(s)}`).catch(() => null),
      api<Indicateurs>(`/api/v1/indicateurs/${enc(s)}?barres=300`).catch(() => null),
    ]);
    if (s === selectionRef.current) { setBarres(h); setCarnet(c); setIndic(i); }
  }, []);

  useEffect(() => {
    void lire();
    const t = setInterval(() => { if (document.visibilityState === "visible") void lire(); }, 2500);
    return () => clearInterval(t);
  }, [lire, selection]);

  // si le symbole par défaut n'a pas de données, on prend le premier disponible du marché
  useEffect(() => {
    if (!inst) return;
    const dispo = inst.cotations.filter((c) => classes.includes(actifs.find((a) => a.symbole === c.symbole)?.classe as Classe));
    if (dispo.length > 0 && !dispo.some((c) => c.symbole === selection)) setSelection(dispo[0].symbole);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inst, actifs, classe]);

  useEffect(() => { setChoix(lireChoix()); }, []);
  const changerChoix = (c: CleIndicateur[]) => { setChoix(c); enregistrerChoix(c); };

  const choisir = (s: string) => { setBarres([]); setCarnet(null); setIndic(null); setSelection(s); };

  const actif = actifs.find((a) => a.symbole === selection);
  const cotation = inst?.cotations.find((c) => c.symbole === selection);
  const base = cotation?.reference ?? cotation?.derniere_cloture ?? null;
  const v = cotation && base ? (cotation.prix - base) / Math.abs(base) : null;
  const derniere = barres[barres.length - 1];
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
              </>
            ) : <h1>Choisissez un actif</h1>}
          </div>
          {inst?.horloge.en_pause && !inst.termine && (
            <p className="bandeau-pause" role="status">La simulation est à l&apos;arrêt. Appuyez sur « Lancer », ou choisissez une date sur la frise.</p>
          )}
          <BarreIndicateurs choix={choix} onChange={changerChoix} mode={mode} parametres={indic?.parametres ?? null} />
          {barres.length > 0 ? <Graphique barres={barres} symbole={selection} indicateurs={indic} choix={choix} /> : <p className="vide">Pas encore de bougies à cette date : avancez dans le temps.</p>}
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
