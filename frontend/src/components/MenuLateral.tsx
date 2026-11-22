"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { BrainCircuit, CircleUserRound, LayoutDashboard, Newspaper, Settings, ShieldAlert, type LucideIcon } from "lucide-react";
import { PRINCIPALES, SECONDAIRES, estActif, visiblesPour, type LienNav } from "@/lib/navigation";
import { useMarche } from "./Contexte";
import Dialogue from "./ui/Dialogue";
import IconeSeance, { type NomIcone } from "./ui/IconeSeance";
import { Logo } from "./ui/Logo";

const TRACES: Record<string, NomIcone> = {
  "/": "dashboard",
  "/marche": "marche",
  "/portefeuille": "portefeuille",
  "/strategies": "analyse",
  "/jeu": "jeu",
  "/stress": "banque",
  "/formation": "ecole",
  "/actuariat": "bouclier",
  "/xai": "xai",
};
/** Pages rangées sous « Plus », absentes du prototype. */
const ICONES: Record<string, LucideIcon> = {
  "/actualites": Newspaper,
  "/credit": ShieldAlert,
  "/ia": BrainCircuit,
  "/compte": CircleUserRound,
  "/admin": Settings,
};

function Icone({ href }: { href: string }) {
  if (TRACES[href]) return <IconeSeance nom={TRACES[href]} />;
  const Dessin = ICONES[href] ?? LayoutDashboard;
  return <Dessin size={21} strokeWidth={1.7} aria-hidden="true" />;
}

/** Rail à gauche sur ordinateur, barre du bas sur téléphone. */
export default function MenuLateral() {
  const { utilisateur } = useMarche();
  const chemin = usePathname();
  const [plus, setPlus] = useState(false);
  const secondaires = visiblesPour(SECONDAIRES, utilisateur.role);
  const dansPlus = secondaires.some((l) => estActif(l, chemin));
  const horsBarreMobile = PRINCIPALES.filter((l) => !l.mobile);
  const cacheeMobile = horsBarreMobile.some((l) => estActif(l, chemin));

  const entreePlus = (lien: LienNav, mobileSeulement: boolean) => {
    return (
      <Link key={lien.href} href={lien.href} className={mobileSeulement ? "mobile-seulement" : undefined}
        aria-current={estActif(lien, chemin) ? "page" : undefined} onClick={() => setPlus(false)}>
        <Icone href={lien.href} />
        <span><strong>{lien.libelle}</strong><small>{lien.description}</small></span>
      </Link>
    );
  };

  return (
    <nav className="seance-rail" aria-label="Navigation principale">
      <Link href="/" className="seance-rail-logo" aria-label="Séance, dashboard"><Logo /></Link>
      {PRINCIPALES.map((lien) => {
        return (
          <Link key={lien.href} href={lien.href} title={lien.description} className="seance-nav"
            data-secondaire={!lien.mobile || undefined} aria-current={estActif(lien, chemin) ? "page" : undefined}>
            <Icone href={lien.href} /><span>{lien.libelle}</span>
          </Link>
        );
      })}
      <button type="button" className="seance-nav seance-nav-plus" data-actif={dansPlus || undefined}
        data-actif-mobile={cacheeMobile || undefined} aria-haspopup="dialog" onClick={() => setPlus(true)}>
        <IconeSeance nom="plus" /><span>Plus</span>
      </button>

      {plus && (
        <Dialogue titre="Plus de modules" fermer={() => setPlus(false)}>
          <div className="seance-plus">
            {horsBarreMobile.map((l) => entreePlus(l, true))}
            {secondaires.map((l) => entreePlus(l, false))}
          </div>
        </Dialogue>
      )}
    </nav>
  );
}
