"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { ouvrirActif, variationCotation } from "@/lib/actif";
import { NOMS_CLASSES, prix, variation } from "@/lib/format";
import { pagesNavigation } from "@/lib/navigation";
import { useMarche } from "./Contexte";

type Resultat =
  | { type: "page"; cle: string; libelle: string; detail: string; href: string }
  | { type: "actif"; cle: string; libelle: string; detail: string; symbole: string; prix: string; v: number | null };

const normaliser = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Recherche globale (Ctrl+K) : un actif parmi tous ceux du simulateur, ou une page de l'application. */
export default function Recherche({ ouverte, fermer }: { ouverte: boolean; fermer: () => void }) {
  const { actifs, inst, utilisateur } = useMarche();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [index, setIndex] = useState(0);
  const champ = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (ouverte) { setQ(""); setIndex(0); setTimeout(() => champ.current?.focus(), 0); }
  }, [ouverte]);

  const resultats = useMemo<Resultat[]>(() => {
    const t = normaliser(q.trim());
    const pages: Resultat[] = pagesNavigation(utilisateur.role)
      .map((l) => ({ type: "page" as const, cle: l.href, libelle: l.libelle, detail: "Page", href: l.href }));
    const cot = new Map((inst?.cotations ?? []).map((c) => [c.symbole, c]));
    const lesActifs: Resultat[] = actifs.filter((a) => cot.has(a.symbole)).map((a) => {
      const c = cot.get(a.symbole)!;
      return { type: "actif" as const, cle: a.symbole, libelle: `${a.symbole} · ${a.nom}`, detail: a.secteur && a.secteur !== "-" ? `${NOMS_CLASSES[a.classe]} · ${a.secteur}` : NOMS_CLASSES[a.classe], symbole: a.symbole, prix: prix(c.prix), v: variationCotation(c) };
    });
    const filtre = (r: Resultat) => !t || normaliser(`${r.libelle} ${r.detail}`).includes(t);
    return [...lesActifs.filter(filtre).slice(0, 10), ...pages.filter(filtre).slice(0, t ? 5 : 4)];
  }, [q, actifs, inst, utilisateur.role]);

  if (!ouverte) return null;

  const choisir = (r: Resultat) => {
    fermer();
    if (r.type === "page") router.push(r.href);
    else { const a = actifs.find((x) => x.symbole === r.symbole); if (a) ouvrirActif(router, a); }
  };

  const touche = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); fermer(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setIndex((i) => Math.min(i + 1, resultats.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setIndex((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" && resultats[index]) { e.preventDefault(); choisir(resultats[index]); }
  };

  return (
    <div className="recherche-fond" onMouseDown={(e) => { if (e.target === e.currentTarget) fermer(); }}>
      <div className="recherche" role="dialog" aria-modal="true" aria-label="Recherche" onKeyDown={touche}>
        <div className="recherche-champ">
          <Search size={18} aria-hidden="true" />
          <input ref={champ} type="search" value={q} onChange={(e) => { setQ(e.target.value); setIndex(0); }}
            placeholder="Chercher un actif ou une page" aria-label="Chercher un actif ou une page"
            role="combobox" aria-expanded="true" aria-controls="recherche-liste" aria-activedescendant={resultats[index] ? `res-${resultats[index].cle}` : undefined} />
          <button type="button" className="btn-icone" onClick={fermer} aria-label="Fermer la recherche"><X size={16} aria-hidden="true" /></button>
        </div>
        <ul id="recherche-liste" className="recherche-liste" role="listbox">
          {resultats.length === 0 && <li className="vide">Rien ne correspond. Essayez un symbole (AAPL), un nom (pétrole) ou une page.</li>}
          {resultats.map((r, i) => (
            <li key={`${r.type}-${r.cle}`} id={`res-${r.cle}`} role="option" aria-selected={i === index}>
              <button type="button" className="recherche-ligne" data-actif={i === index} onMouseEnter={() => setIndex(i)} onClick={() => choisir(r)}>
                <span className="recherche-nom">{r.libelle}<small className="discret">{r.detail}</small></span>
                {r.type === "actif" && (
                  <span className="recherche-cours">
                    {r.prix} <small className={r.v !== null && r.v > 0 ? "gain" : r.v !== null && r.v < 0 ? "perte" : "discret"}>{variation(r.v)}</small>
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
        <p className="recherche-pied discret"><kbd>↑</kbd> <kbd>↓</kbd> pour choisir, <kbd>Entrée</kbd> pour ouvrir, <kbd>Échap</kbd> pour fermer.</p>
      </div>
    </div>
  );
}
