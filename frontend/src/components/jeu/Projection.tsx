"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Maximize, Pause, Play, SkipForward, Volume2, VolumeX, X } from "lucide-react";
import { dateCourte, entier, nombre, pct, pctSigne } from "@/lib/format";
import SalleCanvas from "./SalleCanvas";
import { bip } from "./son";
import type { Acte, Partie } from "./types";
import type { usePartie } from "./usePartie";

type Jeu = ReturnType<typeof usePartie>;

interface Props {
  jeu: Jeu;
  son: boolean;
  basculerSon: () => void;
  quitter: () => void;
  pleinEcran: () => void;
}

const sens = (v: number) => (v > 0.00005 ? "gain" : v < -0.00005 ? "perte" : "discret");

function mesurePeur(m: NonNullable<Partie["peur_mesure"]>) {
  return m.unite === "points" ? `${m.nom} ${nombre(m.valeur, 1)}` : `BTC −${pct(m.valeur, 0)} en 30 j`;
}

export default function Projection({ jeu, son, basculerSon, quitter, pleinEcran }: Props) {
  const { partie, agir, coupure, message } = jeu;
  const [compte, setCompte] = useState(3);           // clap : 3, 2, 1, Action
  const [pause, setPause] = useState(false);
  const [choisi, setChoisi] = useState(partie.vedette);
  const [verdict, setVerdict] = useState<string | null>(null);
  const [decide, setDecide] = useState(false);
  const jury = partie.mode === "jury";
  const { arret, difficulte } = partie;
  const peutPause = difficulte.pause || jury;

  useEffect(() => {
    if (compte < 0) return;
    const t = window.setTimeout(() => {
      bip(son, compte > 1 ? 520 : 880, 0.18);
      setCompte((c) => c - 1);
    }, 700);
    return () => window.clearTimeout(t);
  }, [compte, son]);

  // l'horloge du film : une séance à la fois, demandée au serveur
  const roule = compte < 0 && !pause && !arret && !coupure && !verdict && partie.statut === "en_cours";
  const [essai, setEssai] = useState(0);
  useEffect(() => {
    if (!roule) return;
    let vivant = true;
    const t = window.setTimeout(() => {
      bip(son, 90, 0.05, 0.03);
      void agir({ nom: "avancer" }).then(() => { if (vivant) setEssai((n) => n + 1); });
    }, difficulte.ms);
    return () => { vivant = false; window.clearTimeout(t); };
  }, [roule, partie.seance, essai, difficulte.ms, agir, son]);

  // un onglet caché n'avale pas le film
  useEffect(() => {
    const cache = () => { if (document.hidden) setPause(true); };
    document.addEventListener("visibilitychange", cache);
    return () => document.removeEventListener("visibilitychange", cache);
  }, []);

  const numeroArret = arret?.numero;
  useEffect(() => {
    if (numeroArret !== undefined) bip(son, 220, 0.8, 0.08);
  }, [numeroArret, son]);

  useEffect(() => {
    if (!verdict) return;
    const t = window.setTimeout(() => setVerdict(null), 1800);
    return () => window.clearTimeout(t);
  }, [verdict]);

  const enVol = useRef(false);
  const decider = useCallback(async (acte: Acte, nom: string) => {
    if (enVol.current) return;
    enVol.current = true;
    setDecide(true);
    bip(son, 660);
    if (jury) setVerdict(nom);
    setPause(false);
    await agir({ nom: "choix", corps: { acte } });
    enVol.current = false;
    setDecide(false);
  }, [agir, jury, son]);

  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      if (document.querySelector("dialog[open]") || e.ctrlKey || e.metaKey || e.altKey) return;
      const cible = e.target as HTMLElement;
      if (["INPUT", "SELECT", "TEXTAREA"].includes(cible.tagName)) return;
      const rang = ["Digit1", "Digit2", "Digit3", "Digit4"].indexOf(e.code);
      const pave = ["Numpad1", "Numpad2", "Numpad3", "Numpad4"].indexOf(e.code);
      const k = rang >= 0 ? rang : pave;
      if (arret && k >= 0 && !e.repeat) {
        e.preventDefault();
        const o = arret.options[k];
        void decider(o.acte, o.nom);
      } else if (e.code === "Space" && cible.tagName !== "BUTTON" && !arret && compte < 0 && peutPause) {
        e.preventDefault();
        setPause((p) => !p);
      }
    };
    document.addEventListener("keydown", touche);
    return () => document.removeEventListener("keydown", touche);
  }, [arret, decider, compte, peutPause]);

  const libre = partie.liquidites - partie.engage;
  const ouvert = compte < 0 && !arret && !pause && !coupure;
  const couleurPeur = partie.peur > 66 ? "haute" : partie.peur > 33 ? "moyenne" : "basse";
  const voile = compte >= 0 ? "clap" : coupure ? "coupure" : verdict ? "verdict" : arret ? "arret" : pause ? "pause" : null;

  function ordre(rang: number, sensOrdre: "achat" | "vente") {
    bip(son, sensOrdre === "achat" ? 700 : 330);
    void agir({ nom: "ordres", corps: { rang, sens: sensOrdre } });
  }

  return (
    <div className="obscure-partie" data-voile={voile ?? undefined}>
      <header className="obscure-hud">
        <button type="button" className="obscure-icone" onClick={quitter} aria-label="Quitter la projection, elle reste en pause"><X size={18} aria-hidden="true" /></button>
        <div className="obscure-hud-titre">
          <strong>{partie.titre}</strong>
          <small>{partie.date ? dateCourte(`${partie.date}T00:00:00`) : `Séance ${partie.seance + 1}`}{jury ? ", le jury décide" : ""}</small>
        </div>
        <p className="obscure-stat">
          <small>Portefeuille de jeu</small>
          <strong>{entier(partie.valeur)} <span className={sens(partie.valeur / partie.capital - 1)}>{pctSigne(partie.valeur / partie.capital - 1, 1)}</span></strong>
        </p>
        <p className="obscure-stat obscure-option"><small>Double immobile</small><strong>{entier(partie.double)}</strong></p>
        {partie.plan && (
          <p className="obscure-stat obscure-option" data-limite={partie.baisse >= partie.plan.perte_max / 100 || undefined}>
            <small>Votre limite, {partie.plan.perte_max} %</small>
            <strong>{partie.baisse >= 0.0005 ? `−${pct(partie.baisse)}` : "0 %"}</strong>
          </p>
        )}
        <div className="obscure-peur" data-niveau={couleurPeur}>
          <small>Peur <b>{Math.round(partie.peur)}</b>{partie.peur_mesure && <span>{mesurePeur(partie.peur_mesure)}</span>}</small>
          <i aria-hidden="true"><em style={{ width: `${partie.peur}%` }} /></i>
        </div>
        <div className="obscure-commandes">
          {jury && (
            <button type="button" className="obscure-bouton" disabled={!ouvert} onClick={() => void agir({ nom: "avancer", corps: { jusqu_a_l_arret: true } })}>
              <SkipForward size={15} aria-hidden="true" /><span>Arrêt suivant</span>
            </button>
          )}
          {peutPause && (
            <button type="button" className="obscure-icone" disabled={compte >= 0 || !!arret} onClick={() => setPause((p) => !p)} aria-label={pause ? "Reprendre" : "Mettre en pause"}>
              {pause ? <Play size={17} aria-hidden="true" /> : <Pause size={17} aria-hidden="true" />}
            </button>
          )}
          <button type="button" className="obscure-icone" onClick={basculerSon} aria-pressed={son} aria-label={son ? "Couper le son" : "Activer le son"}>
            {son ? <Volume2 size={17} aria-hidden="true" /> : <VolumeX size={17} aria-hidden="true" />}
          </button>
          <button type="button" className="obscure-icone obscure-option" onClick={pleinEcran} aria-label="Plein écran"><Maximize size={17} aria-hidden="true" /></button>
        </div>
      </header>

      <div className="obscure-salle">
        <SalleCanvas actif={partie.actifs[choisi]} peur={partie.peur} />
        {!voile && <p className="obscure-sous-titre">{partie.sous_titre}</p>}
        {voile && (
          <div className="obscure-voile" aria-live="polite">
            {voile === "clap" && <div className="obscure-clap"><small>{partie.sujet}</small><strong>{compte > 0 ? compte : "Action !"}</strong></div>}
            {voile === "coupure" && <div className="obscure-clap"><small>Connexion au serveur perdue</small><b>Le film reprendra tout seul.</b></div>}
            {voile === "verdict" && <div className="obscure-clap obscure-verdict"><small>Le jury a décidé</small><strong>{verdict}</strong></div>}
            {voile === "pause" && (
              <div className="obscure-clap">
                <small>La projection est suspendue</small>
                <button type="button" className="obscure-bouton obscure-bouton-fort" onClick={() => setPause(false)}>Reprendre</button>
              </div>
            )}
            {voile === "arret" && arret && (
              <section className="obscure-dilemme" data-jury={jury || undefined} aria-label={`Arrêt sur image ${arret.numero + 1} sur 3`}>
                <small>Arrêt sur image {arret.numero + 1} sur 3{jury ? ", au jury de décider" : ""}</small>
                {arret.evenement && <p>{arret.evenement}</p>}
                <h2>{arret.question}</h2>
                <div className="obscure-choix">
                  {arret.options.map((o, k) => (
                    <button key={o.acte} type="button" data-acte={o.acte} disabled={decide} onClick={() => void decider(o.acte, o.nom)}>
                      <kbd>{k + 1}</kbd><span><strong>{o.nom}</strong><small>{o.detail}</small></span>
                    </button>
                  ))}
                </div>
                {partie.plan && arret.conseil && <p className="obscure-conseil">{arret.conseil}</p>}
                <p className="obscure-petit">Votre décision part à l’ouverture de la séance suivante.</p>
              </section>
            )}
          </div>
        )}
        {message && <p className="obscure-message" role="alert">{message}</p>}
      </div>

      <div className="obscure-pont">
        {partie.actifs.map((a) => {
          const variation = a.clotures[a.clotures.length - 1] / 100 - 1;
          return (
            <div key={a.rang} className="obscure-actif" data-choisi={choisi === a.rang || undefined}>
              <button type="button" className="obscure-actif-nom" title={a.detail ?? undefined} aria-pressed={choisi === a.rang} onClick={() => setChoisi(a.rang)}>
                <span>{a.nom}</span>
                <b className={sens(variation)}>{pctSigne(variation, 1)}</b>
                <small>{entier(a.valeur)} USD{a.en_attente.length > 0 && <i>{a.en_attente.length} ordre{a.en_attente.length > 1 ? "s" : ""} pour demain</i>}</small>
              </button>
              {!jury && (
                <>
                  <button type="button" className="obscure-achat" disabled={!ouvert || libre < 1} onClick={() => ordre(a.rang, "achat")} aria-label={`Acheter ${entier(partie.mise)} dollars de ${a.nom}`}>+ {entier(partie.mise)}</button>
                  <button type="button" className="obscure-vente" disabled={!ouvert || a.valeur < 1} onClick={() => ordre(a.rang, "vente")} aria-label={`Vendre la moitié de ${a.nom}`}>Vendre ½</button>
                </>
              )}
            </div>
          );
        })}
        <p className="obscure-liquidites"><small>Liquidités</small><strong>{entier(libre)}</strong></p>
      </div>
    </div>
  );
}
