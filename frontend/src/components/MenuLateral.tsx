"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity, BrainCircuit, Briefcase, Bitcoin, Calculator, FlaskConical, Gem, GraduationCap, LayoutDashboard, Newspaper,
  PanelLeftClose, PanelLeftOpen, Settings, ShieldAlert, TrendingUp, UserRound, type LucideIcon,
} from "lucide-react";
import { NAVIGATION } from "@/lib/navigation";
import { definirApparence, useApparence } from "@/lib/apparence";
import { useMarche } from "./Contexte";

const ICONES: Record<string, LucideIcon> = {
  "/": LayoutDashboard,
  "/actions": TrendingUp,
  "/crypto": Bitcoin,
  "/matieres": Gem,
  "/portefeuille": Briefcase,
  "/strategies": FlaskConical,
  "/actualites": Newspaper,
  "/ia": BrainCircuit,
  "/credit": ShieldAlert,
  "/stress": Activity,
  "/actuariat": Calculator,
  "/formation": GraduationCap,
  "/compte": UserRound,
  "/admin": Settings,
};

interface Section { titre: string | null; liens: { href: string; libelle: string; description?: string }[] }

/** Découpe la navigation en sections : les liens isolés forment une section sans titre, chaque groupe devient une section. */
function sections(estAdmin: boolean): Section[] {
  const res: Section[] = [];
  let isoles: Section["liens"] = [];
  const viderIsoles = () => { if (isoles.length) { res.push({ titre: null, liens: isoles }); isoles = []; } };
  for (const e of NAVIGATION) {
    if ("liens" in e && e.liens) { viderIsoles(); res.push({ titre: e.libelle, liens: e.liens }); }
    else if (e.href) isoles.push({ href: e.href, libelle: e.libelle });
  }
  viderIsoles();
  if (estAdmin) res.push({ titre: "Gestion", liens: [{ href: "/admin", libelle: "Administration" }] });
  return res;
}

export default function MenuLateral({ ouvertMobile, fermerMobile }: { ouvertMobile: boolean; fermerMobile: () => void }) {
  const { utilisateur } = useMarche();
  const { menuReplie } = useApparence();
  const chemin = usePathname();
  const actif = (href: string) => (href === "/" ? chemin === "/" : chemin.startsWith(href));
  const replie = menuReplie && !ouvertMobile;

  return (
    <>
      {ouvertMobile && <button type="button" className="menu-voile" aria-label="Fermer le menu" onClick={fermerMobile} />}
      <nav className="menu-lateral" aria-label="Pages" data-replie={replie} data-mobile={ouvertMobile}>
                <button type="button" className="menu-bascule-haut" onClick={() => definirApparence({ menuReplie: !menuReplie })}
          aria-pressed={menuReplie} aria-label={menuReplie ? "Déplier le menu" : "Replier le menu"} title={menuReplie ? "Déplier le menu" : "Replier le menu"}>
          {menuReplie ? <PanelLeftOpen size={18} aria-hidden="true" /> : <PanelLeftClose size={18} aria-hidden="true" />}
          {!replie && <span>Réduire le menu</span>}
        </button>
        <div className="menu-lateral-liste">
          {sections(utilisateur.role === "admin").map((s, i) => (
            <section key={s.titre ?? `s${i}`} className="menu-section">
              {s.titre && !replie && <h2 className="menu-section-titre">{s.titre}</h2>}
              {s.titre && replie && <hr className="menu-section-trait" />}
              <ul>
                {s.liens.map((l) => {
                  const Icone = ICONES[l.href] ?? LayoutDashboard;
                  return (
                    <li key={l.href}>
                      <Link href={l.href} className="menu-lien" aria-current={actif(l.href) ? "page" : undefined}
                        title={replie ? l.libelle : l.description} aria-label={replie ? l.libelle : undefined} onClick={fermerMobile}>
                        <Icone size={18} aria-hidden="true" />
                        {!replie && <span>{l.libelle}</span>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
        <button type="button" className="menu-lien menu-bascule-bas" onClick={() => definirApparence({ menuReplie: !menuReplie })}
          aria-pressed={menuReplie} aria-label={menuReplie ? "Déplier le menu" : "Replier le menu"} title={menuReplie ? "Déplier le menu" : "Replier le menu"}>
          {menuReplie ? <PanelLeftOpen size={18} aria-hidden="true" /> : <PanelLeftClose size={18} aria-hidden="true" />}
          {!replie && <span>Replier</span>}
        </button>
      </nav>
    </>
  );
}
