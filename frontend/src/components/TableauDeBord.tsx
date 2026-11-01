"use client";

import Link from "next/link";
import { useMemo } from "react";
import { dateCourte, montant, montantSigne, pct, pctSigne, prix, variation } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import { REPERES } from "@/lib/reperes";
import type { Actif, Classe, CotationLigne, HistoriqueValeur } from "@/lib/types";
import { useMarche } from "./Contexte";
import Courbe from "./Courbe";
import Indicateur from "./Indicateur";

const MARCHES: { classe: Classe; titre: string; href: string }[] = [
  { classe: "action", titre: "Actions", href: "/actions" },
  { classe: "crypto", titre: "Cryptomonnaies", href: "/crypto" },
  { classe: "matiere", titre: "Matières premières", href: "/matieres" },
];

function variationDe(c: CotationLigne): number | null {
  const base = c.reference ?? c.derniere_cloture;
  return base ? (c.prix - base) / Math.abs(base) : null;
}

function Mouvements({ titre, href, lignes }: { titre: string; href: string; lignes: { actif: Actif; c: CotationLigne; v: number }[] }) {
  const tri = [...lignes].sort((a, b) => b.v - a.v);
  const hausses = tri.slice(0, 3);
  const baisses = tri.slice(-3).reverse().filter((l) => !hausses.includes(l));
  const ligne = (l: { actif: Actif; c: CotationLigne; v: number }) => (
    <li key={l.actif.symbole}>
      <Link href={`${href}`} className="mouvement">
        <span><strong>{l.actif.symbole}</strong> <small>{l.actif.nom}</small></span>
        <span className="mouvement-droite">{prix(l.c.prix)} <small className={l.v > 0 ? "gain" : l.v < 0 ? "perte" : ""}>{l.v > 0 ? "▲ " : l.v < 0 ? "▼ " : ""}{variation(l.v)}</small></span>
      </Link>
    </li>
  );
  return (
    <section className="panneau">
      <header className="panneau-tete"><h2>{titre}</h2><Link href={href} className="lien-discret">Ouvrir le marché →</Link></header>
      {lignes.length === 0 ? <p className="vide">Pas de cotation à cette date.</p> : (
        <>
          <p className="sous-titre">Plus fortes hausses</p>
          <ul>{hausses.map(ligne)}</ul>
          {baisses.length > 0 && (<><p className="sous-titre">Plus fortes baisses</p><ul>{baisses.map(ligne)}</ul></>)}
        </>
      )}
    </section>
  );
}

export default function TableauDeBord() {
  const { utilisateur, inst, actifs, pf, execs, ordres, aller, mode } = useMarche();
  const { donnees: hist } = useLecture<HistoriqueValeur>("/api/v1/portefeuille/historique", 6000);

  const parClasse = useMemo(() => {
    const parSymbole = new Map(actifs.map((a) => [a.symbole, a]));
    const out: Record<string, { actif: Actif; c: CotationLigne; v: number }[]> = {};
    for (const c of inst?.cotations ?? []) {
      const a = parSymbole.get(c.symbole);
      const v = variationDe(c);
      if (!a || v === null || !a.tradable) continue;
      (out[a.classe] ??= []).push({ actif: a, c, v });
    }
    return out;
  }, [actifs, inst]);

  const indices = (inst?.cotations ?? []).filter((c) => c.symbole === "^GSPC" || c.symbole === "^VIX");
  const rendement = pf && pf.capital_initial ? pf.pnl_total / pf.capital_initial : null;
  const ordresOuverts = ordres.filter((o) => o.statut === "en_attente" || o.statut === "partiel");
  const aucunePosition = !!pf && pf.positions.length === 0 && execs.length === 0;
  const top = pf ? [...pf.positions].sort((a, b) => b.valeur - a.valeur).slice(0, 5) : [];
  const instantDate = inst?.instant.slice(0, 10) ?? "";

  return (
    <main className="page">
      <header className="page-tete">
        <div>
          <h1>Bonjour {utilisateur.nom}</h1>
          <p className="aide">Votre vue d&apos;ensemble : la valeur de votre portefeuille, les marchés du jour et ce qu&apos;il reste à faire.</p>
        </div>
      </header>

      {(!utilisateur.profil_risque || aucunePosition) && (
        <section className="panneau panneau-depart" aria-label="Pour commencer">
          <h2>Pour commencer</h2>
          <ol className="etapes">
            <li data-fait={!!utilisateur.profil_risque}>
              <span><strong>Répondez au questionnaire de risque.</strong> Il fixe la perte maximale que vous acceptez ; le simulateur la compare ensuite à vos portefeuilles.</span>
              {!utilisateur.profil_risque && <Link className="btn" href="/compte#profil">Répondre</Link>}
            </li>
            <li data-fait={!aucunePosition}>
              <span><strong>Passez votre premier ordre.</strong> Ouvrez un marché, choisissez un actif et achetez-en quelques-uns avec votre capital virtuel.</span>
              {aucunePosition && <Link className="btn" href="/actions">Ouvrir les actions</Link>}
            </li>
            <li data-fait={false}>
              <span><strong>Faites avancer le temps.</strong> Appuyez sur « Lancer » en haut de page : une semaine passe en une heure. Regardez ensuite votre portefeuille évoluer.</span>
            </li>
          </ol>
        </section>
      )}

      <section className="kpis" aria-label="Résumé du portefeuille">
        <Indicateur grand libelle="Valeur du portefeuille" valeur={pf ? montant(pf.equity) : "–"}
          detail={pf ? `Capital de départ : ${montant(pf.capital_initial)}` : undefined}
          explication="C'est ce que vaudrait tout votre portefeuille si vous vendiez tout maintenant : liquidités plus positions." />
        <Indicateur libelle="Gain ou perte depuis le départ" valeur={pf ? `${pf.pnl_total > 0 ? "▲ " : pf.pnl_total < 0 ? "▼ " : ""}${montantSigne(pf.pnl_total)}` : "–"}
          ton={pf && pf.pnl_total !== 0 ? (pf.pnl_total > 0 ? "gain" : "perte") : undefined} detail={rendement !== null ? pctSigne(rendement) : undefined}
          explication="La différence entre la valeur actuelle et votre capital de départ, frais compris." />
        <Indicateur libelle="Liquidités" valeur={pf ? montant(pf.cash) : "–"} detail={pf && pf.equity ? `${pct(pf.cash / pf.equity, 0)} du portefeuille` : undefined}
          explication="L'argent non investi. Il sert à acheter et amortit les baisses." />
        <Indicateur libelle="Positions ouvertes" valeur={pf ? String(pf.positions.length) : "–"} detail={ordresOuverts.length > 0 ? `${ordresOuverts.length} ordre(s) en attente` : undefined}
          explication="Le nombre d'actifs que vous détenez en ce moment." />
      </section>

      <div className="grille-2">
        <section className="panneau">
          <header className="panneau-tete"><h2>Valeur du portefeuille</h2><Link href="/portefeuille" className="lien-discret">Analyse complète →</Link></header>
          {hist ? <Courbe points={hist.points} capitalInitial={hist.capital_initial} nomReference="S&P 500" hauteur={230} tableau={false} /> : <p className="vide">Chargement…</p>}
        </section>

        <section className="panneau">
          <header className="panneau-tete"><h2>Indices de référence</h2></header>
          <ul className="liste-indices">
            {indices.map((c) => {
              const v = variationDe(c);
              const nom = c.symbole === "^GSPC" ? "S&P 500" : "VIX";
              return (
                <li key={c.symbole}>
                  <p><strong>{nom}</strong> <small className="discret">{c.symbole === "^VIX" ? "peur du marché" : "500 grandes entreprises américaines"}</small></p>
                  <p className="indice-prix">{prix(c.prix)} <small className={v !== null && v > 0 ? "gain" : v !== null && v < 0 ? "perte" : ""}>{v !== null && (v > 0 ? "▲ " : v < 0 ? "▼ " : "")}{variation(v)}</small></p>
                </li>
              );
            })}
          </ul>
          {mode === "apprenant" && <p className="aide">Le VIX monte quand les investisseurs ont peur : il dépasse souvent 30 dans les krachs.</p>}
        </section>
      </div>

      <div className="grille-3">
        {MARCHES.map((m) => <Mouvements key={m.classe} titre={m.titre} href={m.href} lignes={parClasse[m.classe] ?? []} />)}
      </div>

      <div className="grille-2">
        <section className="panneau">
          <header className="panneau-tete"><h2>Mes plus grosses positions</h2><Link href="/portefeuille" className="lien-discret">Tout voir →</Link></header>
          {top.length === 0 ? <p className="vide">Aucune position pour le moment.</p> : (
            <table className="tableau tableau-compact">
              <thead><tr><th>Actif</th><th>Valeur</th><th>Gain ou perte</th><th>Poids</th></tr></thead>
              <tbody>
                {top.map((p) => (
                  <tr key={p.symbole}>
                    <td>{p.symbole}</td><td>{montant(p.valeur)}</td>
                    <td className={p.pnl_latent > 0 ? "gain" : p.pnl_latent < 0 ? "perte" : ""}>{p.pnl_latent > 0 ? "▲ " : p.pnl_latent < 0 ? "▼ " : ""}{montantSigne(p.pnl_latent)}</td>
                    <td>{pct(p.poids)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panneau">
          <header className="panneau-tete"><h2>Machine à remonter le temps</h2></header>
          <p className="aide">Sautez directement à un moment marquant de l&apos;histoire des marchés et voyez comment votre portefeuille aurait réagi.</p>
          <ul className="reperes">
            {REPERES.map((r) => (
              <li key={r.date}>
                <div><strong>{r.titre}</strong><p className="discret">{dateCourte(`${r.date}T00:00:00`)} · {r.explication}</p></div>
                <button className="btn" onClick={() => void aller(`${r.date}T17:00:00`)} disabled={instantDate === r.date}>Y aller</button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}
