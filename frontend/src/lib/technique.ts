/** Analyse technique : unités de temps, outils affichables et tracés manuels (mémorisés dans ce navigateur, par actif). */
import type { Barre, Bougie, Dessin, Unite } from "./types";

export const UNITES: { cle: Unite; libelle: string }[] = [
  { cle: "1min", libelle: "1 min" }, { cle: "5min", libelle: "5 min" }, { cle: "15min", libelle: "15 min" },
  { cle: "1h", libelle: "1 h" }, { cle: "1j", libelle: "1 jour" },
];

export type Outil = "volumes" | "niveaux" | "tendances" | "fibonacci";
export const OUTILS: { cle: Outil; libelle: string; aide: string }[] = [
  { cle: "volumes", libelle: "Volumes", aide: "Nombre de titres échangés par séance (barres en bas du graphique). Disponible en unité 1 jour seulement : les données ne contiennent pas de volume intrajournalier." },
  { cle: "niveaux", libelle: "Supports et résistances", aide: "Zones où le prix s'est retourné au moins deux fois. Support : sous le prix actuel (pression acheteuse passée) ; résistance : au-dessus (pression vendeuse passée). Une flèche marque une cassure possible : la clôture a traversé la zone." },
  { cle: "tendances", libelle: "Lignes de tendance", aide: "Droite passant par les deux derniers creux montants (tendance haussière) ou les deux derniers sommets descendants (tendance baissière), prolongée jusqu'à aujourd'hui." },
  { cle: "fibonacci", libelle: "Fibonacci", aide: "Retracements de Fibonacci entre le plus haut et le plus bas de la période affichée : 23,6 %, 38,2 %, 50 %, 61,8 %, 78,6 %. Des repères où un repli s'arrête parfois, sans aucune garantie." },
];

/** Bougie journalière de /historique au format du graphique (temps en secondes UTC). */
export const barreEnBougie = (b: Barre): Bougie => ({ ...b, t: Date.parse(`${b.date}T00:00:00Z`) / 1000 });

const cle = (symbole: string) => `sdm.dessins.${symbole}`;

export function lireDessins(symbole: string): Dessin[] {
  try {
    const brut = localStorage.getItem(cle(symbole));
    const l = brut ? (JSON.parse(brut) as unknown) : null;
    return Array.isArray(l) ? (l as Dessin[]).filter((d) => d && (d.type === "horizontal" || d.type === "tendance")) : [];
  } catch {
    return [];
  }
}

export function enregistrerDessins(symbole: string, d: Dessin[]): void {
  try { localStorage.setItem(cle(symbole), JSON.stringify(d)); } catch { /* stockage indisponible : les tracés ne seront pas mémorisés */ }
}
