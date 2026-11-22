import type { CleIndicateur } from "./types";

/** Couleurs des indicateurs sur le fond navy de Séance : or, violet, bleu, magenta.
 *  Elles évitent le menthe et le corail des bougies, et le cyan réservé à ce qui se clique. */
export const COULEURS = {
  sma_courte: "#b98a14", sma_longue: "#8b7cf0", ema: "#4c86e8", bollinger: "#7e93a6",
  rsi: "#8b7cf0", macd: "#8b7cf0", macd_signal: "#b98a14",
  histogramme_haut: "rgba(47, 165, 138, 0.6)", histogramme_bas: "rgba(229, 98, 94, 0.6)",
};

export const TOUS: CleIndicateur[] = ["sma", "ema", "bollinger", "rsi", "macd"];
export const CLE_STOCKAGE = "sdm.indicateurs";

export const LIBELLES: Record<CleIndicateur, string> = {
  sma: "Moyennes mobiles", ema: "EMA", bollinger: "Bandes de Bollinger", rsi: "RSI", macd: "MACD",
};

/** Explications en mots simples, affichées en mode Apprenant. */
export const AIDE: Record<CleIndicateur | "atr", string> = {
  sma: "Moyenne mobile : la moyenne des derniers prix de clôture (20 puis 50 jours). Quand le prix passe au-dessus, la tendance récente est plutôt à la hausse ; en dessous, plutôt à la baisse. Elle réagit avec du retard.",
  ema: "Moyenne mobile exponentielle : comme la moyenne mobile, mais les prix récents pèsent plus lourd, donc elle réagit plus vite.",
  bollinger: "Bandes de Bollinger : une bande autour de la moyenne de 20 jours, large de deux écarts-types. Plus elle est large, plus le prix est agité. Toucher une bande ne veut pas dire que le prix va repartir dans l'autre sens.",
  rsi: "RSI : de 0 à 100, il dit si le prix a beaucoup monté (au-dessus de 70) ou beaucoup baissé (sous 30) ces 14 derniers jours. Seul, ce n'est pas un signal fiable d'achat ou de vente.",
  macd: "MACD : compare une moyenne rapide (12 jours) et une lente (26 jours). Quand sa ligne passe au-dessus de son signal, la hausse s'accélère ; en dessous, elle faiblit. Les barres montrent l'écart.",
  atr: "ATR : l'amplitude moyenne d'une journée sur 14 jours, écarts d'ouverture compris. Elle sert à placer un stop à une distance raisonnable.",
};

export function lireChoix(): CleIndicateur[] {
  try {
    const brut = typeof window === "undefined" ? null : localStorage.getItem(CLE_STOCKAGE);
    const l = brut ? (JSON.parse(brut) as unknown) : null;
    return Array.isArray(l) ? (l.filter((x): x is CleIndicateur => TOUS.includes(x as CleIndicateur))) : [];
  } catch {
    return [];
  }
}

export function enregistrerChoix(choix: CleIndicateur[]): void {
  try { localStorage.setItem(CLE_STOCKAGE, JSON.stringify(choix)); } catch { /* stockage indisponible : le choix ne sera pas mémorisé */ }
}
