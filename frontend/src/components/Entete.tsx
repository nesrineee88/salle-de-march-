"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { CalendarDays, Search, Star } from "lucide-react";
import { dateCourte, entier } from "@/lib/format";
import { useSuivis } from "@/lib/suivis";
import { ouvrirDates, ouvrirDirect } from "@/lib/temps";
import { useMarche } from "./Contexte";
import { MotSeance } from "./ui/Logo";

interface Props {
  instant: string | null;
  ouvrirRecherche: () => void;
  suivisOuverts: boolean;
  basculerSuivis: () => void;
  signaler: (message: string) => void;
}

/** Barre du haut : marque, date, Rejeu ou Direct, recherche, valeur du portefeuille et compte. */
export default function Entete({ instant, ouvrirRecherche, suivisOuverts, basculerSuivis, signaler }: Props) {
  const { utilisateur, deconnecter, mode, setMode, inst, pf, quitterDirect } = useMarche();
  const { suivis } = useSuivis(utilisateur.email);
  const [menu, setMenu] = useState(false);
  const zone = useRef<HTMLDivElement>(null);
  const direct = inst?.direct ?? false;

  useEffect(() => {
    if (!menu) return;
    const fermer = (e: MouseEvent) => { if (zone.current && !zone.current.contains(e.target as Node)) setMenu(false); };
    const echap = (e: KeyboardEvent) => e.key === "Escape" && setMenu(false);
    document.addEventListener("mousedown", fermer);
    document.addEventListener("keydown", echap);
    return () => { document.removeEventListener("mousedown", fermer); document.removeEventListener("keydown", echap); };
  }, [menu]);

  async function rejeu() {
    if (!direct) return;
    try { await quitterDirect(); }
    catch (e) { signaler(e instanceof Error ? e.message : "Impossible de quitter le Direct."); }
  }

  return (
    <header className="seance-haut">
      <Link href="/" className="seance-haut-mot" aria-label="Séance, dashboard"><MotSeance /></Link>

      <button type="button" className="seance-date" onClick={ouvrirDates} disabled={!inst} aria-label="Changer la date">
        <CalendarDays size={16} aria-hidden="true" />
        <span>{instant ? dateCourte(instant) : "Connexion…"}</span>
      </button>

      <div className="seance-regime" role="group" aria-label="Origine des prix">
        <button type="button" aria-pressed={!direct} onClick={() => void rejeu()}>Rejeu</button>
        <button type="button" aria-pressed={direct} onClick={() => { if (!direct) ouvrirDirect(); }}><i aria-hidden="true" />Direct</button>
      </div>

      <button type="button" className="seance-recherche" onClick={ouvrirRecherche} aria-label="Chercher un actif ou une page (Ctrl+K)">
        <Search size={16} aria-hidden="true" /><span>Chercher</span><kbd>Ctrl K</kbd>
      </button>

      <div className="seance-haut-fin">
        <div className="seance-modes" role="group" aria-label="Niveau d’explication">
          <button type="button" aria-pressed={mode === "apprenant"} onClick={() => setMode("apprenant")}>Apprenant</button>
          <button type="button" aria-pressed={mode === "trader"} onClick={() => setMode("trader")}>Trader</button>
        </div>
        {pf && (
          <p className="seance-solde">
            <small>{direct && inst?.instant_compte ? `Au ${dateCourte(inst.instant_compte)}` : "Valeur totale"}</small>
            <strong>{entier(pf.equity)} USD</strong>
          </p>
        )}
        <button type="button" className="seance-icone" title="Mes suivis" aria-pressed={suivisOuverts} onClick={basculerSuivis}
          aria-label={`Mes suivis${suivis.length > 0 ? ` (${suivis.length})` : ""}`}>
          <Star size={18} aria-hidden="true" />{suivis.length > 0 && <span className="seance-pastille">{suivis.length}</span>}
        </button>
        <div className="seance-compte" ref={zone}>
          <button type="button" className="seance-avatar" aria-label={`Compte de ${utilisateur.nom}`} aria-haspopup="true" aria-expanded={menu} onClick={() => setMenu(!menu)}>
            {utilisateur.nom.charAt(0).toUpperCase()}
          </button>
          {menu && (
            <div className="menu menu-profil">
              <p className="menu-info">{utilisateur.email}<br />Rôle : {utilisateur.role}</p>
              <fieldset className="menu-choix">
                <legend>Mode</legend>
                <button type="button" aria-pressed={mode === "apprenant"} onClick={() => setMode("apprenant")}>Apprenant</button>
                <button type="button" aria-pressed={mode === "trader"} onClick={() => setMode("trader")}>Trader</button>
                <p className="aide">Apprenant : explications à côté des chiffres. Trader : mêmes données, moins d&apos;aide.</p>
              </fieldset>
              <Link href="/compte" onClick={() => setMenu(false)}>Mon compte</Link>
              {utilisateur.role === "admin" && <Link href="/admin" onClick={() => setMenu(false)}>Administration</Link>}
              <button type="button" onClick={() => void deconnecter()}>Se déconnecter</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
