"use client";

import { nombre } from "@/lib/format";
import { points, pc, Statut } from "./Communs";
import { LIBELLE_TYPE, type Comparaison, type TypeBanque } from "./types";

const FIN = 0.19;                                     // l'axe finit à 19 % ; il commence à 4 %, ou plus bas si une banque y descend
const TYPES: TypeBanque[] = ["islamique", "conventionnelle"];
const m = (v: number) => nombre(v, 2);

/** Résultat de la simulation pour PLUSIEURS banques : duel des deux groupes, une ligne par banque, classement du pire cas. */
export default function Comparer({ comp, ouvrir }: { comp: Comparaison; ouvrir: (cle: string) => void }) {
  const DEBUT = Math.min(0.04, Math.floor(Math.min(...comp.resultats.map((r) => r.cet1_apres)) * 100) / 100);
  const pos = (v: number) => Math.min(100, Math.max(0, ((v - DEBUT) / (FIN - DEBUT)) * 100));
  const x = (v: number) => `${pos(v)}%`;
  const types = TYPES.filter((t) => comp.groupes[t]);
  const classement = [...comp.resultats].sort((a, b) => a.hausse_vers_4_5 - b.hausse_vers_4_5);
  const max = Math.max(...classement.map((r) => r.hausse_vers_4_5), 1e-9);
  const sous7 = comp.resultats.filter((r) => r.cet1_apres < comp.seuil_coussin).length;

  return (
    <div className="stress-grille stress-grille-comparer">
      <section className="stress-panneau stress-large" aria-labelledby="stress-titre-comparer">
        <h2 id="stress-titre-comparer" className="sr-only">CET1 avant et après, banque par banque</h2>
        <div className={`stress-duel${types.length === 1 ? " stress-duel-seul" : ""}`}>
          {types.map((t) => {
            const g = comp.groupes[t]!;
            return (
              <div key={t}>
                <small>{LIBELLE_TYPE[t]}, moyenne simple de {g.nb}</small>
                <strong>{pc(g.cet1_apres)}</strong>
                <span className="stress-baisse">{g.points_perdus > 0 ? "▼ " : ""}{points(g.points_perdus)} {g.points_perdus >= 2 ? "perdus" : "perdu"}</span>
                <em>{g.au_dessus_7} sur {g.nb} au-dessus de 7 %</em>
              </div>
            );
          })}
          {comp.phrase && <p>{comp.phrase}</p>}
        </div>

        <div className="stress-corps">
          <div className="stress-legende" aria-hidden="true">
            <span><i className="stress-point stress-point-avant" /> Avant</span>
            <span><i className="stress-point stress-point-apres" /> Après le choc</span>
            <span><i className="stress-trait-seuil" /> Repères 4,5 % et 7 %</span>
          </div>
          {types.map((t) => (
            <div key={t}>
              <p className="stress-groupe">{LIBELLE_TYPE[t]}</p>
              {comp.resultats.filter((r) => r.type === t).map((r) => (
                <button key={r.cle} type="button" className="stress-ligne" onClick={() => ouvrir(r.cle)}
                  aria-label={`${r.banque} : CET1 de ${pc(r.cet1_avant)} à ${pc(r.cet1_apres)}. Simuler cette banque seule.`}>
                  <b>{r.banque}</b>
                  <span className="stress-piste" aria-hidden="true">
                    <i className="stress-seuil" style={{ left: x(comp.seuil_minimum) }} />
                    <i className="stress-seuil" style={{ left: x(comp.seuil_coussin) }} />
                    <i className="stress-tige" style={{ left: `${Math.min(pos(r.cet1_avant), pos(r.cet1_apres))}%`, width: `${Math.abs(pos(r.cet1_avant) - pos(r.cet1_apres))}%` }} />
                    <i className="stress-point stress-point-avant" style={{ left: x(r.cet1_avant) }} />
                    <i className="stress-point stress-point-apres" style={{ left: x(r.cet1_apres) }} />
                  </span>
                  <span className="stress-valeurs"><span className="stress-discret">{pc(r.cet1_avant)}</span> <Statut statut={r.statut} valeur={r.cet1_apres} /></span>
                </button>
              ))}
            </div>
          ))}
          <div className="stress-axe" aria-hidden="true">
            <span />
            <span className="stress-axe-piste">
              {DEBUT < 0.04 && <span style={{ left: x(DEBUT) }}>{nombre(DEBUT * 100, 0)}</span>}
              {DEBUT <= 0 && DEBUT < -0.005 && <span style={{ left: x(0) }}>0</span>}
              <span style={{ left: x(0.045) }}>4,5</span><span style={{ left: x(0.07) }}>7</span>
              <span className="stress-axe-large" style={{ left: x(0.1) }}>10</span><span className="stress-axe-large" style={{ left: x(0.15) }}>15</span>
              <span style={{ left: x(FIN) }}>19 %</span>
            </span>
            <span />
          </div>
          <p className="stress-aide">
            L&apos;axe commence à {nombre(DEBUT * 100, 0)} %{DEBUT > 0 ? ", pas à 0" : ""}. Cliquez sur une banque pour la simuler seule et voir son calcul. Moyennes simples : chaque
            banque compte pour une, quelle que soit sa taille.
          </p>
        </div>
      </section>

      <section className="stress-panneau" aria-labelledby="stress-titre-classement">
        <header className="stress-tete"><h2 id="stress-titre-classement">Pire cas : de la plus fragile à la plus solide</h2></header>
        <div className="stress-corps">
          <p className="stress-compte">
            <b>{sous7}</b> banque{sous7 > 1 ? "s" : ""} sur {comp.resultats.length} sous 7 % dans ce scénario
          </p>
          <ol className="stress-classement">
            {classement.map((r) => (
              <li key={r.cle}>
                <span>{r.banque}</span>
                <strong>{nombre(r.hausse_vers_4_5 * 100, 1)} points</strong>
                <i aria-hidden="true"><em style={{ width: `${(r.hausse_vers_4_5 / max) * 100}%` }} /></i>
              </li>
            ))}
          </ol>
          <p className="stress-aide">
            Hausse des prêts en défaut qui ferait descendre chaque banque à 4,5 % de CET1, avec la LGD de ce scénario ({Math.round(comp.lgd * 100)} %). Plus le chiffre est
            petit, plus la banque est fragile.
          </p>
        </div>
      </section>

      <section className="stress-panneau stress-plein" aria-labelledby="stress-titre-besoins">
        <header className="stress-tete"><h2 id="stress-titre-besoins">Capital à reconstituer, banque par banque</h2></header>
        <table className="stress-parametres stress-calculs">
          <caption className="sr-only">Capital restant après le choc et capital à reconstituer pour revenir à 7 % et à 4,5 %, en milliards de SAR</caption>
          <thead>
            <tr><th scope="col">Banque</th><th scope="col">Capital restant</th><th scope="col">Pour revenir à 7 %</th><th scope="col">Pour revenir à 4,5 %</th></tr>
          </thead>
          <tbody>
            {comp.resultats.map((r) => (
              <tr key={r.cle}>
                <th scope="row">{r.banque}</th>
                <td data-l="Capital restant">{m(r.capital_avant_md)} − {m(r.perte_md)} = <b>{m(r.capital_apres_md)}</b></td>
                <td data-l="Pour 7 %">7 % × {m(r.actifs_ponderes_md)} − {m(r.capital_apres_md)} → <b>{m(r.besoin_7_md)}</b></td>
                <td data-l="Pour 4,5 %">4,5 % × {m(r.actifs_ponderes_md)} − {m(r.capital_apres_md)} → <b>{m(r.besoin_4_5_md)}</b></td>
              </tr>
            ))}
            <tr className="stress-total">
              <th scope="row">Total</th>
              <td data-l="Capital restant">{m(comp.resultats.reduce((x, r) => x + r.capital_apres_md, 0))}</td>
              <td data-l="Pour 7 %"><b>{m(comp.conclusion.besoin_7_md)}</b></td>
              <td data-l="Pour 4,5 %"><b>{m(comp.conclusion.besoin_4_5_md)}</b></td>
            </tr>
          </tbody>
        </table>
        <p className="stress-aide">
          Milliards de SAR. Capital à reconstituer = max(0 ; seuil × actifs pondérés − capital restant) : 0 quand la banque reste au-dessus du seuil.
        </p>
      </section>
    </div>
  );
}
