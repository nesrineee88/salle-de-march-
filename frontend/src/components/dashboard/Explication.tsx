"use client";

import { dateCourte, entier, nombre, pct, pctSigne } from "@/lib/format";
import { NOMS_FAMILLES, NOMS_NIVEAUX, raisonNiveau } from "@/lib/risque";
import type { SyntheseTableau } from "@/lib/types";
import Dialogue from "../ui/Dialogue";

export type Sujet = "valeur" | "retour" | "risque" | "var";

export function Info({ sujet, ouvrir }: { sujet: Sujet; ouvrir: (s: Sujet) => void }) {
  return <button type="button" className="dash-info" onClick={() => ouvrir(sujet)} aria-label="Comment ce chiffre est calculé">?</button>;
}

export default function Explication({ sujet, synthese, cash, fermer }: { sujet: Sujet; synthese: SyntheseTableau; cash: number; fermer: () => void }) {
  const s = synthese.suivi, r = synthese.niveau_risque, v = synthese.risque;

  if (sujet === "valeur") {
    return (
      <Dialogue titre="Valeur totale" fermer={fermer}>
        <p>Ce que vaut votre portefeuille si vous comptez tout au dernier cours connu.</p>
        <p className="seance-formule">{entier(cash)} de liquidités + {entier(s.valeur - cash)} de positions = {entier(s.valeur)} USD</p>
        <p className="seance-petit">Les frais d’une vente future ne sont pas déduits.</p>
      </Dialogue>
    );
  }
  if (sujet === "retour") {
    return (
      <Dialogue titre="Total return" fermer={fermer}>
        <p>Tout ce que vous avez gagné ou perdu depuis votre première transaction : latent, réalisé et frais compris.</p>
        <p className="seance-formule">{entier(s.valeur)} ÷ {entier(s.capital_initial)} − 1 = {pctSigne(s.rendement_total)}</p>
        <p className="seance-petit">
          {s.a_commence ? `Première transaction le ${dateCourte(s.debut)}. ` : ""}
          Les cours des actions sont ajustés des dividendes : c’est pourquoi le S&amp;P 500 de référence les inclut aussi. Les autres indices ne les incluent pas.
        </p>
      </Dialogue>
    );
  }
  if (sujet === "var") {
    return (
      <Dialogue titre="Perte d’un mauvais jour (VaR 95 %)" fermer={fermer}>
        <p>La perte qu’un jour sur 20 a dépassée dans le passé, avec vos poids actuels.</p>
        <p className="seance-formule">{v ? `${pct(v.var, 2)} × ${entier(s.valeur)} = ${entier(v.var_montant)} USD` : "Il faut au moins 30 séances communes."}</p>
        <p className="seance-petit">Ce n’est pas une perte maximale : au-delà, la CVaR donne la perte moyenne.</p>
      </Dialogue>
    );
  }
  return (
    <Dialogue titre="Comment le niveau de risque est calculé" fermer={fermer}>
      <p>Cinq indicateurs notés sur 100, une moyenne pondérée, puis un plancher de sécurité.</p>
      {r.familles.length > 0 && (
        <div className="dash-defile">
          <table className="dash-table dash-table-calcul">
            <thead><tr><th>Indicateur</th><th>Valeur</th><th>Seuils</th><th>Note</th><th>Poids</th><th>Points</th></tr></thead>
            <tbody>
              {r.familles.map((f) => (
                <tr key={f.cle}>
                  <td>{NOMS_FAMILLES[f.cle]}{f.nature === "secteur" ? " (secteur)" : ""}</td>
                  <td>{pct(f.valeur)}</td>
                  <td>{nombre(f.seuil_modere * 100, f.seuil_modere < 0.05 ? 1 : 0)} / {nombre(f.seuil_eleve * 100, f.seuil_eleve < 0.05 ? 1 : 0)}</td>
                  <td>{nombre(f.note, 0)}</td><td>{pct(f.poids, 0)}</td><td>{nombre(f.points, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="seance-formule">{NOMS_NIVEAUX[r.niveau]}{r.score !== null ? `, ${nombre(r.score, 1)} sur 100` : ""}</p>
      <p>{raisonNiveau(r)}</p>
      <p className="seance-petit">
        Score au-dessus de 33 : modéré. Au-dessus de 67 : élevé. Un indicateur au-dessus de 67 donne au moins Modéré, à 83 ou plus il impose Élevé.
        {r.jours > 0 && ` Mesuré sur ${r.jours} séances.`} Seuils pédagogiques, sans valeur réglementaire. Ce calcul ne prévoit rien : après une année calme, tout paraît peu risqué.
      </p>
    </Dialogue>
  );
}
