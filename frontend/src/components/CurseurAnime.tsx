"use client";

import { useEffect, useRef } from "react";
import { useApparence } from "@/lib/apparence";

const CIBLES = "a, button, input, select, textarea, label, summary, [role='tab'], [role='option'], [role='menuitem']";

/** Halo lumineux qui suit la souris et grossit sur les éléments cliquables. Le vrai curseur reste visible (accessibilité).
 *  Absent sur écran tactile et quand le système demande moins d'animations. */
export default function CurseurAnime() {
  const { curseur } = useApparence();
  const anneau = useRef<HTMLDivElement>(null);
  const point = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!curseur) return;
    if (window.matchMedia("(pointer: coarse), (prefers-reduced-motion: reduce)").matches) return;
    const a = anneau.current, p = point.current;
    if (!a || !p) return;
    let x = -100, y = -100, ax = -100, ay = -100, raf = 0, visible = false;

    const bouger = (e: MouseEvent) => {
      x = e.clientX; y = e.clientY;
      if (!visible) { visible = true; ax = x; ay = y; a.style.opacity = "1"; p.style.opacity = "1"; }
      const cible = (e.target as Element | null)?.closest?.(CIBLES);
      a.dataset.sur = cible ? "oui" : "non";
    };
    const sortir = () => { visible = false; a.style.opacity = "0"; p.style.opacity = "0"; };
    const appuyer = (b: boolean) => () => { a.dataset.appui = b ? "oui" : "non"; };
    const haut = appuyer(true), bas = appuyer(false);

    const boucle = () => {
      ax += (x - ax) * 0.2; ay += (y - ay) * 0.2;
      a.style.transform = `translate3d(${ax}px, ${ay}px, 0) translate(-50%, -50%)`;
      p.style.transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, -50%)`;
      raf = requestAnimationFrame(boucle);
    };
    raf = requestAnimationFrame(boucle);
    window.addEventListener("mousemove", bouger, { passive: true });
    document.addEventListener("mouseleave", sortir);
    window.addEventListener("mousedown", haut);
    window.addEventListener("mouseup", bas);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", bouger);
      document.removeEventListener("mouseleave", sortir);
      window.removeEventListener("mousedown", haut);
      window.removeEventListener("mouseup", bas);
    };
  }, [curseur]);

  if (!curseur) return null;
  return (
    <>
      <div ref={anneau} className="curseur-anneau" aria-hidden="true" data-sur="non" data-appui="non" />
      <div ref={point} className="curseur-point" aria-hidden="true" />
    </>
  );
}
