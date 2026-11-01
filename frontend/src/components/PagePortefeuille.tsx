"use client";

import Link from "next/link";
import { useState } from "react";
import { dateHeure, montant, montantSigne, nombre, pct, pctSigne, prix, quantite } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import { LIBELLE_STATUT_REGLE, libelleRegle } from "@/lib/regles";
import type { Analyse, HistoriqueValeur, Trade } from "@/lib/types";
import Barres from "./Barres";
import { useMarche } from "./Contexte";
import Correlations from "./Correlations";
import Courbe from "./Courbe";
import Indicateur from "./Indicateur";

const STATUTS = {
  ok: { icone: "✓", titre: "Dans votre tolérance", classe: "jauge-ok" },
  proche: { icone: "!", titre: "Proche de votre limite", classe: "jauge-proche" },
  depasse: { icone: "✕", titre: "Au-delà de votre tolérance", classe: "jauge-depasse" },
} as const;

function ton(n: number): "gain" | "perte" | undefined { return n > 0 ? "gain" : n < 0 ? "perte" : undefined; }
function fleche(n: number): string { return n > 0 ? "▲ " : n < 0 ? "▼ " : ""; }
/** Une perte exprimée en nombre positif (0,03 = 3 %) : flèche et signe moins seulement s'il y a vraiment une perte. */
function perte(n: number): string { return n > 1e-9 ? `▼ −${pct(n)}` : pct(n); }

function ProfilVsRisque({ analyse }: { analyse: Analyse | null }) {
  const { mode } = useMarche();
  if (!analyse) return <section className="panneau"><header className="panneau-tete"><h2>Profil de risque</h2></header><p className="vide">Chargement…</p></section>;
  const p = analyse.profil;
  if (p.statut === "profil_absent") {
    return (
      <section className="panneau">
        <header className="panneau-tete"><h2>Profil de risque</h2></header>
        <p>Vous n&apos;avez pas encore défini votre profil de risque. Sans lui, le simulateur ne peut pas dire si votre portefeuille est trop risqué <em>pour vous</em>.</p>
        <p style={{ marginTop: "0.75rem" }}><Link className="btn btn-principal btn-lien" href="/compte#profil">Répondre au questionnaire (2 minutes)</Link></p>
      </section>
    );
  }
  const s = STATUTS[p.statut];
  const utilisation = Math.max(0, Math.min(1, p.utilisation ?? 0));
  return (
    <section className="panneau" aria-labelledby="titre-profil-risque">
      <header className="panneau-tete"><h2 id="titre-profil-risque">Profil de risque : {p.categorie}</h2><Link href="/compte#profil" className="lien-discret">Modifier</Link></header>
      <p className={`statut ${s.classe}`}><span aria-hidden="true">{s.icone}</span> {s.titre}</p>
      <div className="jauge" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(utilisation * 100)}
        aria-label="Part de votre perte maximale tolérée déjà utilisée">
        <span className={`jauge-rempli ${s.classe}`} style={{ width: `${utilisation * 100}%` }} />
        <span className="jauge-seuil" style={{ left: "75%" }} aria-hidden="true" />
      </div>
      <dl className="jauge-chiffres">
        <div><dt>Perte actuelle depuis le sommet</dt><dd>{pct(p.perte_actuelle)}</dd></div>
        <div><dt>Perte maximale que vous acceptez</dt><dd>{pct(p.perte_tolerance, 0)}</dd></div>
        {p.var95_jour !== null && p.var95_jour !== undefined && (
          <div><dt>Un mauvais jour peut coûter (VaR 95 %)</dt><dd>{pct(p.var95_jour)}{p.var_sur_tolerance !== null && p.var_sur_tolerance !== undefined ? ` · ${pct(p.var_sur_tolerance, 0)} de votre limite` : ""}</dd></div>
        )}
      </dl>
      {mode === "apprenant" && (
        <p className="aide">Votre limite vient de votre questionnaire. La barre se remplit quand votre portefeuille s&apos;éloigne de son dernier sommet ; au-delà de 75 %, on vous prévient.</p>
      )}
    </section>
  );
}

const ONGLETS_REPARTITION = [
  { cle: "marche", libelle: "Par marché" },
  { cle: "secteur", libelle: "Par secteur" },
  { cle: "position", libelle: "Par actif" },
] as const;

function Repartition({ analyse }: { analyse: Analyse | null }) {
  const [cle, setCle] = useState<(typeof ONGLETS_REPARTITION)[number]["cle"]>("marche");
  const { mode } = useMarche();
  if (!analyse) return <section className="panneau"><header className="panneau-tete"><h2>Répartition</h2></header><p className="vide">Chargement…</p></section>;
  const d = analyse.diversification;
  const c = analyse.concentration;
  return (
    <section className="panneau">
      <header className="panneau-tete"><h2>Répartition du portefeuille</h2></header>
      <div className="onglets" role="tablist" aria-label="Type de répartition">
        {ONGLETS_REPARTITION.map((o) => (
          <button key={o.cle} role="tab" aria-selected={cle === o.cle} className="onglet" onClick={() => setCle(o.cle)}>{o.libelle}</button>
        ))}
      </div>
      <div className="repartition-corps"><Barres parts={analyse.repartition[cle]} titre={`Répartition ${ONGLETS_REPARTITION.find((o) => o.cle === cle)!.libelle.toLowerCase()}`} /></div>
      <dl className="mini-indicateurs">
        <div>
          <dt>Diversification</dt>
          <dd>{d ? `${d.score} / 100` : "–"}</dd>
          {mode === "apprenant" && <p className="aide">{d ? `${d.nb_positions} position(s) sur ${d.nb_marches} marché(s). Plus c'est réparti, plus la note monte.` : "S'affiche dès que vous détenez un actif."}</p>}
        </div>
        <div>
          <dt>Plus grosse position</dt>
          <dd>{c ? `${c.plus_grosse_position.symbole} · ${pct(c.plus_grosse_position.part, 0)}` : "–"}</dd>
          {mode === "apprenant" && <p className="aide">{c ? `Comme si vous déteniez ${nombre(c.nb_effectif, 1)} actifs de taille égale.` : ""}</p>}
        </div>
      </dl>
    </section>
  );
}

function Journal({ trades }: { trades: Trade[] | null }) {
  const { pf, ordres, execs, annuler, regles, supprimerRegle } = useMarche();
  const [onglet, setOnglet] = useState<"positions" | "trades" | "ordres" | "executions" | "regles">("positions");
  const origines = new Map(ordres.map((o) => [o.id, o.origine]));
  const actives = regles.filter((r) => r.statut === "active").length;
  const ouverts = ordres.filter((o) => o.statut === "en_attente" || o.statut === "partiel");
  const LIBELLE_STATUT: Record<string, string> = { en_attente: "En attente", partiel: "Partiel", execute: "Exécuté", annule: "Annulé", rejete: "Refusé" };
  const LIBELLE_TYPE: Record<string, string> = { marche: "Marché", limite: "Limite", stop: "Stop" };
  return (
    <section className="panneau panneau-tableau">
      <div className="onglets" role="tablist" aria-label="Détail du portefeuille">
        <button role="tab" aria-selected={onglet === "positions"} className="onglet" onClick={() => setOnglet("positions")}>Positions ({pf?.positions.length ?? 0})</button>
        <button role="tab" aria-selected={onglet === "trades"} className="onglet" onClick={() => setOnglet("trades")}>Trades clôturés ({trades?.length ?? 0})</button>
        <button role="tab" aria-selected={onglet === "ordres"} className="onglet" onClick={() => setOnglet("ordres")}>Ordres{ouverts.length > 0 ? ` (${ouverts.length} en attente)` : ""}</button>
        <button role="tab" aria-selected={onglet === "executions"} className="onglet" onClick={() => setOnglet("executions")}>Journal des exécutions</button>
        <button role="tab" aria-selected={onglet === "regles"} className="onglet" onClick={() => setOnglet("regles")}>Règles automatiques{actives > 0 ? ` (${actives} active${actives > 1 ? "s" : ""})` : ""}</button>
      </div>
      <div className="tableau-defile" role="tabpanel">
        {onglet === "positions" && (pf && pf.positions.length > 0 ? (
          <table className="tableau">
            <thead><tr><th>Actif</th><th>Quantité</th><th>Prix moyen</th><th>Prix actuel</th><th>Valeur</th><th>Gain ou perte latent</th><th>Rendement</th><th>Poids</th></tr></thead>
            <tbody>
              {pf.positions.map((p) => {
                const r = p.prix_moyen ? p.prix_marche / p.prix_moyen - 1 : null;
                return (
                  <tr key={p.symbole}>
                    <td>{p.symbole}</td><td>{quantite(p.quantite)}</td><td>{prix(p.prix_moyen)}</td><td>{prix(p.prix_marche)}</td><td>{montant(p.valeur)}</td>
                    <td className={ton(p.pnl_latent)}>{fleche(p.pnl_latent)}{montantSigne(p.pnl_latent)}</td>
                    <td className={r !== null ? ton(r) : undefined}>{r !== null ? `${fleche(r)}${pctSigne(r)}` : "–"}</td><td>{pct(p.poids)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : <p className="vide">Aucune position. Ouvrez un marché pour passer un premier ordre.</p>)}

        {onglet === "trades" && (trades && trades.length > 0 ? (
          <table className="tableau">
            <thead><tr><th>Date simulée</th><th>Actif</th><th>Quantité</th><th>Prix d&apos;achat moyen</th><th>Prix de vente</th><th>Gain ou perte réalisé</th><th>Rendement</th><th>Frais</th></tr></thead>
            <tbody>
              {trades.map((t, i) => (
                <tr key={`${t.instant}-${i}`}>
                  <td>{dateHeure(t.instant)}</td><td>{t.symbole}</td><td>{quantite(t.quantite)}</td><td>{prix(t.prix_achat_moyen)}</td><td>{prix(t.prix_vente)}</td>
                  <td className={ton(t.pnl)}>{fleche(t.pnl)}{montantSigne(t.pnl)}</td>
                  <td className={t.rendement !== null ? ton(t.rendement) : undefined}>{t.rendement !== null ? `${fleche(t.rendement)}${pctSigne(t.rendement)}` : "–"}</td><td>{montant(t.frais)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="vide">Aucun trade clôturé : un trade est clôturé quand vous vendez une position.</p>)}

        {onglet === "ordres" && (ordres.length > 0 ? (
          <table className="tableau">
            <thead><tr><th>N°</th><th>Actif</th><th>Sens</th><th>Type</th><th>Quantité</th><th>Niveau</th><th>Prix moyen</th><th>Statut</th><th><span className="sr-only">Action</span></th></tr></thead>
            <tbody>
              {[...ordres].reverse().map((o) => (
                <tr key={o.id}>
                  <td>{o.id}</td><td>{o.symbole}</td><td>{o.sens === "achat" ? "Achat" : "Vente"}</td><td>{LIBELLE_TYPE[o.type]}{o.origine ? <span className="pastille" title="Placé par une règle automatique">auto</span> : null}</td>
                  <td>{quantite(o.quantite_executee)} / {quantite(o.quantite)}</td><td>{prix(o.prix_limite ?? o.prix_stop)}</td><td>{prix(o.prix_moyen)}</td>
                  <td title={o.motif ?? undefined}>{LIBELLE_STATUT[o.statut]}{o.statut === "rejete" && o.motif ? ` : ${o.motif}` : ""}</td>
                  <td>{(o.statut === "en_attente" || o.statut === "partiel") && <button className="lien" onClick={() => void annuler(o.id)}>Annuler</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="vide">Aucun ordre pour le moment.</p>)}

        {onglet === "executions" && (execs.length > 0 ? (
          <table className="tableau">
            <thead><tr><th>Date simulée</th><th>Actif</th><th>Sens</th><th>Quantité</th><th>Prix</th><th>Frais</th><th>Origine</th></tr></thead>
            <tbody>
              {execs.map((e, i) => (
                <tr key={`${e.ordre_id}-${i}`}><td>{dateHeure(e.instant)}</td><td>{e.symbole}</td><td>{e.sens === "achat" ? "Achat" : "Vente"}</td><td>{quantite(e.quantite)}</td><td>{prix(e.prix)}</td><td>{montant(e.frais)}</td><td>{origines.get(e.ordre_id) ? "Règle automatique" : "Manuel"}</td></tr>
              ))}
            </tbody>
          </table>
        ) : <p className="vide">Aucune exécution pour le moment.</p>)}

        {onglet === "regles" && (regles.length > 0 ? (
          <table className="tableau tableau-regles">
            <thead><tr><th>Actif</th><th>Règle</th><th>Se déclenche vers</th><th>Statut</th><th>Posée le</th><th>Résultat</th><th><span className="sr-only">Action</span></th></tr></thead>
            <tbody>
              {regles.map((r) => (
                <tr key={r.id}>
                  <td>{r.symbole}</td><td>{libelleRegle(r)}</td><td>{r.niveau !== null ? prix(r.niveau) : "–"}</td>
                  <td>{LIBELLE_STATUT_REGLE[r.statut]}</td><td>{r.cree_le ? dateHeure(r.cree_le) : "–"}</td>
                  <td title={r.motif ?? undefined}>{r.motif ?? ""}</td>
                  <td>{r.statut === "active" && <button className="lien" onClick={() => void supprimerRegle(r.id)}>Retirer</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="vide">Aucune règle automatique. Ouvrez un marché, achetez un actif, puis posez un stop-loss dans « Protection automatique ».</p>)}
      </div>
    </section>
  );
}

export default function PagePortefeuille() {
  const { pf, inst } = useMarche();
  const { donnees: analyse } = useLecture<Analyse>("/api/v1/portefeuille/analyse", 4000);
  const { donnees: hist } = useLecture<HistoriqueValeur>("/api/v1/portefeuille/historique", 4000);
  const { donnees: trades } = useLecture<Trade[]>("/api/v1/portefeuille/trades", 5000);
  const perf = analyse?.performance;
  const risque = analyse?.risque;
  const rendement = pf && pf.capital_initial ? pf.pnl_total / pf.capital_initial : null;

  return (
    <main className="page">
      <header className="page-tete">
        <div>
          <h1>Portefeuille</h1>
          <p className="aide">Un seul portefeuille pour les trois marchés (actions, cryptomonnaies, matières premières). Tout est calculé à la date simulée{inst ? ` du ${inst.instant.slice(0, 10).split("-").reverse().join("/")}` : ""}, sans jamais regarder le futur.</p>
        </div>
      </header>

      <section className="kpis" aria-label="Résumé">
        <Indicateur grand libelle="Valeur du portefeuille" valeur={pf ? montant(pf.equity) : "–"} detail={pf ? `Capital de départ : ${montant(pf.capital_initial)}` : undefined}
          explication="Liquidités plus valeur de toutes vos positions au prix actuel." />
        <Indicateur libelle="Gain ou perte total" valeur={pf ? `${fleche(pf.pnl_total)}${montantSigne(pf.pnl_total)}` : "–"} ton={pf ? ton(pf.pnl_total) : undefined} detail={rendement !== null ? pctSigne(rendement) : undefined}
          explication="Valeur actuelle moins capital de départ." />
        <Indicateur libelle="Réalisé" valeur={pf ? `${fleche(pf.pnl_realise)}${montantSigne(pf.pnl_realise)}` : "–"} ton={pf ? ton(pf.pnl_realise) : undefined}
          explication="Gains et pertes déjà encaissés par vos ventes." />
        <Indicateur libelle="Latent" valeur={pf ? `${fleche(pf.pnl_latent)}${montantSigne(pf.pnl_latent)}` : "–"} ton={pf ? ton(pf.pnl_latent) : undefined}
          explication="Gains et pertes sur ce que vous détenez encore : ils peuvent encore changer." />
        <Indicateur libelle="Liquidités" valeur={pf ? montant(pf.cash) : "–"} detail={pf ? `Frais payés : ${montant(pf.frais_cumules)}` : undefined}
          explication="L'argent non investi, disponible pour acheter." />
      </section>

      <div className="grille-courbe">
        <section className="panneau">
          <header className="panneau-tete"><h2>Valeur au fil du temps</h2></header>
          {hist ? <Courbe points={hist.points} capitalInitial={hist.capital_initial} nomReference="S&P 500" /> : <p className="vide">Chargement…</p>}
        </section>
        <ProfilVsRisque analyse={analyse} />
      </div>

      <section aria-labelledby="titre-indicateurs">
        <h2 id="titre-indicateurs" className="titre-section">Indicateurs de risque</h2>
        <div className="kpis kpis-risque">
          <Indicateur libelle="VaR 95 %, un jour" valeur={risque ? perte(risque.var) : "–"} ton={risque && risque.var > 1e-9 ? "perte" : undefined}
            detail={risque ? `soit ${montant(risque.var_montant)} sur ${risque.jours} jours d'historique` : undefined}
            explication="Les jours « normaux » (95 %), vous ne perdez pas plus que cela. Les 5 % de jours restants sont pires." />
          <Indicateur libelle="CVaR 95 %, un jour" valeur={risque ? perte(risque.cvar) : "–"} ton={risque && risque.cvar > 1e-9 ? "perte" : undefined}
            detail={risque ? `soit ${montant(risque.cvar_montant)}` : undefined}
            explication="La perte moyenne pendant ces 5 % de pires jours : la VaR dit où ça commence, la CVaR dit jusqu'où ça peut aller." />
          <Indicateur libelle="Volatilité annualisée" valeur={perf?.volatilite_annuelle != null ? pct(perf.volatilite_annuelle) : "–"}
            explication="La nervosité de votre portefeuille. Plus elle est haute, plus sa valeur bouge fort dans les deux sens." />
          <Indicateur libelle="Ratio de Sharpe" valeur={perf?.sharpe != null ? nombre(perf.sharpe, 2) : "–"}
            explication="Rendement annualisé divisé par la volatilité (taux sans risque posé à 0). Au-dessus de 1, le risque pris a été bien payé." />
          <Indicateur libelle="Ratio de Sortino" valeur={perf?.sortino != null ? nombre(perf.sortino, 2) : "–"}
            explication="Comme le Sharpe, mais seules les baisses comptent comme du risque : les hausses ne sont pas punies." />
          <Indicateur libelle="Perte maximale subie" valeur={perf ? perte(perf.drawdown_max) : "–"} ton={perf && perf.drawdown_max > 1e-9 ? "perte" : undefined}
            explication="La pire chute de votre portefeuille depuis un de ses sommets (« drawdown maximal »)." />
          <Indicateur libelle="Perte depuis le dernier sommet" valeur={perf ? perte(perf.drawdown_courant) : "–"} ton={perf && perf.drawdown_courant > 1e-9 ? "perte" : undefined}
            explication="Où vous en êtes aujourd'hui par rapport à votre plus haut. Zéro signifie que vous êtes à un sommet." />
          <Indicateur libelle="Rendement annualisé" valeur={perf?.rendement_annuel != null ? pctSigne(perf.rendement_annuel) : "–"} ton={perf?.rendement_annuel != null ? ton(perf.rendement_annuel) : undefined}
            explication="Ce que rapporterait votre rythme actuel sur une année complète. Peu fiable sur une courte période." />
        </div>
        {analyse && analyse.avertissements.length > 0 && (
          <ul className="notes" aria-label="À savoir">
            {analyse.avertissements.map((a) => <li key={a}>{a}</li>)}
          </ul>
        )}
      </section>

      <div className="grille-2">
        <Repartition analyse={analyse} />
        <section className="panneau">
          <header className="panneau-tete"><h2>Corrélations entre vos actifs</h2></header>
          {analyse?.correlations ? (
            <Correlations symboles={analyse.correlations.symboles} matrice={analyse.correlations.matrice} />
          ) : <p className="vide">Détenez au moins deux actifs et laissez passer quelques semaines de simulation pour voir comment ils bougent ensemble.</p>}
          <p className="aide">Deux actifs très corrélés (bleu foncé) montent et baissent ensemble : les détenir tous les deux diversifie peu.</p>
        </section>
      </div>

      <Journal trades={trades} />
    </main>
  );
}
