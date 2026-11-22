"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ErreurApi, api } from "@/lib/api";
import { dateCourte, entier, pct } from "@/lib/format";
import { useMarche } from "../Contexte";
import BlocRepliable from "../ui/BlocRepliable";
import { ContenuActuariat } from "../PageActuariat";

interface Pire {
  debut: string; fin: string; perte: number; sans_protection: number; avec_stop: number; stop_declenche: boolean;
  avec_assurance: number | null; indemnite: number; positions: number; positions_en_baisse: number;
}
interface Devis {
  vide: boolean; instant: string; noms: Record<string, string>;
  capital: number; franchise: number; plafond: number; jours: number;
  periodes: number; periodes_sans_chevauchement: number; premiere_date: string; derniere_date: string;
  sinistres: number; tarifable: boolean; frequence: number;
  cout_moyen: number | null; prime_pure: number | null; marge: number | null; frais: number | null; prime: number | null;
  volatilite: number; prix_bourse: number; pire: Pire;
}

const PERIMETRES = [["portefeuille", "Tout le portefeuille"], ["actions", "Actions"], ["crypto", "Crypto"], ["matieres", "Matières"]] as const;
const DUREES = [[30, "1 mois"], [91, "3 mois"], [182, "6 mois"]] as const;
const usd = (n: number) => `${entier(n)} USD`;
const usdSigne = (n: number) => `${n < -0.5 ? "−" : n > 0.5 ? "+" : ""}${entier(Math.abs(n))} USD`;
const jour = (iso: string) => dateCourte(`${iso}T12:00:00`);

function Barre({ nom, valeur, max, detail }: { nom: string; valeur: number; max: number; detail?: string }) {
  return (
    <li>
      <span>{nom}{detail && <small>{detail}</small>}</span>
      <strong className={valeur < -0.5 ? "perte" : valeur > 0.5 ? "gain" : undefined}>{usdSigne(valeur)}</strong>
      <i aria-hidden="true"><em data-sens={valeur < 0 ? "perte" : "gain"} style={{ width: `${Math.min(100, (Math.abs(valeur) / (max || 1)) * 100)}%` }} /></i>
    </li>
  );
}

function Curseur({ nom, valeur, min, max, changer }: { nom: string; valeur: number; min: number; max: number; changer: (v: number) => void }) {
  return (
    <label className="protege-curseur">
      <span>{nom}<strong>{valeur} %</strong></span>
      <input type="range" min={min} max={max} step={1} value={valeur} onChange={(e) => changer(Number(e.target.value))} />
    </label>
  );
}

export default function PageProtection() {
  const { inst } = useMarche();
  const [perimetre, setPerimetre] = useState<string>("portefeuille");
  const [franchise, setFranchise] = useState(10);
  const [plafond, setPlafond] = useState(25);
  const [jours, setJours] = useState<number>(91);
  const [devis, setDevis] = useState<Devis | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [calcul, setCalcul] = useState(false);
  const jourCompte = (inst?.instant_compte ?? inst?.instant)?.slice(0, 10);

  useEffect(() => {
    let actif = true;
    setCalcul(true);
    const t = window.setTimeout(() => {
      api<Devis>(`/api/v1/protection/devis?perimetre=${perimetre}&franchise=${franchise / 100}&plafond=${plafond / 100}&jours=${jours}`)
        .then((d) => { if (actif) { setDevis(d); setErreur(null); } })
        .catch((e) => {
          if (!actif) return;
          setDevis(null);
          setErreur(e instanceof ErreurApi && e.statut === 404 ? "Le serveur Python ne connaît pas encore cette page : redémarrez-le."
            : e instanceof Error ? e.message : "Calcul impossible.");
        })
        .finally(() => { if (actif) setCalcul(false); });
    }, 250);
    return () => { actif = false; window.clearTimeout(t); };
  }, [perimetre, franchise, plafond, jours, jourCompte]);

  const d = devis && !devis.vide ? devis : null;
  const exemple = d ? Math.round(d.capital * 0.18) : 0;

  return (
    <main className="protege">
      <header className="protege-tete">
        <div>
          <h1>Protéger mon portefeuille</h1>
          <p>Combien coûte une protection contre une forte baisse, et est-ce qu’elle aurait servi ? Calculé sur vos positions et les vrais cours passés.</p>
        </div>
        <span className="seance-tag" data-ton="alerte">Devis : rien n’est débité</span>
      </header>

      <section className="protege-reglages" aria-label="Votre contrat">
        <div className="seance-segments" role="group" aria-label="Ce qui est protégé">
          {PERIMETRES.map(([cle, nom]) => <button key={cle} type="button" aria-pressed={perimetre === cle} onClick={() => setPerimetre(cle)}>{nom}</button>)}
        </div>
        <Curseur nom="Franchise : perte à votre charge" valeur={franchise} min={2} max={30} changer={setFranchise} />
        <Curseur nom="Plafond : indemnité maximale" valeur={plafond} min={5} max={50} changer={setPlafond} />
        <div className="seance-segments" role="group" aria-label="Durée">
          {DUREES.map(([n, nom]) => <button key={n} type="button" aria-pressed={jours === n} onClick={() => setJours(n)}>{nom}</button>)}
        </div>
      </section>

      {erreur && <p className="protege-alerte" role="alert">{erreur}</p>}
      {!erreur && !devis && <p className="protege-vide" role="status">Calcul sur les cours passés…</p>}
      {devis?.vide && (
        <div className="protege-vide">
          <p>Rien à protéger dans cette catégorie : vous n’y avez aucune position.</p>
          <Link className="btn btn-principal" href="/marche">Choisir un actif</Link>
        </div>
      )}

      {d && (
        <div className="protege-grille" aria-busy={calcul}>
          <section className="protege-carte protege-prix">
            <p className="protege-sur">Protéger {usd(d.capital)} pendant {DUREES.find(([n]) => n === d.jours)?.[1]}</p>
            {d.tarifable && d.prime !== null ? (
              <>
                <p className="protege-montant">{usd(d.prime)}</p>
                <p className="protege-sous">soit {pct(d.prime / d.capital, 2)} du capital protégé</p>
              </>
            ) : (
              <>
                <p className="protege-montant protege-non">Non tarifable</p>
                <p className="protege-sous">Aucune perte de plus de {franchise} % en {d.periodes} périodes passées : un prix serait inventé.</p>
              </>
            )}
            <p className="protege-regle">
              Vous êtes payé si la perte dépasse <strong>{franchise} %</strong>, au plus <strong>{plafond} %</strong>.
              Exemple : une baisse de 18 %, soit {usd(exemple)}, rapporte <strong>{usd(Math.round(d.capital * Math.min(plafond / 100, Math.max(0, 0.18 - franchise / 100))))}</strong>.
            </p>
          </section>

          <section className="protege-carte">
            <h2>Le calcul de l’assureur</h2>
            {d.tarifable && d.prime !== null && d.prime_pure !== null && d.cout_moyen !== null && d.marge !== null && d.frais !== null ? (
              <ol className="protege-calcul">
                <li><span>Fréquence</span><b>{d.sinistres} sinistres / {d.periodes} périodes = {pct(d.frequence, 1)}</b></li>
                <li><span>Coût moyen d’un sinistre</span><b>{usd(d.cout_moyen)}</b></li>
                <li><span>Prime pure = fréquence × coût</span><b>{usd(d.prime_pure)}</b></li>
                <li><span>+ marge de sécurité (20 %)</span><b>{usd(d.marge)}</b></li>
                <li><span>+ frais (15 % de la prime)</span><b>{usd(d.frais)}</b></li>
                <li className="protege-total"><span>Prime à payer</span><b>{usd(d.prime)}</b></li>
              </ol>
            ) : (
              <p className="protege-texte">Sur {d.periodes} périodes, aucune n’a dépassé la franchise. Un assureur n’a aucun sinistre pour fixer un prix.</p>
            )}
            <p className="protege-petit">
              Le contrat est rejoué sur chaque période passée de même durée, du {jour(d.premiere_date)} au {jour(d.derniere_date)}, avec vos positions d’aujourd’hui.
              Ces périodes se chevauchent : seulement {d.periodes_sans_chevauchement} sont vraiment indépendantes.
            </p>
          </section>

          <section className="protege-carte">
            <h2>La même protection en bourse</h2>
            <p className="protege-montant protege-moyen">{usd(d.prix_bourse)}</p>
            <p className="protege-texte">
              L’indemnité est exactement celle d’une option de vente achetée à {100 - franchise} % et d’une autre vendue à {Math.max(0, 100 - franchise - plafond)} %.
              Son prix (Black-Scholes) dépend de la volatilité récente du panier : {pct(d.volatilite, 1)} par an.
            </p>
            <p className="protege-petit">
              {d.tarifable && d.prime !== null
                ? d.prix_bourse > d.prime ? "La bourse demande plus : elle regarde l’agitation actuelle, l’assureur regarde six ans de passé." : "L’assureur demande plus : son passé contient des chutes que l’agitation actuelle ne montre pas."
                : "C’est le prix de référence quand le passé ne permet pas de tarifer."}
            </p>
          </section>

          <section className="protege-carte protege-large">
            <h2>Votre pire période réelle : du {jour(d.pire.debut)} au {jour(d.pire.fin)}</h2>
            <ul className="protege-barres">
              <Barre nom="Sans protection" valeur={d.pire.sans_protection} max={d.pire.perte} />
              <Barre nom="Avec un stop-loss au seuil de la franchise" valeur={d.pire.avec_stop}
                max={d.pire.perte} detail={d.pire.stop_declenche ? "vendu à la clôture du jour où le seuil est franchi" : "le seuil n’a pas été atteint"} />
              {d.pire.avec_assurance !== null && (
                <Barre nom="Avec la protection, prime payée" valeur={d.pire.avec_assurance} max={d.pire.perte} detail={`indemnité : ${usd(d.pire.indemnite)}`} />
              )}
            </ul>
            <p className="protege-petit">Le stop-loss est gratuit mais vend au premier creux : vous ratez la remontée. La protection coûte une prime, mais vous gardez vos positions.</p>
          </section>

          <section className="protege-carte protege-large protege-lecon">
            <h2>Pourquoi aucun assureur ne vend ce contrat</h2>
            <p>
              Pendant votre pire période, <strong>{d.pire.positions_en_baisse} positions sur {d.pire.positions}</strong> ont baissé en même temps.
              Une assurance auto marche parce que les accidents sont rares et indépendants. Un krach frappe tous les clients le même jour : l’assureur ferait faillite.
              Dans la réalité, on se protège en bourse, avec des options de vente.
            </p>
          </section>
        </div>
      )}

      <p className="protege-petit protege-limites">
        Limites : le passé ne contient pas le prochain krach ; poids fixes ; un seul paiement à l’échéance ; taux sans risque nul ; ce n’est ni un produit réel ni un conseil.
      </p>

      <BlocRepliable titre="Actuariat classique : assurance auto et provisions" aide="L’exemple de cours des assureurs, sur des contrats inventés si le jeu de données public n’est pas installé.">
        <ContenuActuariat />
      </BlocRepliable>
    </main>
  );
}
