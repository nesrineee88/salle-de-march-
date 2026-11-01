import type { Theme } from "./theme";
import type { CleIndicateur } from "./types";

/** Couleurs des indicateurs, ordre magenta, violet, aqua de la palette « dataviz », validées avec son script :
 *  - thème sombre (fond #0B1620) : toutes les vérifications passent ;
 *  - thème clair (fond blanc) : toutes passent, sauf le contraste du magenta et de l'aqua (2,7 et 2,8 contre 3 demandé),
 *    compensé par la légende nommée sous le graphique (règle de « relief » de la méthode).
 *  Elles évitent le bleu et l'orange, déjà pris par les bougies. */
const SOMBRE = {
  sma_courte: "#d55181", sma_longue: "#9085e9", ema: "#199e70", bollinger: "#7e93a6",
  rsi: "#9085e9", macd: "#9085e9", macd_signal: "#199e70",
  histogramme_haut: "rgba(91, 174, 255, 0.55)", histogramme_bas: "rgba(255, 146, 85, 0.55)",
};
const CLAIR = {
  sma_courte: "#e87ba4", sma_longue: "#6250d6", ema: "#1baf7a", bollinger: "#7a8a99",
  rsi: "#6250d6", macd: "#6250d6", macd_signal: "#1baf7a",
  histogramme_haut: "rgba(15, 111, 208, 0.5)", histogramme_bas: "rgba(194, 74, 20, 0.5)",
};
export type CouleursIndicateurs = typeof SOMBRE;
export const couleurs = (theme: Theme): CouleursIndicateurs => (theme === "clair" ? CLAIR : SOMBRE);

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
