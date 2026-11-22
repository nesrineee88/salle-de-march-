"use client";

import { nombre } from "@/lib/format";
import { LienSource, md, pc, pcCourt, pcSeuil, points, Statut } from "./Communs";
import { dateFr, type BanqueChoix, type ResultatBanque } from "./types";

/** Résultat de la simulation pour UNE banque : avant et après, le calcul avec ses chiffres, la perte par canal, le pire cas. */
export default function Detail({ r, banque }: { r: ResultatBanque; banque: BanqueChoix }) {
  const m = (v: number) => nombre(v, 2);
  const lgd = pcCourt(r.lgd);
  const max = Math.max(...r.barres.map((x) => Math.abs(x.valeur_md)), 1e-9);
  const p = r.parametres;
  const pertes = r.barres.slice(1, -1);

  return (
    <div className="stress-grille">
      <section className="stress-panneau" aria-labelledby="stress-titre-fiche">
        <div className="stress-fiche">
          <h2 id="stress-titre-fiche">{banque.nom}{p ? `, ${p.nom.toLowerCase()} ${p.nom_intensite.toLowerCase()}` : ""}</h2>
          <p className="stress-grand">{pcSeuil(r.cet1_apres)}<small>CET1 après le choc</small></p>
          <Statut statut={r.statut} />
          <dl className="stress-lignes">
            <div><dt>CET1 avant</dt><dd>{pc(r.cet1_avant)}</dd></div>
            <div><dt>Variation</dt><dd>{r.variation_points < 0 ? "▼ −" : ""}{points(Math.abs(r.variation_points))}</dd></div>
            <div><dt>Prêts en défaut : avant, puis après</dt><dd>{pc(r.pd_avant)} → {pc(r.pd_stressee)}</dd></div>
            <div><dt>Perte de crédit</dt><dd>{md(r.perte_md)} SAR</dd></div>
          </dl>
          <p className="stress-note">
            <b>Pire cas :</b> avec une LGD de {lgd}, il faudrait {nombre(r.hausse_vers_4_5 * 100, 1)} points de prêts en défaut en plus pour
            que cette banque descende à 4,5 %, et {nombre(r.hausse_vers_7 * 100, 1)} points pour passer sous 7 %.
          </p>
          <p className="stress-aide">Chiffres du rapport Pilier 3 au {dateFr(banque.date_arrete)} : tableau KM1 pour le capital, CR1 pour les prêts.</p>
          <LienSource url={banque.source_url} pages={[banque.page_km1, banque.page_cr1]} />
        </div>
      </section>

      <section className="stress-panneau stress-large" aria-labelledby="stress-titre-calcul">
        <header className="stress-tete">
          <h2 id="stress-titre-calcul">Le calcul, avec les chiffres de {banque.nom}</h2>
          <span className="stress-tag stress-tag-accent">Explication exacte</span>
        </header>
        <div className="stress-corps">
          <ol className="stress-formule">
            <li><span>PD de départ</span> = défaut ÷ prêts bruts = {m(r.prets_defaut_md)} ÷ {m(r.prets_bruts_md)} = <b>{pc(r.pd_avant)}</b></li>
            {r.quantile !== null && (
              <li><span>PD de crise</span> = Vasicek au quantile {pcCourt(r.quantile)}, corrélation {pc(r.correlation)} = <b>{pc(r.pd_crise)}</b></li>
            )}
            {r.hausse_ajoutee > 0 && (
              <li><span>PD stressée</span> = {r.quantile !== null ? "PD de crise" : "PD de départ"} + {nombre(r.hausse_ajoutee * 100, 0)} points = <b>{pc(r.pd_stressee)}</b></li>
            )}
            <li><span>Perte</span> = {m(r.prets_bruts_md)} × ({pc(r.pd_stressee)} − {pc(r.pd_avant)}) × {lgd} = <b>{m(r.perte_md)} Md</b></li>
            <li><span>CET1 après</span> = ({m(r.capital_avant_md)} − {m(r.perte_md)}) ÷ {m(r.actifs_ponderes_md)} = <b>{pcSeuil(r.cet1_apres)}</b></li>
          </ol>
          <p className="stress-aide">Montants en milliards de riyals (SAR). Chaque prêt ne fait défaut qu&apos;une fois et ne perd qu&apos;une fois : une seule PD, une seule LGD.</p>

          <h3 className="stress-sous-titre">Où part le capital</h3>
          <ul className="stress-barres">
            {r.barres.map((x, i) => (
              <li key={x.libelle}>
                <span>{x.libelle}</span>
                <strong>{x.valeur_md < 0 ? "−" : ""}{m(Math.abs(x.valeur_md))} Md</strong>
                <i aria-hidden="true"><em data-sens={i === 0 ? "depart" : i === r.barres.length - 1 ? "reste" : "perte"} style={{ width: `${(Math.abs(x.valeur_md) / max) * 100}%` }} /></i>
              </li>
            ))}
          </ul>
          <p className="stress-aide">
            {m(r.barres[0].valeur_md)}{pertes.map((x) => ` − ${m(-x.valeur_md)}`).join("")} = {m(r.barres[r.barres.length - 1].valeur_md)}, à
            l&apos;arrondi près : la somme tombe juste.
            {pertes.length > 1 && " La crise et les défauts en plus sont comptés à 45 % de LGD ; la ligne « garanties » ajoute l'écart de LGD sur tous les nouveaux défauts."}
          </p>

          <h3 className="stress-sous-titre">Capital à reconstituer</h3>
          <ol className="stress-formule">
            <li><span>Capital restant</span> = {m(r.capital_avant_md)} − {m(r.perte_md)} = <b>{m(r.capital_apres_md)} Md</b></li>
            <li><span>Pour revenir à 7 %</span> = max(0 ; 7 % × {m(r.actifs_ponderes_md)} − {m(r.capital_apres_md)}) = <b>{m(r.besoin_7_md)} Md</b></li>
            <li><span>Pour revenir à 4,5 %</span> = max(0 ; 4,5 % × {m(r.actifs_ponderes_md)} − {m(r.capital_apres_md)}) = <b>{m(r.besoin_4_5_md)} Md</b></li>
          </ol>

          <h3 className="stress-sous-titre">Pourquoi c&apos;est le pire cas</h3>
          <p className="stress-formule-ligne">
            Hausse qui casse = (capital − 4,5 % × actifs pondérés) ÷ (prêts × LGD) = ({m(r.capital_avant_md)} − 4,5 % × {m(r.actifs_ponderes_md)}) ÷ ({m(r.prets_bruts_md)} × {lgd}) = <b>{nombre(r.hausse_vers_4_5 * 100, 2)} points</b>
          </p>
          <p className="stress-aide">
            Ce n&apos;est pas un scénario choisi : c&apos;est le calcul à l&apos;envers. Dans ce scénario, les défauts montent de{" "}
            {nombre(r.hausse_defauts * 100, 2)} points. Plus le chiffre du pire cas est grand, plus la banque résiste.
          </p>
        </div>
      </section>
    </div>
  );
}
