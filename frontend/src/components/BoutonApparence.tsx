"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Palette, RotateCcw } from "lucide-react";
import { DENSITES, MODELES, PALETTES, definirApparence, reinitialiserApparence, useApparence } from "@/lib/apparence";
import { definirTheme, useTheme } from "@/lib/theme";

/** Fenêtre « Apparence » : modèle de mise en page, thème, densité, bandeau. Tout se change en direct et se mémorise. */
export default function BoutonApparence() {
  const [ouvert, setOuvert] = useState(false);
  const zone = useRef<HTMLDivElement>(null);
  const id = useId();
  const a = useApparence();
  const theme = useTheme();

  useEffect(() => {
    if (!ouvert) return;
    const fermer = (e: MouseEvent) => { if (zone.current && !zone.current.contains(e.target as Node)) setOuvert(false); };
    const echap = (e: KeyboardEvent) => e.key === "Escape" && setOuvert(false);
    document.addEventListener("mousedown", fermer);
    document.addEventListener("keydown", echap);
    return () => { document.removeEventListener("mousedown", fermer); document.removeEventListener("keydown", echap); };
  }, [ouvert]);

  return (
    <div className="apparence" ref={zone}>
      <button type="button" className="btn-rond" data-info="Apparence" aria-label="Apparence" aria-haspopup="dialog" aria-expanded={ouvert} onClick={() => setOuvert(!ouvert)}>
        <Palette size={18} aria-hidden="true" />
      </button>
      {ouvert && (
        <div className="apparence-fenetre" role="dialog" aria-label="Apparence">
          <fieldset>
            <legend>Modèle</legend>
            <div className="modeles">
              {MODELES.map((m) => (
                <label key={m.cle} className="modele" data-choisi={a.modele === m.cle}>
                  <input type="radio" name={`${id}-modele`} checked={a.modele === m.cle} onChange={() => definirApparence({ modele: m.cle })} />
                  <span className={`modele-apercu modele-apercu-${m.cle}`} aria-hidden="true"><i /><i /><i /></span>
                  <span className="modele-nom">{m.nom}</span>
                  <small className="discret">{m.description}</small>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend>Couleurs</legend>
            <div className="palettes">
              {PALETTES.map((p) => (
                <label key={p.cle} className="palette" data-choisi={a.palette === p.cle}>
                  <input type="radio" name={`${id}-palette`} checked={a.palette === p.cle} onChange={() => definirApparence({ palette: p.cle })} />
                  <span className="palette-pastilles" aria-hidden="true">{p.teintes.map((t) => <i key={t} style={{ background: t }} />)}</span>
                  {p.nom}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend>Thème</legend>
            <div className="choix-ligne">
              {(["sombre", "clair"] as const).map((t) => (
                <label key={t} className="choix" data-choisi={theme === t}>
                  <input type="radio" name={`${id}-theme`} checked={theme === t} onChange={() => definirTheme(t)} />
                  {t === "sombre" ? "Sombre" : "Clair"}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend>Densité</legend>
            <div className="choix-ligne">
              {DENSITES.map((d) => (
                <label key={d.cle} className="choix" data-choisi={a.densite === d.cle}>
                  <input type="radio" name={`${id}-densite`} checked={a.densite === d.cle} onChange={() => definirApparence({ densite: d.cle })} />
                  {d.nom}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend>Ambiance</legend>
            <div className="choix-ligne">
              {([["aucun", "Fond fixe"], ["discret", "Fond animé discret"], ["vivant", "Fond animé vivant"]] as const).map(([cle, lib]) => (
                <label key={cle} className="choix" data-choisi={a.fond === cle}>
                  <input type="radio" name={`${id}-fond`} checked={a.fond === cle} onChange={() => definirApparence({ fond: cle })} />
                  {lib}
                </label>
              ))}
            </div>
            <label className="case"><input type="checkbox" checked={a.curseur} onChange={(e) => definirApparence({ curseur: e.target.checked })} /> Curseur lumineux</label>
            <p className="aide">Désactivés automatiquement si votre système demande moins d&apos;animations.</p>
          </fieldset>

          <fieldset>
            <legend>Affichage</legend>
            <label className="case"><input type="checkbox" checked={a.bandeau} onChange={(e) => definirApparence({ bandeau: e.target.checked })} /> Bandeau de cours</label>
            <label className="case"><input type="checkbox" checked={a.menuReplie} onChange={(e) => definirApparence({ menuReplie: e.target.checked })} /> Menu replié (icônes seules)</label>
          </fieldset>

          <button type="button" className="btn btn-icone-texte" onClick={reinitialiserApparence}><RotateCcw size={14} aria-hidden="true" /> Revenir aux réglages d&apos;origine</button>
        </div>
      )}
    </div>
  );
}