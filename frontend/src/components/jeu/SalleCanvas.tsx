"use client";

import { useEffect, useRef } from "react";
import { pctSigne } from "@/lib/format";
import type { ActifPartie } from "./types";

/* La salle : le cours est projeté, le public est le marché. Chaque silhouette part quand la peur réelle du jour dépasse
   son seuil, et revient quand elle retombe. Le dessin ne connaît que les séances déjà envoyées par le serveur. */

function tirage(graine: number) {
  let g = graine;
  return () => {
    g = (g + 0x6d2b79f5) | 0;
    let t = Math.imul(g ^ (g >>> 15), 1 | g);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const RANGS = 7;
const sieges = (rang: number) => 22 - rang * 2;

const PUBLIC = (() => {
  const r = tirage(314);
  const tous: { rang: number; x: number; seuil: number; vitesse: number; phase: number; taille: number }[] = [];
  for (let rang = 0; rang < RANGS; rang++) {
    for (let c = 0; c < sieges(rang); c++) {
      tous.push({ rang, x: (c + 0.5) / sieges(rang) - 0.5, seuil: 24 + r() * 86, vitesse: 0.6 + r() * 0.8, phase: r() * 6.3, taille: 0.9 + r() * 0.22 });
    }
  }
  return tous;
})();

const POUSSIERE = Array.from({ length: 70 }, (_, i) => {
  const r = tirage(900 + i);
  return [r(), r(), r()] as const;
});

const borner = (v: number, bas: number, haut: number) => Math.min(haut, Math.max(bas, v));

interface Memoire { peur: number; depart: Float32Array; avant: number | null }

function dessiner(c: CanvasRenderingContext2D, W: number, H: number, temps: number, calme: boolean,
  actif: ActifPartie | undefined, peurCible: number, m: Memoire, polices: { titre: string; texte: string }) {
  const t = calme ? 0 : temps / 1000;
  const dt = m.avant === null ? 1 : borner((temps - m.avant) / 16.7, 0, 4);
  m.avant = temps;
  m.peur += (peurCible - m.peur) * (calme ? 1 : Math.min(1, 0.06 * dt));
  const p = m.peur / 100;
  const melange = borner((p - 0.2) / 0.55, 0, 1);
  const lum = [59, 227, 234].map((v, i) => Math.round(v + ([255, 113, 108][i] - v) * melange));
  const lumiere = (a: number) => `rgba(${lum},${a})`;

  const etroit = W < 600;
  const eh = H * (etroit ? 0.5 : 0.56);
  const ew = Math.min(W * (etroit ? 0.92 : 0.66), eh * 2.5);
  const ex = (W - ew) / 2, ey = H * 0.045, sol = ey + eh;
  const secousse = !calme && p > 0.72 ? Math.sin(t * 43) * (p - 0.72) * 5 : 0;

  c.fillStyle = "#02070e";
  c.fillRect(0, 0, W, H);
  c.save();
  c.translate(secousse, 0);

  // murs en perspective, appliques, rideaux, issues de secours
  for (const droite of [false, true]) {
    const x = (v: number) => (droite ? W - v : v);
    const mur = c.createLinearGradient(x(0), 0, x(ex), 0);
    mur.addColorStop(0, "#02070e");
    mur.addColorStop(1, "#0b1b30");
    c.fillStyle = mur;
    c.beginPath(); c.moveTo(x(0), 0); c.lineTo(x(ex), ey); c.lineTo(x(ex), sol); c.lineTo(x(0), H); c.fill();
    for (let i = 1; i < 6; i++) {
      const u = i / 6, xx = x(ex * u);
      c.strokeStyle = "#12283f";
      c.beginPath(); c.moveTo(xx, ey * u); c.lineTo(xx, H + (sol - H) * u); c.stroke();
      if (i % 2) {
        const halo = c.createRadialGradient(xx, H * 0.3, 0, xx, H * 0.3, 30);
        halo.addColorStop(0, lumiere(0.35));
        halo.addColorStop(1, lumiere(0));
        c.fillStyle = halo;
        c.fillRect(xx - 30, H * 0.3 - 30, 60, 60);
      }
    }
    const pli = ew * 0.055;
    for (let i = 0; i < 4; i++) {
      const px = ex - pli + (i * pli) / 4;
      c.fillStyle = i % 2 ? "#0c2a3a" : "#124053";
      c.fillRect(droite ? W - px - pli / 4 : px, ey, pli / 4, eh + 5);
    }
    if (!etroit) {
      const sx = x(Math.max(28, ex * 0.55));
      c.fillStyle = p > 0.45 ? "#4fd1b0" : "#1d5a4e";
      c.fillRect(sx - 20, H * 0.54, 40, 13);
      c.fillStyle = "#02130f";
      c.font = `600 9px ${polices.texte}`;
      c.textAlign = "center";
      c.fillText("SORTIE", sx, H * 0.54 + 10);
    }
  }

  const reflet = c.createRadialGradient(W / 2, sol, 10, W / 2, sol, W * 0.65);
  reflet.addColorStop(0, lumiere(0.22));
  reflet.addColorStop(1, lumiere(0));
  c.fillStyle = reflet;
  c.fillRect(0, 0, W, H);

  // écran
  c.fillStyle = "#071727";
  c.fillRect(ex, ey, ew, eh);
  const toile = c.createLinearGradient(0, ey, 0, sol);
  toile.addColorStop(0, lumiere(0.2));
  toile.addColorStop(1, lumiere(0.04));
  c.fillStyle = toile;
  c.fillRect(ex, ey, ew, eh);
  c.save();
  c.beginPath(); c.rect(ex, ey, ew, eh); c.clip();
  if (actif) {
    const o = actif.ouvertures, f = actif.clotures, n = f.length;
    let bas = 90, haut = 106;
    for (let i = 0; i < n; i++) { bas = Math.min(bas, f[i], i ? o[i] : f[i]); haut = Math.max(haut, f[i], i ? o[i] : f[i]); }
    bas *= 0.97; haut *= 1.02;
    // l'axe s'allonge avec le film : la place restante ne dit rien de sa durée
    const axe = Math.max(36, Math.ceil(n * 1.3));
    const pas = (ew * 0.94) / axe;
    const gx = (i: number) => ex + ew * 0.03 + (i + 0.5) * pas;
    const gy = (v: number) => ey + eh * 0.2 + ((haut - v) / (haut - bas)) * eh * 0.71;
    const futur = gx(n - 1) + pas;

    c.strokeStyle = "rgba(237,245,251,0.07)";
    for (let i = 1; i < 5; i++) { c.beginPath(); c.moveTo(ex, ey + (eh * i) / 5); c.lineTo(ex + ew, ey + (eh * i) / 5); c.stroke(); }

    c.save();
    c.beginPath(); c.rect(futur, ey, ex + ew - futur, eh); c.clip();
    c.strokeStyle = "rgba(169,189,209,0.1)";
    c.beginPath();
    for (let x = futur - eh; x < ex + ew + eh; x += 11) { c.moveTo(x, ey); c.lineTo(x + eh * 0.4, sol); }
    c.stroke();
    c.restore();

    c.setLineDash([5, 5]);
    c.strokeStyle = "rgba(237,245,251,0.3)";
    c.beginPath(); c.moveTo(ex, gy(100)); c.lineTo(ex + ew, gy(100)); c.stroke();
    c.setLineDash([]);

    const epaisseur = Math.max(1.5, Math.min(13, pas * 0.68));
    for (let i = 0; i < n; i++) {
      const debut = i ? o[i] : f[i], avant = i ? f[i - 1] : f[i];
      const x = gx(i);
      c.strokeStyle = c.fillStyle = f[i] >= avant ? "#5ce6c3" : "#ff7f79";
      // le trait relie la clôture d'hier à l'ouverture : c'est le saut qu'aucun stop ne protège
      if (i) { c.beginPath(); c.moveTo(x, gy(avant)); c.lineTo(x, gy(debut)); c.stroke(); }
      c.fillRect(x - epaisseur / 2, gy(Math.max(debut, f[i])), epaisseur, Math.max(2, Math.abs(gy(f[i]) - gy(debut))));
    }
    const dernier = f[n - 1];
    c.fillStyle = lumiere(0.22);
    c.beginPath(); c.arc(gx(n - 1), gy(dernier), 9 + (calme ? 0 : Math.sin(t * 4) * 3), 0, 7); c.fill();
    c.strokeStyle = lumiere(0.8);
    c.beginPath(); c.moveTo(futur, ey); c.lineTo(futur, sol); c.stroke();

    const corps = Math.min(Math.max(14, eh * 0.1), ew * 0.06);
    c.fillStyle = "#edf5fb";
    c.font = `700 ${corps}px ${polices.titre}`;
    c.textAlign = "left";
    c.fillText(actif.nom, ex + 14, ey + Math.max(22, eh * 0.115));
    c.textAlign = "right";
    c.fillText(pctSigne(dernier / 100 - 1, 1), ex + ew - 14, ey + Math.max(22, eh * 0.115));
  }
  if (p > 0.62) {
    c.strokeStyle = `rgba(237,245,251,${(p - 0.55) * 0.6})`;
    c.beginPath();
    let x = ex + ew * 0.8, y = ey;
    c.moveTo(x, y);
    for (let i = 0; i < 8; i++) { x += (i % 2 ? -1 : 1.4) * ew * 0.025; y += eh / 8; c.lineTo(x, y); }
    c.stroke();
  }
  if (!calme) {
    c.fillStyle = "rgba(237,245,251,0.13)";
    const k = Math.floor(t * 12);
    for (let i = 0; i < 14; i++) c.fillRect(ex + (Math.sin(i * 77 + k) * 0.5 + 0.5) * ew, ey + (Math.cos(i * 31 + k) * 0.5 + 0.5) * eh, 1.5, 1.5);
  }
  c.restore();
  c.lineWidth = 2;
  c.strokeStyle = lumiere(0.65);
  c.strokeRect(ex, ey, ew, eh);
  c.lineWidth = 1;

  // faisceau, derrière le public
  const faisceau = c.createLinearGradient(0, H, 0, ey);
  faisceau.addColorStop(0, lumiere(0));
  faisceau.addColorStop(0.3, lumiere(0.09));
  faisceau.addColorStop(1, lumiere(0.02));
  c.fillStyle = faisceau;
  c.beginPath(); c.moveTo(W * 0.48, H); c.lineTo(ex, ey); c.lineTo(ex + ew, ey); c.lineTo(W * 0.52, H); c.fill();
  for (const [u, v, r] of POUSSIERE) {
    const y = H - ((v + t * 0.025 * (0.5 + r)) % 1) * (H - ey);
    c.fillStyle = lumiere(0.18 + r * 0.3);
    c.fillRect(W / 2 + (u - 0.5) * ((ew * (H - y)) / (H - ey)) + Math.sin(t + r * 9) * 4, y, 1 + r * 1.5, 1 + r * 1.5);
  }

  // le public, du fond vers le premier rang
  PUBLIC.forEach((s, j) => {
    const k = (s.rang + 1) / RANGS;
    const largeur = W * (etroit ? 0.86 : 0.62) + W * 0.56 * k * k;
    const taille = largeur / sieges(s.rang);
    const y = sol + (H - sol) * (0.1 + 0.92 * k * k) + 4;
    const x = W / 2 + s.x * largeur;
    const part = m.peur > s.seuil ? 1 : 0;
    m.depart[j] = calme ? part : borner(m.depart[j] + (part ? 0.022 : -0.03) * s.vitesse * dt, 0, 1);

    c.fillStyle = `rgb(${Math.round(8 + k * 8)},${Math.round(20 + k * 16)},${Math.round(36 + k * 22)})`;
    c.beginPath(); c.roundRect(x - taille * 0.42, y - taille * 0.2, taille * 0.84, taille * 0.85, taille * 0.16); c.fill();
    const e = m.depart[j];
    if (e >= 1) return;
    const debout = Math.min(1, e * 5), marche = Math.max(0, (e - 0.2) / 0.8), cote = s.x < 0 ? -1 : 1;
    const agite = calme ? 0 : Math.sin(t * (2 + p * 9) + s.phase) * taille * 0.05 * p;
    const pasDePied = e > 0.2 && !calme ? Math.abs(Math.sin(t * 8 + s.phase)) * -taille * 0.08 : 0;
    const xx = x + cote * marche * W * 0.6, yy = y - debout * taille * 0.42 + pasDePied, R = taille * 0.2 * s.taille;
    c.globalAlpha = 1 - marche * 0.75;
    c.fillStyle = "#01050a";
    c.strokeStyle = lumiere(0.22 + 0.45 * (1 - k));
    c.lineWidth = 1.2;
    c.beginPath(); c.arc(xx + agite, yy - R * 1.65, R, 0, 7); c.fill();
    c.beginPath(); c.arc(xx + agite, yy - R * 1.65, R, Math.PI * 1.08, Math.PI * 1.92); c.stroke();
    c.beginPath();
    c.moveTo(xx - R * 1.8, yy + R * (1.5 + debout * 2));
    c.quadraticCurveTo(xx - R * 1.8, yy - R * 0.7, xx, yy - R * 0.7);
    c.quadraticCurveTo(xx + R * 1.8, yy - R * 0.7, xx + R * 1.8, yy + R * (1.5 + debout * 2));
    c.fill();
    c.globalAlpha = 1;
    c.lineWidth = 1;
  });
  c.restore();
}

export default function SalleCanvas({ actif, peur }: { actif: ActifPartie | undefined; peur: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const donnees = useRef({ actif, peur });
  donnees.current = { actif, peur };

  useEffect(() => {
    const cv = ref.current;
    const c = cv?.getContext("2d");
    if (!cv || !c) return;
    const reduit = window.matchMedia("(prefers-reduced-motion: reduce)");
    const css = getComputedStyle(document.documentElement);
    const polices = {
      titre: css.getPropertyValue("--police-titre").trim() || "sans-serif",
      texte: css.getPropertyValue("--police").trim() || "sans-serif",
    };
    const memoire: Memoire = { peur: donnees.current.peur, depart: new Float32Array(PUBLIC.length), avant: null };
    PUBLIC.forEach((s, j) => { memoire.depart[j] = memoire.peur > s.seuil ? 1 : 0; });
    let image = 0;
    const boucle = (temps: number) => {
      const W = cv.clientWidth, H = cv.clientHeight, densite = Math.min(2, window.devicePixelRatio || 1);
      if (W >= 20 && H >= 20) {
        if (cv.width !== Math.round(W * densite) || cv.height !== Math.round(H * densite)) {
          cv.width = Math.round(W * densite);
          cv.height = Math.round(H * densite);
        }
        c.setTransform(densite, 0, 0, densite, 0, 0);
        dessiner(c, W, H, temps, reduit.matches, donnees.current.actif, donnees.current.peur, memoire, polices);
      }
      image = requestAnimationFrame(boucle);
    };
    image = requestAnimationFrame(boucle);
    return () => cancelAnimationFrame(image);
  }, []);

  return <canvas ref={ref} role="img" aria-label="Salle de cinéma : le cours est projeté, le public fuit quand la peur monte." />;
}
