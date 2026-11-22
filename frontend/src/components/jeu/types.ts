/** Ce que le serveur du jeu envoie : jamais rien au-delà de la séance atteinte. */
export type Acte = "tenir" | "reduire" | "renforcer" | "sortir";
export type ModeJeu = "solo" | "mystere" | "jury";
export type CleDifficulte = "spectateur" | "acteur" | "realisateur";

export interface Plan { perte_max: number; reaction: Acte }
export interface OptionActe { acte: Acte; nom: string; detail: string }

export interface AccueilJeu {
  films: {
    id: string; titre: string; sujet: string; accroche: string; intensite: number;
    disponible: boolean; indisponible: string | null; meilleur: number | null;
  }[];
  mystere: { disponible: boolean; meilleur: number | null; classable: boolean };
  difficultes: { cle: CleDifficulte; nom: string; detail: string }[];
  reactions: OptionActe[];
  pertes_max: number[];
  capital: number;
  reprise: { id: string; titre: string; mode: ModeJeu } | null;
  classement: { rang: number; nom: string; note: number; parties: number }[];
}

export interface ActifPartie {
  rang: number;
  nom: string;
  detail: string | null;
  ouvertures: number[];
  clotures: number[];                // base 100, jusqu'à la séance atteinte seulement
  valeur: number;
  en_attente: ("achat" | "vente")[];
}

export interface Montage {
  arret: number;
  jour: number;
  date: string | null;
  evenement: string | null;
  acte: Acte;
  nom: string;
  autres: { acte: Acte; nom: string; valeur: number; ecart: number; courbe: number[] }[];
}

export interface Generique {
  note: number | null;               // null : le jury décide, hors classement
  prix: string;
  profil: string;
  valeur: number;
  double: number;
  rendement: number;
  pire_baisse: number;
  frais: number;
  resultat: number;
  protection: number;
  plan: { note: number; regles: { regle: string; note: number; attendu: string; fait: string; limite_franchie: boolean }[] } | null;
  poids: { resultat: number; protection: number; plan: number };
  plafonnee: boolean;
  plafond: number;
  courbe: number[];
  courbe_double: number[];
  montage: Montage[];
  a_deviner: { film: string; sujet: string }[] | null;
  devine: { juste: boolean; sujet: string } | null;
  lecon: string | null;
  classee: boolean;
}

export interface Partie {
  id: string;
  version: number;
  mode: ModeJeu;
  statut: "en_cours" | "terminee" | "abandonnee";
  seance: number;
  titre: string;
  sujet: string;
  film: string | null;
  date: string | null;
  difficulte: { cle: CleDifficulte; nom: string; ms: number; pause: boolean; frais: number };
  plan: Plan | null;
  capital: number;
  mise: number;
  vedette: number;
  actifs: ActifPartie[];
  liquidites: number;
  engage: number;
  valeur: number;
  double: number;
  baisse: number;
  peur: number;
  peur_mesure: { nom: string; valeur: number; unite: "points" | "part" } | null;
  sous_titre: string;
  arret: { numero: number; question: string; evenement: string | null; options: OptionActe[]; conseil: string | null } | null;
  arrets_passes: number[];
  classable: boolean | null;         // null : encore masqué
  generique: Generique | null;
}
