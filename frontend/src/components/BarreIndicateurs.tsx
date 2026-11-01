"use client";

import { AIDE, couleurs, LIBELLES, TOUS } from "@/lib/indicateurs";
import { useTheme } from "@/lib/theme";
import type { CleIndicateur, Indicateurs } from "@/lib/types";
import type { Mode } from "./Contexte";

interface Props {
  choix: CleIndicateur[];
  onChange: (c: CleIndicateur[]) => void;
  mode: Mode;
  parametres: Indicateurs["parametres"] | null;
}

function Cle({ couleur }: { couleur: string }) {
  return <i className="cle" style={{ background: couleur }} aria-hidden="true" />;
}

/** Cases à cocher des indicateurs, légende des courbes affichées et, en mode Apprenant, une explication par indicateur. */
export default function BarreIndicateurs({ choix, onChange, mode, parametres }: Props) {
  const COULEURS = couleurs(useTheme());
  const bascule = (k: CleIndicateur) => onChange(choix.includes(k) ? choix.filter((x) => x !== k) : [...choix, k]);
  const p = parametres;
  const legende: { couleur: string; texte: string }[] = [];
  if (choix.includes("sma")) legende.push({ couleur: COULEURS.sma_courte, texte: `SMA ${p?.sma_courte ?? 20}` }, { couleur: COULEURS.sma_longue, texte: `SMA ${p?.sma_longue ?? 50}` });
  if (choix.includes("ema")) legende.push({ couleur: COULEURS.ema, texte: `EMA ${p?.ema ?? 20}` });
  if (choix.includes("bollinger")) legende.push({ couleur: COULEURS.bollinger, texte: `Bollinger ${p?.bollinger.n ?? 20}, ±${p?.bollinger.k ?? 2} écarts-types` });
  if (choix.includes("rsi")) legende.push({ couleur: COULEURS.rsi, texte: `RSI ${p?.rsi ?? 14} (volet du bas)` });
  if (choix.includes("macd")) legende.push({ couleur: COULEURS.macd, texte: `MACD ${p?.macd.rapide ?? 12}/${p?.macd.lente ?? 26}` }, { couleur: COULEURS.macd_signal, texte: `signal ${p?.macd.signal ?? 9}` });

  return (
    <div className="indicateurs">
      <div className="indicateurs-choix" role="group" aria-label="Indicateurs techniques à afficher">
        <span className="indicateurs-titre">Indicateurs</span>
        {TOUS.map((k) => (
          <button key={k} className="puce" aria-pressed={choix.includes(k)} onClick={() => bascule(k)}>{LIBELLES[k]}</button>
        ))}
      </div>
      {legende.length > 0 && (
        <ul className="indicateurs-legende" aria-label="Légende des indicateurs">
          {legende.map((l) => <li key={l.texte}><Cle couleur={l.couleur} />{l.texte}</li>)}
        </ul>
      )}
      {mode === "apprenant" && choix.length > 0 && (
        <details className="indicateurs-aide">
          <summary>Que veulent dire ces indicateurs ?</summary>
          <div>
            {choix.map((k) => <p key={k}>{AIDE[k]}</p>)}
            <p>Ces indicateurs décrivent le passé : ils ne prédisent pas l&apos;avenir.</p>
          </div>
        </details>
      )}
    </div>
  );
}
