"use client";

import { useEffect, useRef } from "react";
import { useApparence } from "@/lib/apparence";

interface Courbe { y: number; amp: number; vitesse: number; pts: number[]; decalage: number; teinte: "gain" | "discret"; }

const PAS = 46;   // écart horizontal entre deux points d'une courbe

/** Fond animé : des courbes de prix qui dérivent lentement, et un halo qui suit la souris (légère parallaxe).
 *  Dessiné sur un canvas fixe, à 30 images/s, arrêté quand l'onglet est caché ; une seule image fixe si le système demande moins de mouvement. */
export default function FondAnime() {
  const { fond } = useApparence();
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || fond === "aucun") return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduit = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const vivant = fond === "vivant";
    let L = 0, H = 0, raf = 0, dernier = 0;
    const souris = { x: 0.7, y: 0.3, cx: 0.7, cy: 0.3 };
    let couleurs = { gain: "91,174,255", accent: "240,213,138", clair: false };

    const rgb = (v: string) => {
      const s = v.trim();
      const m = /^#([0-9a-f]{6})$/i.exec(s);
      return m ? [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)).join(",") : null;
    };
    const lireCouleurs = () => {
      const st = getComputedStyle(document.documentElement);
      couleurs = { gain: rgb(st.getPropertyValue("--gain")) ?? couleurs.gain, accent: rgb(st.getPropertyValue("--accent")) ?? couleurs.accent, clair: document.documentElement.dataset.theme === "clair" };
    };

    const nouvelle = (i: number, n: number): Courbe => {
      const nb = Math.ceil((L * 1.4) / PAS) + 3;
      let v = 0;
      const pts = Array.from({ length: nb }, () => (v += (Math.random() - 0.5) * 2 - v * 0.04));
      return { y: (i + 0.6) / (n + 0.4), amp: 18 + Math.random() * 34, vitesse: 5 + Math.random() * 9, pts, decalage: Math.random() * PAS, teinte: i % 3 === 2 ? "discret" : "gain" };
    };
    let courbes: Courbe[] = [];
    const redimensionner = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      L = window.innerWidth; H = window.innerHeight;
      canvas.width = L * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = vivant ? 9 : 6;
      courbes = Array.from({ length: n }, (_, i) => nouvelle(i, n));
      dessiner(0);
    };

    function dessiner(dt: number) {
      souris.cx += (souris.x - souris.cx) * 0.05;
      souris.cy += (souris.y - souris.cy) * 0.05;
      ctx!.clearRect(0, 0, L, H);
      const clair = couleurs.clair;

      // halo qui suit la souris
      const g = ctx!.createRadialGradient(souris.cx * L, souris.cy * H, 0, souris.cx * L, souris.cy * H, Math.max(L, H) * (vivant ? 0.42 : 0.34));
      g.addColorStop(0, `rgba(${couleurs.gain},${clair ? 0.1 : vivant ? 0.2 : 0.13})`);
      g.addColorStop(1, `rgba(${couleurs.gain},0)`);
      ctx!.fillStyle = g;
      ctx!.fillRect(0, 0, L, H);

      const alpha = (clair ? 0.2 : 0.15) * (vivant ? 1.7 : 1);
      courbes.forEach((c, i) => {
        c.decalage += c.vitesse * dt;
        while (c.decalage >= PAS) {                                  // la courbe avance : on retire un point à gauche, on en crée un à droite
          c.decalage -= PAS;
          const dernier = c.pts[c.pts.length - 1];
          c.pts.shift();
          c.pts.push(dernier + (Math.random() - 0.5) * 2 - dernier * 0.04);
        }
        const base = c.y * H + (souris.cy - 0.5) * (14 + i * 5);     // parallaxe : chaque courbe réagit un peu différemment
        ctx!.beginPath();
        c.pts.forEach((v, k) => {
          const x = k * PAS - c.decalage + (souris.cx - 0.5) * (-10 - i * 3);
          const y = base + v * c.amp * 0.5;
          if (k === 0) ctx!.moveTo(x, y); else ctx!.lineTo(x, y);
        });
        ctx!.strokeStyle = `rgba(${c.teinte === "gain" ? couleurs.gain : couleurs.accent},${c.teinte === "gain" ? alpha : alpha * 0.7})`;
        ctx!.lineWidth = vivant ? 1.6 : 1.2;
        ctx!.lineJoin = "round";
        ctx!.stroke();
      });
    }

    const boucle = (t: number) => {
      raf = requestAnimationFrame(boucle);
      if (document.hidden || t - dernier < 33) return;
      dessiner(Math.min((t - dernier) / 1000, 0.1));
      dernier = t;
    };
    const bouger = (e: MouseEvent) => { souris.x = e.clientX / window.innerWidth; souris.y = e.clientY / window.innerHeight; };

    lireCouleurs();
    redimensionner();
    window.addEventListener("resize", redimensionner);
    const observateur = new MutationObserver(() => { lireCouleurs(); if (reduit) dessiner(0); });
    observateur.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-palette"] });
    if (!reduit) {
      window.addEventListener("mousemove", bouger, { passive: true });
      raf = requestAnimationFrame(boucle);
    }
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", redimensionner);
      window.removeEventListener("mousemove", bouger);
      observateur.disconnect();
    };
  }, [fond]);

  if (fond === "aucun") return null;
  return <canvas ref={ref} className="fond-anime" aria-hidden="true" />;
}
