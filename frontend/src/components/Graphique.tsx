"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries, ColorType, createChart, createSeriesMarkers, HistogramSeries, LineSeries, LineStyle,
  type IChartApi, type IPriceLine, type ISeriesApi, type ISeriesMarkersPluginApi, type SeriesType, type Time, type UTCTimestamp,
} from "lightweight-charts";
import { couleurs } from "@/lib/indicateurs";
import type { Outil } from "@/lib/technique";
import { useTheme } from "@/lib/theme";
import type { Bougie, CleIndicateur, Dessin, ReponseBougies, Unite } from "@/lib/types";

export type ModeTrace = "aucun" | "horizontal" | "tendance";

interface Props {
  bougies: Bougie[];
  symbole: string;
  unite?: Unite;
  /** Séries d'indicateurs alignées sur `bougies` (même indice), valeurs absentes = null. */
  indicateurs?: Record<string, (number | null)[]> | null;
  choix?: CleIndicateur[];
  niveaux?: ReponseBougies["niveaux"] | null;
  outils?: Outil[];
  dessins?: Dessin[];
  modeTrace?: ModeTrace;
  onDessin?: (d: Dessin) => void;
}

const HAUTEUR_VOLET = { rsi: 110, macd: 130 };
const HAUTEUR_PRINCIPALE = 300;      // hauteur du graphique des prix quand des volets s'ajoutent dessous
const temps = (t: number) => t as UTCTimestamp;

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
  return { discret: v("--discret"), trait: v("--trait"), traitFort: v("--trait-fort"), gain: v("--gain"), perte: v("--perte"), accent: v("--accent"), texte: v("--texte"), ok: v("--ok") };
}

/** « #5baeff » + opacité → « rgba(91, 174, 255, 0.4) » (le canevas ne comprend pas toujours color-mix). */
function transparence(hex: string, alpha: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

const pctFr = (r: number) => `${(r * 100).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`;

export default function Graphique({ bougies, symbole, unite = "1j", indicateurs = null, choix = [], niveaux = null, outils = [], dessins = [], modeTrace = "aucun", onDessin }: Props) {
  const zone = useRef<HTMLDivElement>(null);
  const graphique = useRef<IChartApi | null>(null);
  const serie = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumes = useRef<ISeriesApi<"Histogram"> | null>(null);
  const derniereCle = useRef<string | null>(null);
  const theme = useTheme();
  const serieIndic = useRef<Map<string, ISeriesApi<SeriesType>>>(new Map());
  const reperes = useRef<{ lignes: IPriceLine[]; series: ISeriesApi<SeriesType>[]; marqueurs: ISeriesMarkersPluginApi<Time> | null }>({ lignes: [], series: [], marqueurs: null });
  const donneesRef = useRef({ bougies, indicateurs });
  donneesRef.current = { bougies, indicateurs };
  const themeRef = useRef(theme);
  themeRef.current = theme;
  const traceRef = useRef({ modeTrace, onDessin, premier: null as { t: number; p: number } | null });
  traceRef.current = { ...traceRef.current, modeTrace, onDessin };
  if (modeTrace !== "tendance") traceRef.current.premier = null;
  const cleChoix = [...choix].sort().join(",");
  const sousVolets = (choix.includes("rsi") ? HAUTEUR_VOLET.rsi : 0) + (choix.includes("macd") ? HAUTEUR_VOLET.macd : 0);
  const intraday = unite !== "1j";

  /** Alimente les séries d'indicateurs (valeurs absentes sautées), alignées sur les bougies par leur indice. */
  function remplirIndicateurs() {
    const COULEURS = couleurs(themeRef.current);
    const { bougies: b, indicateurs: d } = donneesRef.current;
    for (const [cle, s] of serieIndic.current) {
      const valeurs = d?.[cle];
      if (!valeurs) { s.setData([]); continue; }
      const points: { time: UTCTimestamp; value: number; color?: string }[] = [];
      b.forEach((x, i) => {
        const v = valeurs[i];
        if (v === null || v === undefined) return;
        points.push(cle === "macd_histogramme"
          ? { time: temps(x.t), value: v, color: v >= 0 ? COULEURS.histogramme_haut : COULEURS.histogramme_bas }
          : { time: temps(x.t), value: v });
      });
      (s as ISeriesApi<"Line">).setData(points);
    }
  }

  // Création du graphique et du tracé manuel (un clic : ligne horizontale ; deux clics : ligne de tendance).
  useEffect(() => {
    if (!zone.current) return;
    const v = couleursCss();
    const c = createChart(zone.current, {
      autoSize: true,
      localization: { locale: "fr-FR" },
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: v.discret, fontFamily: getComputedStyle(document.body).fontFamily, fontSize: 12 },
      grid: { vertLines: { color: v.trait }, horzLines: { color: v.trait } },
      rightPriceScale: { borderColor: v.traitFort },
      timeScale: { borderColor: v.traitFort, timeVisible: false, secondsVisible: false },
      crosshair: { vertLine: { color: v.discret, labelBackgroundColor: v.traitFort }, horzLine: { color: v.discret, labelBackgroundColor: v.traitFort } },
    });
    const s = c.addSeries(CandlestickSeries, {
      upColor: v.gain, downColor: v.perte, wickUpColor: v.gain, wickDownColor: v.perte, borderVisible: false,
      priceFormat: { type: "custom", formatter: formaterPrix, minMove: 0.00001 },
    });
    c.subscribeClick((param) => {
      const { modeTrace: m, onDessin: rappel, premier } = traceRef.current;
      if (m === "aucun" || !rappel || !param.point || param.time === undefined) return;
      const prix = s.coordinateToPrice(param.point.y);
      if (prix === null) return;
      if (m === "horizontal") { rappel({ type: "horizontal", prix }); return; }
      const t = Number(param.time);
      if (!premier) { traceRef.current.premier = { t, p: prix }; return; }
      if (t !== premier.t) rappel({ type: "tendance", t1: Math.min(t, premier.t), p1: t < premier.t ? prix : premier.p, t2: Math.max(t, premier.t), p2: t < premier.t ? premier.p : prix });
      traceRef.current.premier = null;
    });
    graphique.current = c;
    serie.current = s;
    return () => {
      serieIndic.current.clear();
      reperes.current = { lignes: [], series: [], marqueurs: null };
      volumes.current = null;
      c.remove();
      graphique.current = null;
      serie.current = null;
      derniereCle.current = null;
    };
  }, []);

  // Échelle de temps : heures et minutes visibles en intrajournalier (heures UTC, comme l'horloge du simulateur).
  useEffect(() => { graphique.current?.applyOptions({ timeScale: { timeVisible: intraday } }); }, [intraday]);

  // Bougies.
  useEffect(() => {
    if (!serie.current || !graphique.current) return;
    serie.current.setData(bougies.map((b) => ({ time: temps(b.t), open: b.open, high: b.high, low: b.low, close: b.close })));
    const cle = `${symbole}|${unite}`;
    if (derniereCle.current !== cle && bougies.length > 0) {
      derniereCle.current = cle;
      graphique.current.timeScale().setVisibleLogicalRange({ from: Math.max(0, bougies.length - 120), to: bougies.length + 6 });
    }
    remplirIndicateurs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bougies, symbole, unite]);

  // Volumes : histogramme en bas du volet des prix, sur sa propre échelle (jamais un second axe de prix).
  const voirVolumes = outils.includes("volumes") && !intraday;
  useEffect(() => {
    const c = graphique.current;
    if (!c) return;
    if (!voirVolumes) {
      if (volumes.current) { c.removeSeries(volumes.current); volumes.current = null; }
      return;
    }
    const v = couleursCss();
    if (!volumes.current) {
      volumes.current = c.addSeries(HistogramSeries, { priceScaleId: "volume", priceLineVisible: false, lastValueVisible: false, priceFormat: { type: "volume" } }, 0);
      c.priceScale("volume").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    }
    volumes.current.setData(bougies.filter((b) => b.volume !== null).map((b) => ({
      time: temps(b.t), value: b.volume as number, color: transparence(b.close >= b.open ? v.gain : v.perte, 0.45),
    })));
  }, [bougies, voirVolumes, theme]);

  // Apparence : les couleurs suivent le thème (sombre ou clair).
  useEffect(() => {
    const c = graphique.current, b = serie.current;
    if (!c || !b) return;
    const v = couleursCss();
    c.applyOptions({
      layout: { textColor: v.discret, panes: { separatorColor: v.trait, separatorHoverColor: v.trait } },
      grid: { vertLines: { color: v.trait }, horzLines: { color: v.trait } },
      rightPriceScale: { borderColor: v.traitFort }, timeScale: { borderColor: v.traitFort },
      crosshair: { vertLine: { color: v.discret, labelBackgroundColor: v.traitFort }, horzLine: { color: v.discret, labelBackgroundColor: v.traitFort } },
    });
    b.applyOptions({ upColor: v.gain, downColor: v.perte, wickUpColor: v.gain, wickDownColor: v.perte });
  }, [theme]);

  // Repères : supports et résistances, cassures, tendances, Fibonacci, tracés manuels. Redessinés seulement s'ils changent.
  const cleReperes = JSON.stringify([outils.filter((o) => o !== "volumes").sort(), niveaux, dessins, theme]);
  useEffect(() => {
    const c = graphique.current, s = serie.current;
    if (!c || !s) return;
    const r = reperes.current;
    r.lignes.forEach((l) => s.removePriceLine(l));
    r.series.forEach((x) => c.removeSeries(x));
    r.marqueurs?.setMarkers([]);
    r.lignes = []; r.series = [];
    const v = couleursCss();
    const ligne = (p1: { t: number; p: number }, p2: { t: number; p: number }, couleur: string, style = LineStyle.Solid) => {
      const x = c.addSeries(LineSeries, { color: couleur, lineWidth: 2, lineStyle: style, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }, 0);
      x.setData([{ time: temps(p1.t), value: p1.p }, { time: temps(p2.t), value: p2.p }]);
      r.series.push(x);
    };

    if (niveaux && outils.includes("niveaux")) {
      for (const n of niveaux.supports_resistances) {
        r.lignes.push(s.createPriceLine({ price: n.niveau, color: n.type === "support" ? v.gain : v.perte, lineWidth: 1, lineStyle: LineStyle.Dashed,
          axisLabelVisible: true, title: `${n.type === "support" ? "Support" : "Résistance"} (${n.touches} contacts)` }));
      }
      const marques = niveaux.cassures.map((x) => ({
        time: temps(x.t), position: x.sens === "haussiere" ? "belowBar" as const : "aboveBar" as const,
        color: x.sens === "haussiere" ? v.gain : v.perte, shape: x.sens === "haussiere" ? "arrowUp" as const : "arrowDown" as const,
        text: "Cassure possible",
      })).sort((a, b) => Number(a.time) - Number(b.time));
      if (!r.marqueurs) r.marqueurs = createSeriesMarkers(s, marques);
      else r.marqueurs.setMarkers(marques);
    }
    if (niveaux && outils.includes("tendances")) {
      for (const t of niveaux.tendances) ligne({ t: t.t1, p: t.p1 }, { t: t.t2, p: t.p2 }, t.sens === "haussiere" ? v.gain : v.perte);
    }
    if (niveaux?.fibonacci && outils.includes("fibonacci")) {
      for (const n of niveaux.fibonacci.niveaux) {
        r.lignes.push(s.createPriceLine({ price: n.prix, color: v.accent, lineWidth: 1, lineStyle: n.ratio === 0 || n.ratio === 1 ? LineStyle.Solid : LineStyle.Dotted,
          axisLabelVisible: false, title: `Fibo ${pctFr(n.ratio)}` }));
      }
    }
    for (const d of dessins) {
      if (d.type === "horizontal") r.lignes.push(s.createPriceLine({ price: d.prix, color: v.texte, lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: "Mon tracé" }));
      else ligne({ t: d.t1, p: d.p1 }, { t: d.t2, p: d.p2 }, v.texte);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cleReperes]);

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

  useEffect(() => { remplirIndicateurs(); }, [indicateurs]);  // eslint-disable-line react-hooks/exhaustive-deps

  const libelleUnite = intraday ? `en bougies de ${unite.replace("min", " minute(s)").replace("1h", "1 heure")}` : "en bougies journalières";
  return (
    <div ref={zone} className={`graphique-zone${modeTrace !== "aucun" ? " graphique-trace" : ""}`}
      style={sousVolets > 0 ? { flex: "none", height: HAUTEUR_PRINCIPALE + sousVolets } : undefined}
      role="img" aria-label={`Graphique de ${symbole} ${libelleUnite}`} />
  );
}
