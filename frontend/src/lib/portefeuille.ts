/** Calculs purs des visuels du portefeuille (aucun appel réseau, aucun état). Montants en USD, parts en fractions. */
import type { PointValeur, Portefeuille } from "./types";

// ----------------------------------------------------------------------------- carte des positions (treemap)
export interface Tuile<T> { item: T; x: number; y: number; w: number; h: number }

/** Pire rapport largeur/hauteur d'une rangée de surfaces posée le long d'un côté de longueur `cote`. */
function pireRapport(surfaces: number[], cote: number): number {
  const s = surfaces.reduce((a, b) => a + b, 0);
  const max = Math.max(...surfaces), min = Math.min(...surfaces);
  return Math.max((cote * cote * max) / (s * s), (s * s) / (cote * cote * min));
}

/** Treemap « squarifié » (Bruls, Huizing, van Wijk, 2000) : surface de chaque tuile proportionnelle à sa valeur,
 *  tuiles aussi carrées que possible. Les valeurs nulles ou négatives sont ignorées. */
export function squarifier<T>(elements: { valeur: number; item: T }[], largeur: number, hauteur: number): Tuile<T>[] {
  const positifs = elements.filter((e) => e.valeur > 0).sort((a, b) => b.valeur - a.valeur);
  const total = positifs.reduce((s, e) => s + e.valeur, 0);
  if (total <= 0 || largeur <= 0 || hauteur <= 0) return [];
  const echelle = (largeur * hauteur) / total;
  const restants = positifs.map((e) => ({ item: e.item, surface: e.valeur * echelle }));
  const sortie: Tuile<T>[] = [];
  let x = 0, y = 0, w = largeur, h = hauteur;
  let rangee: typeof restants = [];

  const poser = () => {
    const s = rangee.reduce((a, r) => a + r.surface, 0);
    if (w >= h) {                         // colonne à gauche, le long de la hauteur (côté le plus court)
      const lw = s / h;
      let yy = y;
      for (const r of rangee) { const rh = r.surface / lw; sortie.push({ item: r.item, x, y: yy, w: lw, h: rh }); yy += rh; }
      x += lw; w -= lw;
    } else {                              // rangée en haut, le long de la largeur
      const rh = s / w;
      let xx = x;
      for (const r of rangee) { const rw = r.surface / rh; sortie.push({ item: r.item, x: xx, y, w: rw, h: rh }); xx += rw; }
      y += rh; h -= rh;
    }
    rangee = [];
  };

  while (restants.length > 0) {
    const cote = Math.min(w, h);
    const suivant = restants[0];
    const avec = [...rangee, suivant].map((r) => r.surface);
    if (rangee.length === 0 || pireRapport(avec, cote) <= pireRapport(rangee.map((r) => r.surface), cote)) {
      rangee.push(suivant);
      restants.shift();
    } else {
      poser();
    }
  }
  if (rangee.length) poser();
  return sortie;
}

// ----------------------------------------------------------------------------- cascade du résultat
export interface Marche { libelle: string; debut: number; fin: number; type: "total" | "hausse" | "baisse"; aide: string }

/** Cascade exacte : valeur actuelle = capital initial + réalisé + latent − frais (le réalisé est hors frais). */
export function cascade(pf: Portefeuille): Marche[] {
  const c = pf.capital_initial;
  const a = c + pf.pnl_realise;
  const b = a + pf.pnl_latent;
  const d = b - pf.frais_cumules;
  const sens = (v: number): Marche["type"] => (v >= 0 ? "hausse" : "baisse");
  return [
    { libelle: "Capital de départ", debut: 0, fin: c, type: "total", aide: "L'argent virtuel reçu au départ." },
    { libelle: "Gains et pertes réalisés", debut: c, fin: a, type: sens(pf.pnl_realise), aide: "Résultat de vos ventes, déjà encaissé (hors frais)." },
    { libelle: "Gains et pertes latents", debut: a, fin: b, type: sens(pf.pnl_latent), aide: "Ce que vous gagneriez ou perdriez en vendant maintenant." },
    { libelle: "Frais payés", debut: b, fin: d, type: "baisse", aide: "Commissions de courtage cumulées." },
    { libelle: "Valeur actuelle", debut: 0, fin: pf.equity, type: "total", aide: "Liquidités plus valeur des positions." },
  ];
}

// ----------------------------------------------------------------------------- périodes et drawdown
export const PERIODES = [
  { cle: "1m", libelle: "1 mois", jours: 31 },
  { cle: "3m", libelle: "3 mois", jours: 92 },
  { cle: "6m", libelle: "6 mois", jours: 183 },
  { cle: "1a", libelle: "1 an", jours: 366 },
  { cle: "tout", libelle: "Tout", jours: null },
] as const;
export type CleePeriode = (typeof PERIODES)[number]["cle"];

/** Points de la période choisie (jusqu'au dernier point connu, jamais au-delà) ; l'indice de référence est ramené à la
 *  valeur du portefeuille au premier point de la période, pour comparer les deux courbes depuis le même départ. */
export function decouperPeriode(points: PointValeur[], cle: CleePeriode): PointValeur[] {
  const periode = PERIODES.find((p) => p.cle === cle);
  if (!periode || periode.jours === null || points.length === 0) return points;
  const fin = Date.parse(`${points[points.length - 1].jour}T00:00:00Z`);
  const debut = fin - periode.jours * 86_400_000;
  const garde = points.filter((p) => Date.parse(`${p.jour}T00:00:00Z`) >= debut);
  const base = garde.find((p) => p.benchmark !== null);
  if (!base || base.benchmark === null || base.benchmark === 0) return garde;
  const f = base.equity / base.benchmark;
  return garde.map((p) => ({ ...p, benchmark: p.benchmark === null ? null : p.benchmark * f }));
}

/** Drawdown à chaque point : (plus haut atteint jusque-là − valeur) / plus haut, en fraction positive (0,1 = 10 % sous le sommet). */
export function sousLEau(points: PointValeur[]): { jour: string; baisse: number }[] {
  let pic = -Infinity;
  return points.map((p) => {
    pic = Math.max(pic, p.equity);
    return { jour: p.jour, baisse: pic > 0 ? (pic - p.equity) / pic : 0 };
  });
}

// ----------------------------------------------------------------------------- risque par secteur
export type StatutSecteur = "ok" | "attention" | "danger";
export const SEUILS_SECTEUR = { attention: 0.4, danger: 0.6 };      // mêmes seuils pédagogiques que l'analyse serveur

export function statutSecteur(part: number): StatutSecteur {
  return part > SEUILS_SECTEUR.danger ? "danger" : part > SEUILS_SECTEUR.attention ? "attention" : "ok";
}
