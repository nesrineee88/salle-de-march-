"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { symboleCourt } from "@/lib/actif";
import { dateCourte, entier, montantSigne, nombre, pctSigne, signe } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import { ouvrirDates } from "@/lib/temps";
import type { HistoriqueValeur, SyntheseTableau } from "@/lib/types";
import { useMarche } from "./Contexte";
import { ASurveiller, ContreReference, Mouvements, Positions, References, Repartition, Risque, sens } from "./dashboard/Blocs";
import CourbeValeur from "./dashboard/CourbeValeur";
import Explication, { Info, type Sujet } from "./dashboard/Explication";

const PERIODES = [
  { cle: "1m", libelle: "1 M", jours: 31 },
  { cle: "3m", libelle: "3 M", jours: 92 },
  { cle: "6m", libelle: "6 M", jours: 183 },
  { cle: "tout", libelle: "Depuis le début", jours: Infinity },
] as const;
type Periode = (typeof PERIODES)[number]["cle"];

const CLE_REFERENCE = "sdm.reference";
const montantRond = (v: number) => `${signe(Math.abs(v) < 0.5 ? 0 : v)}${entier(Math.abs(v))}`;

export default function TableauDeBord() {
  const { utilisateur, inst, actifs, pf, ordres, execs } = useMarche();
  const [choix, setChoix] = useState<string | null>(null);
  const [periode, setPeriode] = useState<Periode>("tout");
  const [sujet, setSujet] = useState<Sujet | null>(null);

  useEffect(() => {
    try { setChoix(localStorage.getItem(CLE_REFERENCE)); } catch { /* stockage indisponible */ }
  }, []);

  // Synthèse calculée côté serveur (rendement, références, risque) : jamais recalculée ici.
  const { donnees: synthese, erreur, relire } = useLecture<SyntheseTableau>("/api/v1/tableau-de-bord", 6000);
  const references = synthese?.suivi?.references ?? [];
  const reference = references.find((r) => r.symbole === choix) ?? references[0];
  const chemin = `/api/v1/portefeuille/historique${reference ? `?reference=${encodeURIComponent(reference.symbole)}` : ""}`;
  const { donnees: hist, relire: relireHist } = useLecture<HistoriqueValeur>(chemin, 6000);

  // Après un saut de date, un ordre ou un changement de régime : relecture immédiate.
  const jour = inst?.instant.slice(0, 10);
  const direct = inst?.direct ?? false;
  useEffect(() => {
    if (!jour) return;
    void relire(); void relireHist();
  }, [jour, direct, execs.length, relire, relireHist]);

  const parSymbole = useMemo(() => new Map(actifs.map((a) => [a.symbole, a])), [actifs]);
  const points = useMemo(() => {
    const tous = hist?.points ?? [];
    const p = PERIODES.find((x) => x.cle === periode)!;
    if (tous.length === 0 || p.jours === Infinity) return tous;
    const seuil = Date.parse(tous[tous.length - 1].jour) - p.jours * 86_400_000;
    return tous.filter((x) => Date.parse(x.jour) >= seuil);
  }, [hist, periode]);

  if (synthese && !synthese.suivi) {
    return (
      <main className="dash">
        <p className="seance-note" role="alert">Le serveur Python utilise encore l’ancienne version. Arrêtez-le, relancez-le, puis rechargez cette page.</p>
      </main>
    );
  }
  if (!synthese || !pf) {
    return <main className="dash">{erreur ? <p className="erreur" role="alert">{erreur}</p> : <p className="chargement" role="status">Chargement du dashboard…</p>}</main>;
  }

  const { suivi, niveau_risque, risque } = synthese;
  const pire = [...pf.positions].sort((a, b) => a.pnl_latent - b.pnl_latent)[0];
  const ecart = reference?.ecart_points ?? null;
  const nomRef = (reference?.nom ?? "Référence").replace(/ /g, "\u00a0");
  const reserve = pf.cash - pf.cash_disponible;

  function choisir(symbole: string) {
    setChoix(symbole);
    try { localStorage.setItem(CLE_REFERENCE, symbole); } catch { /* le choix ne sera pas mémorisé */ }
  }

  return (
    <main className="dash">
      <h1 className="sr-only">Dashboard de {utilisateur.nom}</h1>

      {reference && <References references={references} choix={reference} choisir={choisir} />}

      {suivi.operations_futures && (
        <div className="seance-note seance-note-action" role="note">
          <p>Ce portefeuille contient des opérations postérieures à la date affichée, héritées des anciennes règles (retour en arrière, ordres en Direct). Ses chiffres ne sont pas fiables : recommencez à une date.</p>
          <button type="button" className="btn" onClick={ouvrirDates}>Recommencer</button>
        </div>
      )}

      <section className="dash-hero">
        <div className="dash-recit">
          <p className="discret">Votre portefeuille, au {dateCourte(synthese.instant)}</p>
          <p className="dash-valeur">{entier(suivi.valeur)}<small>USD <Info sujet="valeur" ouvrir={setSujet} /></small></p>
          <div className="dash-retour">
            <small>Total return depuis le début <Info sujet="retour" ouvrir={setSujet} /></small>
            <strong className={sens(suivi.rendement_total)}>
              <span aria-hidden="true">{sens(suivi.rendement_total) === "gain" ? "▲ " : sens(suivi.rendement_total) === "perte" ? "▼ " : ""}</span>
              {pctSigne(suivi.rendement_total)}
            </strong>
            <span>{suivi.a_commence ? `${montantRond(suivi.gain)} USD, depuis le ${dateCourte(suivi.debut)}` : "Il démarre à votre première transaction"}</span>
          </div>
          {suivi.a_commence ? (
            <p className="dash-phrase">
              {ecart === null ? null : Math.abs(ecart) < 0.05 ? <>Vous faites jeu égal avec {nomRef}. </> : (
                <>Vous faites <strong>{nombre(Math.abs(ecart), 1)} points {ecart > 0 ? "de mieux" : "de moins"}</strong> que {nomRef}. </>
              )}
              {pire && pire.pnl_latent < -0.5 && (
                <>{parSymbole.get(pire.symbole)?.nom ?? symboleCourt(pire.symbole)} est votre plus grosse perte : <strong>{montantRond(pire.pnl_latent)} USD</strong>.</>
              )}
            </p>
          ) : (
            <ol className="dash-depart">
              <li>Choisissez la date en haut de l’écran.</li>
              <li>Achetez un premier actif.</li>
              <li>Lancez le temps avec le bouton ▶ en bas.</li>
            </ol>
          )}
          <div className="dash-actions">
            <Link className="btn btn-principal" href="/marche">Passer un ordre</Link>
            {utilisateur.profil_risque
              ? <button type="button" className="btn" onClick={ouvrirDates}>Changer la date</button>
              : <Link className="btn" href="/compte#profil">Mon profil</Link>}
          </div>
        </div>
        <div className="dash-hero-courbe">
          <div className="dash-tete">
            <p className="dash-cle">
              <span><i className="cle-vous" />Votre portefeuille</span>
              <span><i className="cle-reference" />{nomRef}{reference?.dividendes ? ", dividendes inclus" : ""}, même départ</span>
            </p>
            <div className="seance-segments" role="group" aria-label="Période">
              {PERIODES.map((p) => <button key={p.cle} type="button" aria-pressed={periode === p.cle} onClick={() => setPeriode(p.cle)}>{p.libelle}</button>)}
            </div>
          </div>
          <CourbeValeur points={points} nomReference={nomRef} futur={!direct} />
        </div>
      </section>

      <dl className="dash-faits">
        <div>
          <dt>Résultat du jour</dt>
          <dd className={sens(Math.round(suivi.resultat_jour))}>{montantRond(suivi.resultat_jour)}</dd>
          <dd className="dash-fait-detail">USD, depuis hier soir</dd>
        </div>
        <div>
          <dt>Disponible</dt>
          <dd>{entier(pf.cash_disponible)}</dd>
          <dd className="dash-fait-detail">{reserve > 0.5 ? `${entier(reserve)} réservés par vos ordres` : "USD à investir"}</dd>
        </div>
        <div>
          <dt>{nomRef}, depuis le début</dt>
          <dd className={sens(reference?.depuis_debut)}>{suivi.a_commence ? pctSigne(reference?.depuis_debut) : "–"}</dd>
          <dd className="dash-fait-detail">{ecart !== null && suivi.a_commence ? `Écart : ${montantSigne(ecart)} points` : "Mêmes dates que vous"}</dd>
        </div>
        <div>
          <dt>Perte d’un mauvais jour <Info sujet="var" ouvrir={setSujet} /></dt>
          <dd>{risque ? entier(risque.var_montant) : "–"}</dd>
          <dd className="dash-fait-detail">USD, 1 jour sur 20</dd>
        </div>
      </dl>

      <div className="dash-grille">
        <section className="dash-panneau dash-c7">
          <header className="dash-tete">
            <h2>Niveau de risque <Info sujet="risque" ouvrir={setSujet} /></h2>
            <button type="button" className="btn btn-mini" onClick={() => setSujet("risque")}>Voir le calcul</button>
          </header>
          <Risque risque={niveau_risque} />
        </section>

        <section className="dash-panneau dash-c5">
          <header className="dash-tete"><h2>Vous contre la référence</h2></header>
          {suivi.a_commence && reference
            ? <ContreReference suivi={suivi} reference={reference} pireBaisse={synthese.performance.drawdown_max} />
            : <p className="dash-vide">La comparaison démarre à votre première transaction, le même jour pour vous et pour l’indice.</p>}
        </section>

        <section className="dash-panneau dash-c5">
          <header className="dash-tete"><h2>Vos positions</h2><Link className="btn btn-mini" href="/portefeuille">Tout voir</Link></header>
          <Positions pf={pf} parSymbole={parSymbole} />
        </section>

        <section className="dash-panneau dash-c4">
          <header className="dash-tete"><h2>À surveiller</h2></header>
          <ASurveiller synthese={synthese} ordres={ordres} pf={pf} />
        </section>

        <section className="dash-panneau dash-c3">
          <header className="dash-tete"><h2>Répartition</h2></header>
          <Repartition lignes={synthese.repartition_detail.marche} />
        </section>

        <section className="dash-panneau dash-c12">
          <header className="dash-tete"><h2>Le marché aujourd’hui</h2><Link className="btn btn-mini" href="/marche">Ouvrir la salle</Link></header>
          <Mouvements lignes={synthese.mouvements} />
        </section>
      </div>

      {sujet && <Explication sujet={sujet} synthese={synthese} cash={pf.cash} fermer={() => setSujet(null)} />}
    </main>
  );
}
