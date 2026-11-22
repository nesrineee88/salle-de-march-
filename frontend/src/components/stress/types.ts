/** Types du stress de crédit sur les banques réelles (routes /api/v1/stress/reelles/*). */

export type TypeBanque = "islamique" | "conventionnelle";
export type StatutCet1 = "ok" | "sous_coussin" | "sous_minimum";
export type CleScenario = "central" | "adverse" | "severe" | "extreme";

export interface Scenario {
  cle: CleScenario;
  nom: string;
  quantile: number | null;
  phrase: string;
}

/** Ce que le serveur envoie pour choisir une banque : les chiffres bruts restent côté serveur. */
export interface BanqueChoix {
  cle: string;
  nom: string;
  type: TypeBanque;
  pays: string;
  date_arrete: string;
  devise: string;
  source_url: string;
  page_km1: number;
  page_cr1: number;
  date_collecte: string;
  statut: "a_relire" | "relu";
}

export type CleType = "recession" | "defauts" | "actifs" | "combine";
export type CleIntensite = "moderee" | "severe" | "extreme";
export type StatutOrigine = "publiee" | "hypothese" | "mesuree" | "manuel";

/** Un levier du scénario : sa valeur, d'où elle vient, pourquoi. `origine` vide : levier non utilisé. */
export interface Levier {
  valeur: number | null;
  origine: string | null;
  statut: StatutOrigine | null;
  justification: string | null;
}

export interface Parametres {
  type: CleType;
  nom: string;
  intensite: CleIntensite;
  nom_intensite: string;
  quantile: Levier;
  hausse: Levier;
  lgd: Levier;
}

export interface Catalogue {
  types: { cle: CleType; nom: string; phrase: string; leviers: string; intensites: Record<CleIntensite, Parametres> }[];
  intensites: { cle: CleIntensite; nom: string; quantile: number; lecture: string }[];
  non_calculables: { nom: string; manque: string }[];
  lgd_min: number;
  lgd_max: number;
  lgd_base: number;
}

export interface ListeBanquesReelles {
  banques: BanqueChoix[];
  catalogue: Catalogue;
  resume: { nb: number; dates_arrete: string[]; pays: string[]; devises: string[]; nb_par_type: Record<TypeBanque, number>; nb_relues: number };
  scenarios: Scenario[];
  lgd_defaut: number;
  lgd_min: number;
  lgd_max: number;
  seuil_minimum: number;
  seuil_coussin: number;
  limites: string[];
  sources_limites: Record<string, string>;
  commande_collecte: string;
}

export interface ResultatBanque {
  cle: string;
  banque: string;
  type: TypeBanque;
  scenario: string;
  lgd: number;
  quantile: number | null;
  hausse_ajoutee: number;
  parametres: Parametres | null;
  pd_crise: number;
  canaux: { cle: string; libelle: string; perte: number; perte_md: number }[];
  cet1_avant: number;
  cet1_publie: number;
  cet1_apres: number;
  variation_points: number;
  pd_avant: number;
  pd_stressee: number;
  hausse_defauts: number;
  correlation: number;
  perte: number;
  perte_md: number;
  capital_avant_md: number;
  capital_apres_md: number;
  actifs_ponderes_md: number;
  prets_bruts_md: number;
  prets_defaut_md: number;
  statut: StatutCet1;
  hausse_vers_4_5: number;
  hausse_vers_7: number;
  devise: string;
  barres: { libelle: string; valeur_md: number }[];
  besoin_4_5_md: number;
  besoin_7_md: number;
  conclusion: string;
}

export interface Groupe {
  nb: number;
  cet1_avant: number;
  cet1_apres: number;
  points_perdus: number;
  au_dessus_7: number;
}

export interface Comparaison {
  scenario: string;
  lgd: number;
  parametres?: Parametres;
  resultats: ResultatBanque[];
  groupes: Partial<Record<TypeBanque, Groupe>>;
  phrase: string;
  conclusion: { texte: string; besoin_7_md: number; besoin_4_5_md: number; sous_7: number; sous_4_5: number; pire: string };
  seuil_minimum: number;
  seuil_coussin: number;
}

export const STATUTS: Record<StatutCet1, { icone: string; mot: string; classe: string }> = {
  ok: { icone: "✓", mot: "Au moins 7 %", classe: "ok" },
  sous_coussin: { icone: "!", mot: "Entre 4,5 et 7 %", classe: "coussin" },
  sous_minimum: { icone: "✕", mot: "Sous 4,5 %", classe: "minimum" },
};

export const LIBELLE_TYPE: Record<TypeBanque, string> = {
  islamique: "Islamiques",
  conventionnelle: "Conventionnelles (avec guichets islamiques)",
};

export const TYPE_COURT: Record<TypeBanque, string> = { islamique: "Islamique", conventionnelle: "Conventionnelle" };

export const STATUT_ORIGINE: Record<StatutOrigine, string> = {
  publiee: "Référence publiée", hypothese: "Hypothèse", mesuree: "Mesurée", manuel: "Réglage manuel",
};

/** « 2025-12-31 » devient « 31/12/2025 ». */
export const dateFr = (iso: string) => iso.split("-").reverse().join("/");
