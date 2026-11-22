"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { lienFiche, ouvrirActif, symboleCourt } from "@/lib/actif";
import { entier, montantSigne, nombre, pct, pctSigne, prix } from "@/lib/format";
import { NOMS_FAMILLES, NOMS_NIVEAUX, RANG_NIVEAU, raisonNiveau } from "@/lib/risque";
import type { Actif, Mouvement, Ordre, Portefeuille, ReferenceSuivi, SyntheseTableau } from "@/lib/types";

export const sens = (v: number | null | undefined) => (v && v > 1e-9 ? "gain" : v && v < -1e-9 ? "perte" : "discret");

export function Variation({ v, decimales = 2 }: { v: number | null | undefined; decimales?: number }) {
  return (
    <span className={`dash-var ${sens(v)}`}>
      <span aria-hidden="true">{sens(v) === "gain" ? "▲ " : sens(v) === "perte" ? "▼ " : ""}</span>{pctSigne(v, decimales)}
    </span>
  );
}

function Identite({ symbole, nom, monogramme = true }: { symbole: string; nom?: string; monogramme?: boolean }) {
  return (
    <span className="dash-actif">
      {monogramme && <span className="dash-mono" aria-hidden="true">{symboleCourt(symbole).slice(0, 2)}</span>}
      <span><strong>{symboleCourt(symbole)}</strong>{nom && <small>{nom}</small>}</span>
    </span>
  );
}

export function References({ references, choix, choisir }: { references: ReferenceSuivi[]; choix: ReferenceSuivi; choisir: (s: string) => void }) {
  return (
    <section className="dash-refs" aria-label="Indices de référence">
      <label className="seance-champ">
        Indice de référence
        <select value={choix.symbole} onChange={(e) => choisir(e.target.value)}>
          {references.map((r) => <option key={r.symbole} value={r.symbole}>{r.nom}{r.dividendes ? ", dividendes inclus" : ""}</option>)}
        </select>
      </label>
      <div className="dash-refs-liste">
        {references.map((r) => (
          <button key={r.symbole} type="button" aria-pressed={r.symbole === choix.symbole} onClick={() => choisir(r.symbole)}>
            <small>{r.nom}{r.dividendes ? " TR" : ""}</small>
            <strong>{entier(r.niveau)}</strong><Variation v={r.variation} />
          </button>
        ))}
      </div>
    </section>
  );
}

export function Risque({ risque }: { risque: SyntheseTableau["niveau_risque"] }) {
  if (risque.niveau === "aucun") {
    return <p className="dash-vide">Aucune position : aucun risque de marché. Le niveau apparaîtra après un achat.</p>;
  }
  return (
    <div className="dash-risque">
      <div>
        <p className="dash-niveau" data-niveau={risque.niveau}>{NOMS_NIVEAUX[risque.niveau]}</p>
        {risque.score !== null && (
          <>
            <p className="dash-score"><strong>{nombre(risque.score, 0)}</strong> / 100</p>
            <div className="dash-echelle" aria-hidden="true"><i style={{ left: `${risque.score}%` }} /></div>
          </>
        )}
        {risque.niveau === "incomplet" && risque.plancher?.niveau === "eleve" && <p className="seance-tag" data-ton="perte">Au moins Élevé</p>}
        <p className="seance-petit">{raisonNiveau(risque)}</p>
      </div>
      <ul className="dash-familles">
        {risque.familles.map((f) => (
          <li key={f.cle}>
            <span>{NOMS_FAMILLES[f.cle]}</span>
            <strong>{pct(f.valeur)}</strong>
            <span className="dash-piste" aria-hidden="true">
              <i data-niveau={f.rang === null ? undefined : RANG_NIVEAU[f.rang]} style={{ width: `${f.note ?? 0}%` }} />
            </span>
            <small>{f.note === null ? "indisponible" : `${nombre(f.note, 0)} × ${pct(f.poids, 0)}`}</small>
          </li>
        ))}
        {(risque.profil.statut === "proche" || risque.profil.statut === "depasse") && (
          <li className="dash-profil">
            Votre baisse actuelle ({pct(risque.profil.perte_actuelle)}) {risque.profil.statut === "depasse" ? "dépasse" : "approche"} la perte que vous acceptez ({pct(risque.profil.tolerance, 0)}).
          </li>
        )}
      </ul>
    </div>
  );
}

export function ContreReference({ suivi, reference, pireBaisse }: { suivi: SyntheseTableau["suivi"]; reference: ReferenceSuivi; pireBaisse: number }) {
  const ecart = reference.ecart_points === null ? null : reference.ecart_points / 100;
  const lignes: [string, number | null, boolean][] = [["Vous", suivi.rendement_total, false], [reference.nom, reference.depuis_debut, false], ["Votre écart", ecart, true]];
  const maxi = Math.max(0.02, ...lignes.map(([, v]) => Math.abs(v ?? 0)));
  return (
    <>
      <ul className="dash-compare">
        {lignes.map(([nom, v, enPoints]) => (
          <li key={nom}>
            <span>{nom}</span>
            <span className="dash-axe" aria-hidden="true">
              {v !== null && <i data-sens={v >= 0 ? "gain" : "perte"} style={{ width: `${(Math.abs(v) / maxi) * 49}%`, [v >= 0 ? "left" : "right"]: "50%" }} />}
            </span>
            <strong className={sens(v)}>{v === null ? "–" : enPoints ? `${montantSigne(v * 100)} pts` : pctSigne(v)}</strong>
          </li>
        ))}
      </ul>
      <dl className="dash-details">
        <div><dt>Capital initial</dt><dd>{entier(suivi.capital_initial)} USD</dd></div>
        <div><dt>Pire baisse vécue</dt><dd>{pct(pireBaisse)}</dd></div>
        <div><dt>Durée</dt><dd>{suivi.jours} {suivi.jours > 1 ? "jours" : "jour"}</dd></div>
      </dl>
    </>
  );
}

export function Positions({ pf, parSymbole }: { pf: Portefeuille; parSymbole: Map<string, Actif> }) {
  const lignes = [...pf.positions].sort((a, b) => b.valeur - a.valeur).slice(0, 5);
  if (lignes.length === 0) return <p className="dash-vide">Aucune position. Passez un premier ordre.</p>;
  return (
    <ul className="dash-lignes">
      {lignes.map((p) => (
        <li key={p.symbole}>
          <Link href={lienFiche(p.symbole)}>
            <Identite symbole={p.symbole} nom={parSymbole.get(p.symbole)?.nom} />
            <span className="dash-droite">
              {entier(p.valeur)} <span className="discret">USD</span><br />
              <Variation v={p.prix_moyen ? (p.prix_marche - p.prix_moyen) / Math.abs(p.prix_moyen) : null} decimales={1} />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

const NOMS_REGLES = { stop_loss: "Stop-loss", take_profit: "Objectif", stop_suiveur: "Stop suiveur" } as const;

export function ASurveiller({ synthese, ordres, pf }: { synthese: SyntheseTableau; ordres: Ordre[]; pf: Portefeuille }) {
  type Ligne = { cle: string; symbole: string; texte: string; etat: string; ton?: "gain" | "perte" | "alerte" | "accent" };
  const lignes: Ligne[] = synthese.alertes.surveillance.slice(0, 3).map((a) => ({
    cle: `r${a.id}`, symbole: a.symbole, texte: `${NOMS_REGLES[a.type]} à ${pct(a.distance)} du prix`,
    etat: a.proche ? "Proche" : "Protégé", ton: a.proche ? "alerte" : "accent",
  }));
  for (const o of ordres.filter((x) => x.statut === "en_attente" || x.statut === "partiel").slice(0, 2)) {
    lignes.push({
      cle: `o${o.id}`, symbole: o.symbole, etat: "En attente", ton: "accent",
      texte: `${o.sens === "achat" ? "Achat" : "Vente"} en attente à ${prix(o.type === "limite" ? o.prix_limite : o.prix_stop)}`,
    });
  }
  const proteges = new Set(lignes.map((l) => l.symbole));
  const sansProtection = pf.positions.filter((p) => !proteges.has(p.symbole) && p.prix_moyen)
    .map((p) => ({ p, v: (p.prix_marche - p.prix_moyen) / Math.abs(p.prix_moyen) }))
    .sort((a, b) => a.v - b.v).slice(0, Math.max(0, 4 - lignes.length));
  for (const { p, v } of sansProtection) {
    lignes.push({
      cle: `p${p.symbole}`, symbole: p.symbole, texte: `${pctSigne(v, 1)} depuis votre achat`,
      etat: v < -0.1 ? "À revoir" : "Sans protection", ton: v < -0.1 ? "perte" : undefined,
    });
  }
  if (lignes.length === 0) return <p className="dash-vide">Rien ne demande votre attention.</p>;
  return (
    <ul className="dash-lignes">
      {lignes.map((l) => (
        <li key={l.cle}>
          <Link href={lienFiche(l.symbole)}>
            <span className="dash-actif"><span><strong>{symboleCourt(l.symbole)}</strong><small>{l.texte}</small></span></span>
            <span className="seance-tag" data-ton={l.ton}>{l.etat}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

const CLASSE_REPARTITION: Record<string, string> = {
  Actions: "var(--serie-1)", Cryptomonnaies: "var(--serie-2)", "Matières premières": "var(--serie-3)", Liquidités: "var(--ref)",
};

export function Repartition({ lignes }: { lignes: SyntheseTableau["repartition_detail"]["marche"] }) {
  // ordre fixe : la couleur et la place suivent la classe, pas son rang
  const ordre = Object.keys(CLASSE_REPARTITION);
  const tri = [...lignes].sort((a, b) => ordre.indexOf(a.libelle) - ordre.indexOf(b.libelle));
  return (
    <>
      <div className="dash-repartition" aria-hidden="true">
        {tri.map((l) => <i key={l.libelle} style={{ flexGrow: Math.max(l.part, 0), background: CLASSE_REPARTITION[l.libelle] }} />)}
      </div>
      <ul className="dash-legende">
        {tri.map((l) => (
          <li key={l.libelle}>
            <i aria-hidden="true" style={{ background: CLASSE_REPARTITION[l.libelle] }} /><span>{l.libelle}</span><strong>{pct(l.part)}</strong>
          </li>
        ))}
      </ul>
    </>
  );
}

function MiniCourbe({ serie }: { serie: number[] }) {
  if (serie.length < 2) return null;
  const bas = Math.min(...serie), haut = Math.max(...serie);
  const d = serie.map((v, i) => `${i ? "L" : "M"}${((i * 76) / (serie.length - 1)).toFixed(1)},${(18 - ((v - bas) / (haut - bas || 1)) * 16).toFixed(1)}`).join("");
  return <svg className={`dash-mini ${serie[serie.length - 1] >= serie[0] ? "gain" : "perte"}`} width="76" height="20" aria-hidden="true"><path d={d} /></svg>;
}

export function Mouvements({ lignes }: { lignes: Mouvement[] }) {
  const router = useRouter();
  if (lignes.length === 0) return <p className="dash-vide">Pas de cotation à cette date.</p>;
  return (
    <div className="dash-defile">
      <table className="dash-table">
        <thead><tr><th>Plus forts mouvements</th><th className="dash-mini-col">30 séances</th><th>Dernier</th><th>Séance</th></tr></thead>
        <tbody>
          {lignes.map((m) => (
            <tr key={m.symbole}>
              <td><button type="button" onClick={() => ouvrirActif(router, m)}><Identite symbole={m.symbole} nom={m.nom} monogramme={false} /></button></td>
              <td className="dash-mini-col"><MiniCourbe serie={m.serie} /></td>
              <td>{prix(m.prix)}</td>
              <td><Variation v={m.variation} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
