import { pct } from "./format";
import type { CleFamille, NiveauRisque, SyntheseTableau } from "./types";

export const NOMS_NIVEAUX: Record<NiveauRisque, string> = {
  aucun: "Aucune position",
  incomplet: "Calcul incomplet",
  faible: "Faible",
  modere: "Modéré",
  eleve: "Élevé",
};

export const NOMS_FAMILLES: Record<CleFamille, string> = {
  volatilite: "Volatilité",
  var: "VaR 95 %",
  cvar: "CVaR 95 %",
  drawdown: "Maximum drawdown",
  concentration: "Concentration",
};

export const RANG_NIVEAU = ["faible", "modere", "eleve"] as const;

/** La phrase qui explique le niveau. */
export function raisonNiveau(r: SyntheseTableau["niveau_risque"]): string {
  if (r.niveau === "aucun") return "Le niveau sera calculé après votre premier achat.";
  const concentration = r.familles.find((f) => f.cle === "concentration");
  if (r.niveau === "incomplet") {
    return `Il faut 30 séances communes à vos actifs.${concentration ? ` Concentration connue : ${pct(concentration.valeur)} sur ${concentration.libelle}.` : ""}`;
  }
  if (r.plancher?.releve) {
    const detail = r.plancher.cle === "concentration" && concentration ? ` (${concentration.libelle}, ${pct(concentration.valeur)})` : "";
    return `Relevé par le plancher de sécurité : ${NOMS_FAMILLES[r.plancher.cle].toLowerCase()}${detail}.`;
  }
  const principal = r.familles.reduce((a, b) => ((b.points ?? 0) > (a.points ?? 0) ? b : a));
  return `Ce qui pèse le plus : ${NOMS_FAMILLES[principal.cle].toLowerCase()}, ${pct(principal.valeur)}.`;
}
