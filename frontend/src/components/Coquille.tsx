"use client";

import { useCallback, useEffect, useState } from "react";
import Auth from "./Auth";
import BarreTemps from "./BarreTemps";
import { FournisseurMarche, useMarche } from "./Contexte";
import DialogueDates from "./DialogueDates";
import DialogueDirect from "./DialogueDirect";
import Entete from "./Entete";
import MenuLateral from "./MenuLateral";
import PanneauSuivis from "./PanneauSuivis";
import Recherche from "./Recherche";
import { PanneauXAI } from "./xai/Assistant";
import { FournisseurXAI } from "./xai/ContexteXAI";
import { deconnexion, enregistrerSurDeconnexion, restaurerSession } from "@/lib/api";
import { dateCourte, dateLongue } from "@/lib/format";
import { OUVRIR_DATES_EVENT, OUVRIR_DIRECT_EVENT, useInstantLisse } from "@/lib/temps";
import type { Utilisateur } from "@/lib/types";

function Bandeaux() {
  const { inst, erreurReseau, derniereReussiteMarche, derniereReussiteCompte } = useMarche();
  const heure = (instant: string | null) => instant ? new Date(instant).toLocaleTimeString("fr-FR") : "aucune lecture réussie";
  return (
    <div className="bandeaux">
      {erreurReseau && <p className="bandeau erreur" role="alert">
        Données possiblement obsolètes, nouvel essai automatique. Marché : {heure(derniereReussiteMarche)} ; portefeuille : {heure(derniereReussiteCompte)}. {erreurReseau}
      </p>}
      {inst?.synthetiques && (
        <p className="bandeau avertissement" role="note">
          Données de démonstration générées au hasard : ce ne sont pas de vrais prix. Pour les vraies données, lancez <code>python -m pipeline tout</code>.
        </p>
      )}
      {inst?.direct && (
        <p className="bandeau avertissement" role="status">
          {inst.direct_flux?.demo
            ? "Direct, FLUX DE DÉMONSTRATION : les prix sont inventés, ce ne sont pas de vrais cours."
            : "Direct en lecture seule : prix Yahoo Finance, souvent différés d'environ 15 minutes."}
          {inst.instant_compte && ` Votre portefeuille reste figé au ${dateCourte(inst.instant_compte)}.`}
          {inst.direct_flux?.age_secondes != null && ` Dernière mise à jour il y a ${inst.direct_flux.age_secondes} s.`}
          {inst.direct_flux?.erreur && ` Flux momentanément indisponible, derniers prix conservés (${inst.direct_flux.erreur}).`}
        </p>
      )}
      {inst?.termine && (
        <p className="bandeau info" role="status">
          La période rejouée est terminée ({dateLongue(inst.instant)}). Consultez votre bilan, recommencez à une autre date, ou passez en Direct.
        </p>
      )}
    </div>
  );
}

function Interieur({ children }: { children: React.ReactNode }) {
  const { inst, mode } = useMarche();
  const instant = useInstantLisse(inst);
  const [recherche, setRecherche] = useState(false);
  const [suivis, setSuivis] = useState(false);
  const [fenetre, setFenetre] = useState<"dates" | "direct" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const fermer = useCallback(() => setFenetre(null), []);
  const sansDonnees = inst !== null && inst.cotations.length === 0;

  // Ctrl+K (ou Cmd+K) et « / » ouvrent la recherche, sauf pendant la saisie ou sous une fenêtre ouverte.
  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      if (document.querySelector("dialog[open]")) return;
      const cible = e.target as HTMLElement | null;
      const saisie = cible && (cible.tagName === "INPUT" || cible.tagName === "TEXTAREA" || cible.tagName === "SELECT" || cible.isContentEditable);
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setRecherche(true); }
      else if (e.key === "/" && !saisie) { e.preventDefault(); setRecherche(true); }
    };
    document.addEventListener("keydown", touche);
    return () => document.removeEventListener("keydown", touche);
  }, []);

  useEffect(() => {
    const dates = () => setFenetre("dates");
    const direct = () => setFenetre("direct");
    window.addEventListener(OUVRIR_DATES_EVENT, dates);
    window.addEventListener(OUVRIR_DIRECT_EVENT, direct);
    return () => { window.removeEventListener(OUVRIR_DATES_EVENT, dates); window.removeEventListener(OUVRIR_DIRECT_EVENT, direct); };
  }, []);

  useEffect(() => {
    if (!message) return;
    const t = window.setTimeout(() => setMessage(null), 7000);
    return () => window.clearTimeout(t);
  }, [message]);

  return (
    <div className="seance-app" data-mode={mode}>
      <MenuLateral />
      <Entete instant={instant} ouvrirRecherche={() => setRecherche(true)} suivisOuverts={suivis} basculerSuivis={() => setSuivis((v) => !v)} signaler={setMessage} />
      <div className="seance-scene">
        <div className="seance-colonne">
          <Bandeaux />
          <div className="contenu seance-contenu">
            {sansDonnees ? (
              <main className="espace-vide">
                <h1>Aucune donnée de marché</h1>
                <p>Le serveur n&apos;a pas encore de prix à rejouer. Dans le dossier <code>backend</code>, lancez :</p>
                <pre>python -m pipeline tout</pre>
                <p>Cette commande télécharge les prix, les nettoie et prépare le simulateur. Rechargez ensuite cette page.</p>
              </main>
            ) : children}
          </div>
        </div>
        {suivis && <PanneauSuivis fermer={() => setSuivis(false)} />}
      </div>
      <BarreTemps instant={instant} signaler={setMessage} />
      <PanneauXAI />
      <Recherche ouverte={recherche} fermer={() => setRecherche(false)} />
      {fenetre === "dates" && <DialogueDates fermer={fermer} />}
      {fenetre === "direct" && <DialogueDirect fermer={fermer} />}
      {message && <p className="seance-message" role="alert">{message}</p>}
    </div>
  );
}

export default function Coquille({ children }: { children: React.ReactNode }) {
  const [utilisateur, setUtilisateur] = useState<Utilisateur | null>(null);
  const [pret, setPret] = useState(false);

  useEffect(() => {
    enregistrerSurDeconnexion(() => setUtilisateur(null));
    restaurerSession().then((u) => { setUtilisateur(u); setPret(true); });
  }, []);

  if (!pret) return <p className="chargement" role="status">Chargement…</p>;
  if (!utilisateur) return <Auth onConnecte={setUtilisateur} />;
  return (
    <FournisseurMarche
      utilisateur={utilisateur}
      majUtilisateur={setUtilisateur}
      deconnecter={async () => { await deconnexion(); setUtilisateur(null); }}
    >
      <FournisseurXAI>
        <Interieur>{children}</Interieur>
      </FournisseurXAI>
    </FournisseurMarche>
  );
}
