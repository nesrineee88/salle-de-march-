"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Menu, Search, Star } from "lucide-react";
import BoutonApparence from "./BoutonApparence";
import { useSuivis } from "@/lib/suivis";
import { useMarche } from "./Contexte";

interface Props {
  ouvrirRecherche: () => void;
  basculerMenuMobile: () => void;
  suivisOuverts: boolean;
  basculerSuivis: () => void;
}

/** Barre du haut : marque, recherche globale, suivis, apparence, mode et compte. La navigation est dans le menu latéral. */
export default function Entete({ ouvrirRecherche, basculerMenuMobile, suivisOuverts, basculerSuivis }: Props) {
  const { utilisateur, deconnecter } = useMarche();
  const { suivis } = useSuivis(utilisateur.email);
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

  return (
    <header className="entete">
      <button type="button" className="btn-icone menu-mobile" onClick={basculerMenuMobile} aria-label="Ouvrir le menu"><Menu size={20} aria-hidden="true" /></button>
      <Link href="/" className="marque">Salle de marché</Link>

      <button type="button" className="recherche-declencheur" onClick={ouvrirRecherche} aria-label="Chercher un actif ou une page (Ctrl+K)">
        <Search size={16} aria-hidden="true" />
        <span className="recherche-declencheur-texte">Chercher un actif ou une page</span>
        <kbd>Ctrl K</kbd>
      </button>

      <div className="entete-droite">
        <button type="button" className="btn-rond" data-info="Mes suivis" aria-label={`Mes suivis${suivis.length > 0 ? ` (${suivis.length})` : ""}`} aria-pressed={suivisOuverts} onClick={basculerSuivis}>
          <Star size={18} aria-hidden="true" />{suivis.length > 0 && <span className="badge-rond">{suivis.length}</span>}
        </button>
        <BoutonApparence />
        <div className="menu-utilisateur" ref={zone}>
          <button type="button" className="btn-rond btn-rond-avatar" data-info={utilisateur.nom} aria-label={`Compte de ${utilisateur.nom}`} aria-haspopup="menu" aria-expanded={menu} onClick={() => setMenu(!menu)}><span className="avatar-compte" aria-hidden="true">{utilisateur.nom.charAt(0).toUpperCase()}</span></button>
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