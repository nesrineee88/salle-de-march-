"use client";

import Link from "next/link";
import { useMemo } from "react";
import { dateCourte, dateHeure, nombre, pct, prix, quantite } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import type { Actualite, CritereRisque, Execution, NiveauRisque, RegleDeclenchee, SyntheseTableau } from "@/lib/types";
import type { Mode } from "./Contexte";

const NOMS_NIVEAU: Record<Exclude<NiveauRisque, "aucun">, string> = { faible: "Faible", modere: "Modéré", eleve: "Élevé" };
const RESUME_NIVEAU: Record<NiveauRisque, string> = {
  aucun: "Tout est en liquidités : le portefeuille n'est exposé à aucun marché pour l'instant.",
  faible: "Selon nos critères pédagogiques, le portefeuille paraît peu exposé en ce moment.",
  modere: "Au moins un critère mérite votre attention : regardez le détail ci-dessous.",
  eleve: "Au moins un critère est au-dessus du seuil élevé : le portefeuille pourrait subir une perte importante.",
};
const CLASSE_RANG = ["alerte-info", "alerte-attention", "alerte-danger"] as const;
const ICONE_RANG = ["i", "!", "!!"] as const;
const NOMS_REGLE: Record<string, string> = {
  stop_loss: "Stop-loss", take_profit: "Prise de profit", stop_suiveur: "Stop suiveur", achat_complementaire: "Achat complémentaire",
};

/** Phrase d'un critère : simple en mode Apprenant, chiffrée avec ses seuils en mode Trader. Toujours au conditionnel. */
function texteCritere(c: CritereRisque, mode: Mode): string {
  const pro = mode === "trader";
  switch (c.critere) {
    case "var":
      return pro
        ? `VaR historique 95 % à 1 jour : ${pct(c.valeur, 2)} de la valeur totale (seuils : 1 % et 2,5 %).`
        : `Lors d'une mauvaise journée (1 sur 20), le portefeuille pourrait perdre environ ${pct(c.valeur, 1)} de sa valeur, d'après son passé.`;
    case "concentration_position":
      if (pro) return `Plus grosse position : ${c.libelle}, ${pct(c.valeur, 1)} de la valeur totale (seuils : 25 % et 50 %).`;
      return c.rang > 0
        ? `${c.libelle} pèse ${pct(c.valeur, 0)} du portefeuille : une mauvaise nouvelle sur cet actif pourrait peser lourd.`
        : `Aucune ligne ne dépasse 25 % du portefeuille (la plus grosse : ${c.libelle}, ${pct(c.valeur, 0)}).`;
    case "concentration_secteur":
      if (pro) return `Plus gros secteur : ${c.libelle}, ${pct(c.valeur, 1)} de la valeur totale (seuils : 40 % et 60 %).`;
      return c.rang > 0
        ? `Le secteur ${c.libelle} pèse ${pct(c.valeur, 0)} : une crise dans ce secteur pourrait toucher une grande partie du portefeuille.`
        : `Aucun secteur ne dépasse 40 % du portefeuille (le plus gros : ${c.libelle}, ${pct(c.valeur, 0)}).`;
    case "profil": {
      const tol = pct(c.tolerance, 0);
      if (c.rang === 2) return `La baisse actuelle (${pct(c.valeur, 1)}) dépasse la perte que vous avez déclaré accepter (${tol}).`;
      if (c.rang === 1) return `La baisse actuelle (${pct(c.valeur, 1)}) approche la perte que vous acceptez (${tol}).`;
      return `La baisse actuelle reste dans la perte que vous acceptez (${tol}).`;
    }
    case "baisse":
      return pro
        ? `Baisse depuis le plus haut de la courbe de valeur : ${pct(c.valeur, 1)} (seuils : 10 % et 20 %).`
        : c.valeur > 0
          ? `Le portefeuille est ${pct(c.valeur, 1)} sous son plus haut.`
          : "Le portefeuille est à son plus haut.";
  }
}

export function PanneauRisque({ synthese, erreur, mode }: { synthese: SyntheseTableau | null; erreur: string | null; mode: Mode }) {
  const tete = <header className="panneau-tete"><h2 id="titre-niveau-risque">Niveau de risque</h2><Link href="/portefeuille" className="lien-discret">Détail des indicateurs →</Link></header>;
  if (!synthese) {
    return <section className="panneau" aria-labelledby="titre-niveau-risque">{tete}{erreur ? <p className="erreur" role="alert">{erreur}</p> : <p className="chargement">Calcul du niveau de risque…</p>}</section>;
  }
  const { niveau, criteres, part_investie } = synthese.niveau_risque;
  return (
    <section className="panneau" aria-labelledby="titre-niveau-risque">
      {tete}
      <ol className="niveau-risque" aria-label={niveau === "aucun" ? "Niveau de risque : aucune position" : `Niveau de risque : ${NOMS_NIVEAU[niveau]}`}>
        {(["faible", "modere", "eleve"] as const).map((n) => (
          <li key={n} data-niveau={n} data-actif={niveau === n} aria-current={niveau === n ? "true" : undefined}>{NOMS_NIVEAU[n]}</li>
        ))}
      </ol>
      <p>{RESUME_NIVEAU[niveau]}</p>
      {niveau !== "aucun" && (
        <>
          <p className="aide">Partie investie : {pct(part_investie, 0)} de la valeur totale. Le niveau retenu est celui du critère le plus inquiétant.</p>
          <ul className="alertes-risque">
            {criteres.map((c) => (
              <li key={c.critere} className={`alerte ${CLASSE_RANG[c.rang]}`}>
                <span className="alerte-icone" aria-hidden="true">{ICONE_RANG[c.rang]}</span>
                <span>{texteCritere(c, mode)}</span>
              </li>
            ))}
          </ul>
          {mode === "trader" && synthese.risque && (
            <p className="aide">VaR 95 % à 1 jour : {nombre(synthese.risque.var_montant, 2)} USD · CVaR : {nombre(synthese.risque.cvar_montant, 2)} USD, sur {synthese.risque.jours} jours d&apos;historique.</p>
          )}
        </>
      )}
      <p className="aide">Seuils pédagogiques, non réglementaires. Ce sont des signaux possibles, pas des conseils d&apos;achat ou de vente.</p>
    </section>
  );
}

export function PanneauAlertes({ synthese, mode }: { synthese: SyntheseTableau | null; mode: Mode }) {
  const surveillance = synthese?.alertes.surveillance ?? [];
  const declenchees = synthese?.alertes.declenchees ?? [];
  return (
    <section className="panneau" aria-labelledby="titre-alertes-regles">
      <header className="panneau-tete"><h2 id="titre-alertes-regles">Alertes stop-loss et prise de profit</h2><Link href="/portefeuille" className="lien-discret">Gérer →</Link></header>
      {!synthese ? <p className="chargement">Chargement…</p> : surveillance.length === 0 && declenchees.length === 0 ? (
        <p className="vide">Aucune règle de protection. Après un achat, posez un stop-loss ou une prise de profit depuis la page Portefeuille : la vente se fera seule au seuil choisi.</p>
      ) : (
        <>
          {surveillance.length > 0 && <p className="sous-titre">Règles actives, de la plus proche de son seuil à la plus lointaine</p>}
          <ul className="alertes-regles">
            {surveillance.map((a) => (
              <li key={a.id} data-proche={a.proche}>
                <div className="alerte-regle-tete">
                  <span><strong>{a.symbole}</strong> · {NOMS_REGLE[a.type]}</span>
                  <span className={a.proche ? "texte-alerte" : "discret"}>{a.proche ? "Proche du seuil : " : "À "}{pct(a.distance, 1)}</span>
                </div>
                <span className="barre-piste" role="img" aria-label={`Prix à ${pct(a.distance, 1)} du seuil`}>
                  <span className="barre-rempli" style={{ width: `${Math.max(0, 1 - a.distance / 0.25) * 100}%` }} />
                </span>
                {mode === "trader" && <p className="aide">Seuil {prix(a.niveau)} USD · prix actuel {prix(a.prix)} USD</p>}
              </li>
            ))}
          </ul>
          {mode === "apprenant" && surveillance.length > 0 && <p className="aide">Plus la barre est pleine, plus le prix est près du seuil qui déclenchera la vente automatique.</p>}
          {declenchees.length > 0 && (
            <>
              <p className="sous-titre">Dernières règles déclenchées</p>
              <ul className="liste-simple">
                {declenchees.map((r) => (
                  <li key={r.id}>
                    <time dateTime={r.declenchee_le} className="discret">{dateHeure(r.declenchee_le)}</time>{" "}
                    <strong>{r.symbole}</strong> · {NOMS_REGLE[r.type]} {r.statut === "echec" ? "(échec)" : ""}{r.motif ? ` : ${r.motif}` : ""}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}

export function ActualitesImportantes() {
  const { donnees, erreur } = useLecture<{ instant: string; actualites: Actualite[] }>("/api/v1/actualites?limite=4", 30000);
  return (
    <section className="panneau" aria-labelledby="titre-actus-tableau">
      <header className="panneau-tete"><h2 id="titre-actus-tableau">Dernières actualités</h2><Link href="/actualites" className="lien-discret">Toutes →</Link></header>
      {!donnees ? (erreur ? <p className="erreur" role="alert">{erreur}</p> : <p className="chargement">Chargement…</p>) : donnees.actualites.length === 0 ? (
        <p className="vide">Aucune actualité parue à votre date simulée. Faites avancer le temps pour en voir apparaître.</p>
      ) : (
        <ul className="liste-simple">
          {donnees.actualites.map((a) => (
            <li key={a.id}>
              <time dateTime={a.date} className="discret">{dateCourte(`${a.date}T00:00:00`)}</time>{" "}
              <span className={a.sentiment.etiquette === "positif" ? "gain" : a.sentiment.etiquette === "negatif" ? "perte" : "discret"}>
                {a.sentiment.etiquette === "positif" ? "▲" : a.sentiment.etiquette === "negatif" ? "▼" : "●"}
              </span>{" "}
              {a.titre}
              {a.symboles.length > 0 && <small className="discret"> · {a.symboles.join(", ")}</small>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type Evenement = { cle: string; instant: string; texte: string };

/** Exécutions regroupées par ordre (un ordre peut être rempli en plusieurs fois) et règles déclenchées, les plus récentes d'abord. */
function evenements(execs: Execution[], declenchees: RegleDeclenchee[], n: number): Evenement[] {
  const parOrdre = new Map<number, { e: Execution; q: number; notionnel: number }>();
  for (const e of execs) {
    const g = parOrdre.get(e.ordre_id);
    if (g) { g.q += e.quantite; g.notionnel += e.quantite * e.prix; }
    else parOrdre.set(e.ordre_id, { e, q: e.quantite, notionnel: e.quantite * e.prix });
  }
  const liste: Evenement[] = [...parOrdre.values()].map(({ e, q, notionnel }) => ({
    cle: `o${e.ordre_id}`, instant: e.instant,
    texte: `${e.sens === "achat" ? "Achat" : "Vente"} de ${quantite(q)} ${e.symbole} à ${prix(q ? notionnel / q : e.prix)} USD en moyenne`,
  }));
  for (const r of declenchees) {
    liste.push({ cle: `r${r.id}`, instant: r.declenchee_le, texte: `${NOMS_REGLE[r.type]} déclenché sur ${r.symbole}${r.statut === "echec" ? " (échec)" : ""}` });
  }
  return liste.sort((a, b) => b.instant.localeCompare(a.instant)).slice(0, n);
}

export function ActiviteRecente({ execs, synthese }: { execs: Execution[]; synthese: SyntheseTableau | null }) {
  const liste = useMemo(() => evenements(execs, synthese?.alertes.declenchees ?? [], 6), [execs, synthese]);
  return (
    <section className="panneau" aria-labelledby="titre-activite">
      <header className="panneau-tete"><h2 id="titre-activite">Activité récente</h2><Link href="/portefeuille" className="lien-discret">Historique complet →</Link></header>
      {liste.length === 0 ? <p className="vide">Aucune opération pour le moment. Vos achats, ventes et déclenchements de règles apparaîtront ici.</p> : (
        <ul className="liste-simple">
          {liste.map((ev) => <li key={ev.cle}><time dateTime={ev.instant} className="discret">{dateHeure(ev.instant)}</time> {ev.texte}</li>)}
        </ul>
      )}
    </section>
  );
}
