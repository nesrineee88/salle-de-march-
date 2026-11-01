"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries, ColorType, createChart, HistogramSeries, LineSeries, LineStyle,
  type IChartApi, type ISeriesApi, type SeriesType,
} from "lightweight-charts";
import { couleurs } from "@/lib/indicateurs";
import { useTheme } from "@/lib/theme";
import type { Barre, CleIndicateur, Indicateurs } from "@/lib/types";

interface Props {
  barres: Barre[];
  symbole: string;
  indicateurs?: Indicateurs | null;
  choix?: CleIndicateur[];
}

const HAUTEUR_VOLET = { rsi: 110, macd: 130 };
const HAUTEUR_PRINCIPALE = 300;      // hauteur du graphique des prix quand des volets s'ajoutent dessous

/** Nombre de décimales adapté à l'ampleur de la valeur (le MACD d'un Dogecoin vaut des millièmes, celui d'un Bitcoin des centaines). */
function formaterIndicateur(v: number): string {
  const a = Math.abs(v);
  const d = a >= 100 ? 0 : a >= 1 ? 2 : a >= 0.01 ? 4 : 6;
  return v.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
}

/** Prix : plus de décimales pour les petits prix (un Dogecoin vaut quelques centimes). Même règle que dans le reste de l'interface. */
function formaterPrix(p: number): string {
  const a = Math.abs(p);
  const d = a >= 10 ? 2 : a >= 1 ? 3 : 5;
  return p.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
}

function couleursCss() {
  const css = getComputedStyle(document.documentElement);
  const v = (nom: string) => css.getPropertyValue(nom).trim();
  return { discret: v("--discret"), trait: v("--trait"), traitFort: v("--trait-fort"), gain: v("--gain"), perte: v("--perte") };
}

export default function Graphique({ barres, symbole, indicateurs = null, choix = [] }: Props) {
  const zone = useRef<HTMLDivElement>(null);
  const graphique = useRef<IChartApi | null>(null);
  const serie = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const dernierSymbole = useRef<string | null>(null);
  const theme = useTheme();
  const serieIndic = useRef<Map<string, ISeriesApi<SeriesType>>>(new Map());
  const indicRef = useRef<Indicateurs | null>(null);
  indicRef.current = indicateurs && indicateurs.symbole === symbole ? indicateurs : null;
  const themeRef = useRef(theme);
  themeRef.current = theme;
  const cleChoix = [...choix].sort().join(",");
  const sousVolets = (choix.includes("rsi") ? HAUTEUR_VOLET.rsi : 0) + (choix.includes("macd") ? HAUTEUR_VOLET.macd : 0);

  /** Alimente les séries d'indicateurs avec les dernières valeurs reçues (les valeurs absentes sont sautées). */
  function remplirIndicateurs() {
    const COULEURS = couleurs(themeRef.current);
    const d = indicRef.current;
    for (const [cle, serie] of serieIndic.current) {
      if (!d) { serie.setData([]); continue; }
      const valeurs = d.series[cle];
      if (!valeurs) continue;
      const points: { time: string; value: number; color?: string }[] = [];
      d.dates.forEach((date, i) => {
        const v = valeurs[i];
        if (v === null || v === undefined) return;
        points.push(cle === "macd_histogramme"
          ? { time: date, value: v, color: v >= 0 ? COULEURS.histogramme_haut : COULEURS.histogramme_bas }
          : { time: date, value: v });
      });
      (serie as ISeriesApi<"Line">).setData(points as never);
    }
  }

  useEffect(() => {
    if (!zone.current) return;
    const css = getComputedStyle(document.documentElement);
    const v = (nom: string) => css.getPropertyValue(nom).trim();
    const c = createChart(zone.current, {
      autoSize: true,
      localization: { locale: "fr-FR" },
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: v("--discret"),
        fontFamily: getComputedStyle(document.body).fontFamily,
        fontSize: 12,
      },
      grid: { vertLines: { color: v("--trait") }, horzLines: { color: v("--trait") } },
      rightPriceScale: { borderColor: v("--trait-fort") },
      timeScale: { borderColor: v("--trait-fort"), timeVisible: false },
      crosshair: { vertLine: { color: v("--discret"), labelBackgroundColor: v("--trait-fort") }, horzLine: { color: v("--discret"), labelBackgroundColor: v("--trait-fort") } },
    });
    const s = c.addSeries(CandlestickSeries, {
      upColor: v("--gain"), downColor: v("--perte"),
      wickUpColor: v("--gain"), wickDownColor: v("--perte"),
      borderVisible: false,
      priceFormat: { type: "custom", formatter: formaterPrix, minMove: 0.00001 },
    });
    graphique.current = c;
    serie.current = s;
    return () => {
      serieIndic.current.clear();
      c.remove();
      graphique.current = null;
      serie.current = null;
      dernierSymbole.current = null;
    };
  }, []);

  useEffect(() => {
    if (!serie.current || !graphique.current || barres.length === 0) return;
    serie.current.setData(barres.map((b) => ({ time: b.date, open: b.open, high: b.high, low: b.low, close: b.close })));
    if (dernierSymbole.current !== symbole) {
      dernierSymbole.current = symbole;
      graphique.current.timeScale().setVisibleLogicalRange({ from: Math.max(0, barres.length - 120), to: barres.length + 6 });
    }
  }, [barres, symbole]);

  // Apparence : les couleurs du graphique suivent le thème (sombre ou clair).
  useEffect(() => {
    const c = graphique.current, bougies = serie.current;
    if (!c || !bougies) return;
    const v = couleursCss();
    c.applyOptions({
      layout: { textColor: v.discret, panes: { separatorColor: v.trait, separatorHoverColor: v.trait } },
      grid: { vertLines: { color: v.trait }, horzLines: { color: v.trait } },
      rightPriceScale: { borderColor: v.traitFort }, timeScale: { borderColor: v.traitFort },
      crosshair: { vertLine: { color: v.discret, labelBackgroundColor: v.traitFort }, horzLine: { color: v.discret, labelBackgroundColor: v.traitFort } },
    });
    bougies.applyOptions({ upColor: v.gain, downColor: v.perte, wickUpColor: v.gain, wickDownColor: v.perte });
  }, [theme]);

  // Structure : quelles séries et quels volets existent, selon les indicateurs cochés.
  useEffect(() => {
    const c = graphique.current;
    if (!c) return;
    const COULEURS = couleurs(theme);
    serieIndic.current.forEach((s) => c.removeSeries(s));
    serieIndic.current.clear();
    while (c.panes().length > 1) c.removePane(c.panes().length - 1);

    const ligne = (cle: string, couleur: string, volet: number, extra: object = {}) =>
      serieIndic.current.set(cle, c.addSeries(LineSeries, {
        color: couleur, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, ...extra,
      }, volet));
    const fin = (cle: string, couleur: string, volet: number, extra: object = {}) => ligne(cle, couleur, volet, { lineWidth: 1, ...extra });

    const actifs = new Set(cleChoix ? cleChoix.split(",") : []);
    if (actifs.has("sma")) { ligne("sma_courte", COULEURS.sma_courte, 0); ligne("sma_longue", COULEURS.sma_longue, 0); }
    if (actifs.has("ema")) ligne("ema", COULEURS.ema, 0);
    if (actifs.has("bollinger")) {
      fin("bollinger_haute", COULEURS.bollinger, 0); fin("bollinger_basse", COULEURS.bollinger, 0);
      fin("bollinger_milieu", COULEURS.bollinger, 0, { lineStyle: LineStyle.Dotted });
    }
    let volet = 1;
    const hauteurs: [number, number][] = [];
    if (actifs.has("rsi")) {
      ligne("rsi", COULEURS.rsi, volet, {
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
        priceFormat: { type: "custom", formatter: (v: number) => v.toFixed(0), minMove: 1 },
      });
      const rsi = serieIndic.current.get("rsi")!;
      for (const niveau of [30, 70]) rsi.createPriceLine({ price: niveau, color: COULEURS.bollinger, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: "" });
      c.priceScale("right", volet).applyOptions({ scaleMargins: { top: 0.08, bottom: 0.08 } });     // l'échelle reste 0 à 100
      hauteurs.push([volet, HAUTEUR_VOLET.rsi]);
      volet += 1;
    }
    if (actifs.has("macd")) {
      const formatMacd = { type: "custom" as const, formatter: formaterIndicateur, minMove: 0.0001 };
      serieIndic.current.set("macd_histogramme", c.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false, priceFormat: formatMacd }, volet));
      ligne("macd", COULEURS.macd, volet, { priceFormat: formatMacd }); ligne("macd_signal", COULEURS.macd_signal, volet, { priceFormat: formatMacd });
      hauteurs.push([volet, HAUTEUR_VOLET.macd]);
    }
    // Les hauteurs ne s'appliquent qu'une fois le conteneur redimensionné : on attend un court instant.
    const minuteur = setTimeout(() => hauteurs.forEach(([i, h]) => c.panes()[i]?.setHeight(h)), 80);
    remplirIndicateurs();
    return () => clearTimeout(minuteur);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cleChoix, theme]);

  // Données : mises à jour à chaque nouvelle lecture.
  useEffect(() => { remplirIndicateurs(); }, [indicateurs, symbole]);  // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={zone} className="graphique-zone" style={sousVolets > 0 ? { flex: "none", height: HAUTEUR_PRINCIPALE + sousVolets } : undefined} role="img" aria-label={`Graphique en bougies journalières de ${symbole}`} />;
}
