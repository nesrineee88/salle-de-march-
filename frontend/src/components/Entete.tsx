"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { NAVIGATION, type GroupeNav } from "@/lib/navigation";
import BoutonTheme from "./BoutonTheme";
import { useMarche } from "./Contexte";

function Groupe({ groupe, actif }: { groupe: GroupeNav; actif: boolean }) {
  const [ouvert, setOuvert] = useState(false);
  const zone = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ouvert) return;
    const fermer = (e: MouseEvent) => { if (zone.current && !zone.current.contains(e.target as Node)) setOuvert(false); };
    const echap = (e: KeyboardEvent) => e.key === "Escape" && setOuvert(false);
    document.addEventListener("mousedown", fermer);
    document.addEventListener("keydown", echap);
    return () => { document.removeEventListener("mousedown", fermer); document.removeEventListener("keydown", echap); };
  }, [ouvert]);
  return (
    <div className="nav-groupe" ref={zone}>
      <button className="nav-lien nav-bouton" aria-haspopup="menu" aria-expanded={ouvert} aria-current={actif ? "page" : undefined} onClick={() => setOuvert(!ouvert)}>
        {groupe.libelle} <span aria-hidden="true" className="nav-fleche">▾</span>
      </button>
      {ouvert && (
        <ul className="menu nav-menu" role="menu">
          {groupe.liens.map((l) => (
            <li key={l.href} role="none">
              <Link role="menuitem" href={l.href} onClick={() => setOuvert(false)}>
                {l.libelle}
                {l.description && <small className="discret"> {l.description}</small>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Entete() {
  const { utilisateur, mode, setMode, deconnecter } = useMarche();
  const chemin = usePathname();
  const [menu, setMenu] = useState(false);
  const zone = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menu) return;
    const fermer = (e: MouseEvent) => { if (zone.current && !zone.current.contains(e.target as Node)) setMenu(false); };
    const echap = (e: KeyboardEvent) => e.key === "Escape" && setMenu(false);
    document.addEventListener("mousedown", fermer);
    document.addEventListener("keydown", echap);
    return () => { document.removeEventListener("mousedown", fermer); document.removeEventListener("keydown", echap); };
  }, [menu]);

  const entrees = utilisateur.role === "admin" ? [...NAVIGATION, { href: "/admin", libelle: "Administration" }] : NAVIGATION;
  const actif = (href: string) => (href === "/" ? chemin === "/" : chemin.startsWith(href));

  return (
    <header className="entete">
      <Link href="/" className="marque">Salle de marché</Link>
      <nav className="navigation" aria-label="Pages">
        {entrees.map((e) =>
          "liens" in e && e.liens ? (
            <Groupe key={e.libelle} groupe={e} actif={e.liens.some((l) => actif(l.href))} />
          ) : (
            <Link key={e.href} href={e.href!} className="nav-lien" aria-current={actif(e.href!) ? "page" : undefined}>{e.libelle}</Link>
          ),
        )}
      </nav>
      <div className="entete-droite">
        <BoutonTheme />
        <div className="modes" role="group" aria-label="Mode d'affichage">
          <button aria-pressed={mode === "apprenant"} onClick={() => setMode("apprenant")}>Apprenant</button>
          <button aria-pressed={mode === "trader"} onClick={() => setMode("trader")}>Trader</button>
        </div>
        <div className="menu-utilisateur" ref={zone}>
          <button className="btn" aria-haspopup="menu" aria-expanded={menu} onClick={() => setMenu(!menu)}>{utilisateur.nom}</button>
          {menu && (
            <ul className="menu" role="menu">
              <li role="none"><p className="menu-info">{utilisateur.email}<br />Rôle : {utilisateur.role}</p></li>
              <li role="none"><Link role="menuitem" href="/compte" onClick={() => setMenu(false)}>Mon compte</Link></li>
              <li role="none"><button role="menuitem" onClick={deconnecter}>Se déconnecter</button></li>
            </ul>
          )}
        </div>
      </div>
    </header>
  );
}
