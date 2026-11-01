export type Role = "apprenant" | "trader" | "formateur" | "admin";
export type Classe = "action" | "crypto" | "matiere" | "indice";

export interface ProfilRisque {
  score: number;
  categorie: string;
  perte_max_toleree_pct: number;
  reponses: Record<string, number>;
}

export interface Utilisateur {
  id: number;
  email: string;
  nom: string;
  role: Role;
  actif: boolean;
  profil_risque: ProfilRisque | null;
  derniere_connexion: string | null;
}

export interface Actif {
  symbole: string;
  nom: string;
  classe: Classe;
  secteur: string;
  devise: string;
  calendrier: string;
  tradable: boolean;
  disponible: boolean;
}

export interface CotationLigne {
  symbole: string;
  prix: number;
  statut: "ouvert" | "ferme";
  origine: string;
  derniere_cloture: number | null;
  reference: number | null;      // base de la variation affichée (marché fermé : la séance d'avant)
}

export interface Horloge {
  maintenant: string;
  facteur: number;
  en_pause: boolean;
  facteurs_predefinis: Record<string, number>;
}

export interface Instantane {
  instant: string;
  termine: boolean;
  horloge: Horloge;
  fenetre: { debut: string; fin: string };
  cotations: CotationLigne[];
  synthetiques: boolean;
  direct: boolean;
  direct_flux: FluxDirect | null;
}

export interface FluxDirect {
  derniere_maj: string | null;
  age_secondes: number | null;
  erreur: string | null;
  nb_symboles: number;
  demo: boolean;
  utilisateurs_en_direct: number;
}

export interface EtatDirect {
  disponible: boolean;
  actif: boolean;
  beta: boolean;
  avertissements: string[];
  flux: FluxDirect | null;
}

export interface Barre {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  en_formation: boolean;
}

export interface Niveau {
  prix: number;
  quantite: number;
}

export interface Carnet {
  symbole: string;
  prix_reference: number;
  spread: number;
  achats: Niveau[];
  ventes: Niveau[];
  synthetique: boolean;
  statut_marche: string;
}

export interface Position {
  symbole: string;
  quantite: number;
  prix_moyen: number;
  prix_marche: number;
  valeur: number;
  pnl_latent: number;
  poids: number;
}

export interface Portefeuille {
  instant: string;
  capital_initial: number;
  cash: number;
  cash_disponible: number;
  valeur_positions: number;
  equity: number;
  pnl_total: number;
  pnl_realise: number;
  pnl_latent: number;
  frais_cumules: number;
  positions: Position[];
}

export interface Ordre {
  id: number;
  symbole: string;
  sens: "achat" | "vente";
  type: "marche" | "limite" | "stop";
  quantite: number;
  prix_limite: number | null;
  prix_stop: number | null;
  statut: "en_attente" | "partiel" | "execute" | "annule" | "rejete";
  quantite_executee: number;
  prix_moyen: number | null;
  declenche: boolean;
  motif: string | null;
  origine: string | null;        // « regle:12 » si l'ordre a été placé par une règle automatique
  cree_le: string | null;
}

export interface Execution {
  ordre_id: number;
  symbole: string;
  sens: "achat" | "vente";
  quantite: number;
  prix: number;
  frais: number;
  instant: string;
}

export interface Question {
  id: string;
  texte: string;
  choix: string[];
}

export interface LigneAudit {
  id: number;
  utilisateur_id: number | null;
  action: string;
  details: Record<string, unknown> | null;
  ip: string | null;
  horodatage: string;
}

export interface PointValeur {
  jour: string;
  equity: number;
  cash: number;
  benchmark: number | null;
}

export interface HistoriqueValeur {
  points: PointValeur[];
  benchmark: string;
  capital_initial: number;
}

export interface Trade {
  instant: string;
  symbole: string;
  quantite: number;
  prix_achat_moyen: number | null;
  prix_vente: number;
  pnl: number;
  frais: number;
  rendement: number | null;
}

export interface PartRepartition {
  libelle: string;
  part: number;
}

export interface Analyse {
  instant: string;
  performance: {
    rendement_total: number | null;
    drawdown_max: number;
    drawdown_courant: number;
    points_courbe: number;
    volatilite_annuelle: number | null;
    rendement_annuel: number | null;
    sharpe: number | null;
    sortino: number | null;
  };
  risque: { var: number; cvar: number; jours: number; niveau: number; var_montant: number; cvar_montant: number } | null;
  concentration: { hhi: number; nb_effectif: number; plus_grosse_position: { symbole: string; part: number } } | null;
  diversification: { score: number; nb_positions: number; nb_marches: number } | null;
  repartition: { marche: PartRepartition[]; secteur: PartRepartition[]; position: PartRepartition[] };
  correlations: { symboles: string[]; matrice: number[][] } | null;
  profil: {
    statut: "profil_absent" | "ok" | "proche" | "depasse";
    categorie?: string;
    perte_tolerance?: number;
    perte_actuelle?: number;
    utilisation?: number | null;
    var95_jour?: number | null;
    var_sur_tolerance?: number | null;
  };
  avertissements: string[];
}

export interface SessionAppareil {
  famille: string;
  debut: string;
  derniere_activite: string;
  ip: string | null;
  agent: string | null;
  courante: boolean;
}

export type CleIndicateur = "sma" | "ema" | "bollinger" | "rsi" | "macd";

export interface Indicateurs {
  symbole: string;
  dates: string[];
  series: Record<string, (number | null)[]>;
  parametres: {
    sma_courte: number; sma_longue: number; ema: number; rsi: number; atr: number;
    bollinger: { n: number; k: number };
    macd: { rapide: number; lente: number; signal: number };
  };
}

export type TypeRegle = "stop_loss" | "take_profit" | "stop_suiveur" | "achat_complementaire";

export interface Regle {
  id: number;
  symbole: string;
  type: TypeRegle;
  seuil: number;                 // fraction signée : −0,30 pour un stop-loss à 30 %
  part: number;                  // fraction de la position concernée
  statut: "active" | "declenchee" | "annulee" | "echec";
  cree_le: string | null;
  declenchee_le: string | null;
  plus_haut: number | null;
  motif: string | null;
  niveau: number | null;         // prix de déclenchement (règles actives)
  prix_moyen: number | null;
}

export interface Alerte {
  code: string;
  niveau: "attention" | "info";
  texte: string;
}

export interface Verification {
  alertes: Alerte[];
  apres: { poids: number; part_liquidites: number; montant: number } | null;
}

// ------------------------------------------------------------------ backtesting
export interface StrategieCatalogue {
  nom: string;
  libelle: string;
  description: string;
  parametres: Record<string, number>;
}

export interface MetriquesBacktest {
  jours: number;
  rendement_total: number | null;
  rendement_annuel: number | null;
  volatilite: number | null;
  sharpe: number | null;
  sortino: number | null;
  drawdown_max: number | null;     // positif : 0,24 = baisse maximale de 24 %
  calmar: number | null;
  taux_reussite: number | null;
  temps_investi: number | null;
  aller_retours: number;
}

export interface ResultatStrategie {
  nom: string;
  libelle: string;
  description: string;
  parametres: Record<string, number>;
  metriques: MetriquesBacktest;
  premiere_moitie: MetriquesBacktest;
  seconde_moitie: MetriquesBacktest;
  courbe: { dates: string[]; valeurs: number[] };   // base 1 au début de la période
  entrees: number;
  signal_actuel: number;                            // 1 = investi à la dernière clôture, 0 = liquidités
}

export interface ResultatBacktest {
  symbole: string;
  debut: string | null;
  fin: string | null;
  cout_bps: number;
  reference: string;
  strategies: ResultatStrategie[];
  avertissements: string[];
}

// ------------------------------------------------------------------ crises et actualités
export type PorteeScenario = "tous" | "classe" | "secteur" | "actifs";

export interface Scenario {
  id: number;
  nom: string;
  description: string;
  date_debut: string;
  portee_type: PorteeScenario;
  portee_valeurs: string[];
  choc_pct: number;
  recuperation_pct: number;
  duree_recuperation_jours: number;
  actif: boolean;
  nb_actifs?: number;
}

export interface ListeScenarios {
  scenarios: Scenario[];
  secteurs: string[];
  classes: string[];
  actifs: { symbole: string; nom: string }[];
  debut: string;
  fin: string;
}

export interface ModeleScenario {
  cle: string;
  nom: string;
  description: string;
  portee_type: PorteeScenario;
  portee_valeurs: string[];
  choc_pct: number;
  recuperation_pct: number;
  duree_recuperation_jours: number;
  annonce: string;
}

export interface SentimentTexte {
  score: number;
  etiquette: "positif" | "negatif" | "neutre";
  mots_positifs: string[];
  mots_negatifs: string[];
}

export interface ImpactActualite {
  symbole: string;
  rendement_1j: number | null;
  rendement_5j: number | null;
}

export interface Actualite {
  id: number;
  date: string;
  titre: string;
  texte: string;
  symboles: string[];
  type_source: "historique" | "fictif" | "scenario" | "import";
  note_source: string;
  actif: boolean;
  scenario_id: number | null;
  sentiment: SentimentTexte;
  impact?: ImpactActualite[];
}

export interface EtudeSentiment {
  nb_actualites: number;
  nb_non_neutres: number;
  concordance: number | null;
  correlation: number | null;
  avertissement: string;
}

// ------------------------------------------------------------------ risque de crédit
export interface ContributionZ { ratio: string; libelle: string; valeur: number; coefficient: number; contribution: number }
export interface ResultatZ { modele: string; nom_modele: string; z: number; zone: "sain" | "grise" | "detresse"; seuil_sain: number; seuil_detresse: number; contributions: ContributionZ[] }
export interface ExempleZ { nom: string; fictive: boolean; comptes: Record<string, number> }
export interface VariablePD { nom: string; libelle: string; aide: string; min: number; max: number; mediane: number; coefficient: number }
export interface ModelePDInfo {
  source: "kaggle" | "synthetique";
  taux_defaut: number;
  metriques: { auc_logistique: number; auc_arbres_boostes: number; brier: number; brier_reference: number; n_apprentissage: number; n_test: number;
    calibration: { groupe: number; pd_moyenne: number; taux_observe: number }[] };
  variables: VariablePD[];
  avertissement: string;
}
export interface ResultatPD {
  pd: number; taux_defaut_moyen: number; logit: number; intercept: number; source: string;
  contributions: { variable: string; libelle: string; valeur: number; contribution: number }[];
}

// ------------------------------------------------------------------ stress tests bancaires
export interface BanqueStress { nom: string; type: "conventionnelle" | "islamique"; actifs: number; cet1: number; [cle: string]: unknown }
export interface ListeBanques { banques: BanqueStress[]; groupes: { cle: string; libelle: string }[]; seuil_minimum: number; seuil_coussin: number; avertissement: string }
export interface FenetreChoc { cle: string; nom: string; debut: string; fin: string; chocs: Record<string, number | null>; notes: string[] }
export interface CanalStress { cle: string; libelle: string; perte: number; explication: string }
export interface ResultatStress {
  banque: string; type: string; ratio_avant: number; ratio_apres: number; ratio_avec_resultat: number; variation_points: number; perte_brute: number; perte_supportee: number;
  resultat_periode: number; statut: "ok" | "sous_coussin" | "sous_minimum"; canaux: CanalStress[];
}
export interface LigneComparaison { banque: string; type: string; ratio_avant: number; ratio_apres: number; variation_points: number; statut: ResultatStress["statut"] }
export interface Comparaison { banques: LigneComparaison[]; par_type: Record<string, { nb: number; variation_moyenne: number; pire: number }> }
export interface ChocInverse { choc: number | null; message: string; seuil: number }
export interface ComparaisonIA {
  comparaison: { cle: string; nom: string; r2: number; erreur_absolue_moyenne: number }[]; meilleur: string; ecart_type_cible: number; n: number;
  importance: { variable: string; libelle: string; importance: number }[]; avertissement: string;
}
export interface ExplicationIA {
  modele: string; prediction_points: number; reference_structurelle_points: number; note: string;
  attributions: { variable: string; libelle: string; valeur: number; effet: number }[];
}

// ------------------------------------------------------------------ actuariat
export interface VariableTarif { nom: string; libelle: string; min?: number; max?: number; choix?: string[] }
export interface ModeleTarifInfo {
  source: "kaggle" | "synthetique"; avertissement: string; variables: VariableTarif[];
  metriques: { deviance_poisson: number; deviance_poisson_reference: number; deviance_gamma: number; deviance_gamma_reference: number; frequence_moyenne: number; cout_moyen: number; n_contrats: number; n_sinistres: number };
}
export interface FacteurTarif { variable: string; libelle: string; valeur: number; facteur: number }
export interface ResultatPrime {
  frequence_annuelle: number; cout_moyen: number; prime_pure: number; marge_securite: number; frais: number; prime_commerciale: number; probabilite_sinistre: number;
  facteurs_frequence: FacteurTarif[]; facteurs_cout: FacteurTarif[];
}
export interface ResultatCL {
  facteurs: number[]; triangle_complete: number[][]; provision_totale: number; ultime_total: number; limites: string;
  annees: { annee: number; dernier_connu: number; ultime: number; provision: number }[];
}

// ------------------------------------------------------------------ formation
export interface ResumeLecon { id: string; titre: string; niveau: string; minutes: number; resume: string; nb_questions: number; active: boolean; tentatives: number; meilleur_score: number | null; reussie: boolean }
export interface ListeLecons { lecons: ResumeLecon[]; progression: { lecons_actives: number; lecons_reussies: number; score_moyen: number | null; tentatives: number } }
export interface DetailLecon extends ResumeLecon {
  sections: { titre: string; texte: string }[];
  exercices: { texte: string; lien: string; libelle: string }[];
  questions: { index: number; enonce: string; choix: string[] }[];
  seuil_reussite: number;
}
export interface CorrectionLecon {
  score: number; bonnes: number; total: number; reussie: boolean; seuil_reussite: number;
  corrections: { index: number; juste: boolean; repondu: number | null; bonne_reponse: number; explication: string }[];
}
export interface LigneLigue { rang: number; nom: string; rendement: number; drawdown: number; score: number; date_simulee: string; points: number; valeur: number }
export interface LigneClasse {
  id: number; nom: string; role: string; profil_risque: string | null; lecons_reussies: number; lecons_actives: number; score_moyen: number | null;
  portefeuille: { rendement: number; drawdown: number; score: number; date_simulee: string; points: number } | null;
}

// ------------------------------------------------------------------ intelligence artificielle sur les marchés
export interface PredictionIA {
  symbole: string; n_test: number; proba_hausse: number; dans_le_bruit: boolean; conclusion: string; dernier_jour: string; meilleur: string;
  resultats: { cle: string; nom: string; precision: number; marge: number }[];
  contributions: { variable: string; libelle: string; valeur: number; contribution: number }[];
}
export interface AnomaliesIA { nb: number; fenetre: number; seuil: number; note: string; anomalies: { jour: string; rendement: number; score_rendement: number; score_volume: number; type: string }[] }
export interface RegimesIA { regime_actuel: string; depuis_jours: number; note: string; regimes: { regime: string; part: number; rendement_annualise: number; volatilite_annualisee: number }[] }
export interface MetriquesAgent { rendement_total: number | null; rendement_annuel: number | null; volatilite: number | null; sharpe: number | null; drawdown_max: number | null; temps_investi: number | null; aller_retours: number }
export interface AgentIA {
  note: string; cout_bps: number; entrainement: { debut: string; fin: string; jours: number }; test: { debut: string; fin: string; jours: number };
  agent: MetriquesAgent; achat_conservation: MetriquesAgent; politique: { etat: string; hors_marche: string; investi: string }[];
}
export interface OptimiseurIA {
  note: string; jours: number; recommandations: string[]; volatilite_actuelle: number; volatilite_variance_minimale: number; volatilite_parite_risque: number;
  lignes: { symbole: string; poids_actuel: number; contribution_risque: number; poids_variance_minimale: number; poids_parite_risque: number }[];
}

// ------------------------------------------------------------------ administration : statistiques
export interface StatsAdmin {
  utilisateurs: { total: number; actifs: number; par_role: Record<string, number>; nouveaux_7_jours: number; connectes_7_jours: number };
  trading: { ordres_par_statut: Record<string, number>; executions: number; frais_totaux: number; comptes_avec_historique: number; regles_actives: number; actifs_les_plus_echanges: { symbole: string; executions: number }[] };
  formation: { id: string; titre: string; reussites: number; score_moyen: number | null }[];
  crises: { scenarios: number; scenarios_actifs: number; actualites: number; actualites_fictives: number };
  donnees: { actifs_charges: number; actifs_total: number; debut: string; fin: string; synthetiques: boolean; direct_actif: boolean; direct_demo: boolean; flux_direct: FluxDirect | null };
  modeles: { cle: string; titre: string; present: boolean; source?: string; mesure?: string; valeur?: number | null; route_entrainement: string }[];
  parametres: { capital_initial: number; facteur_vitesse_par_defaut: number; ticks_par_barre: number; frais_points_de_base: Record<string, number>; ecart_points_de_base: Record<string, number>;
    duree_jeton_acces_minutes: number; duree_session_jours: number; echecs_avant_verrouillage: number; note: string };
}
export interface PerformanceAdmin { id: number; nom: string; email: string; role: string; actif: boolean; profil_risque: string | null; portefeuille: { rendement: number; drawdown: number; score: number; date_simulee: string; points: number; valeur: number } | null }
