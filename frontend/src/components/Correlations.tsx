"use client";

import { nombre } from "@/lib/format";
import { useTheme } from "@/lib/theme";

interface Props {
  symboles: string[];
  matrice: number[][];
  max?: number;
}

type Rvb = [number, number, number];
// Thème sombre : on part de la surface (#1D3043) vers le bleu et l'orange clairs. Thème clair : on part d'un gris très clair
// vers un bleu et un orange profonds. Le texte de chaque case est choisi selon sa luminosité.
const PALETTES: Record<"sombre" | "clair", { neutre: Rvb; positif: Rvb; negatif: Rvb }> = {
  sombre: { neutre: [29, 48, 67], positif: [91, 174, 255], negatif: [255, 146, 85] },
  clair: { neutre: [238, 242, 246], positif: [15, 111, 208], negatif: [194, 74, 20] },
};

function couleur(r: number, theme: "sombre" | "clair"): { fond: string; texte: string } {
  const { neutre: NEUTRE, positif: POSITIF, negatif: NEGATIF } = PALETTES[theme];
  const pole = r >= 0 ? POSITIF : NEGATIF;
  const t = Math.min(1, Math.abs(r));
  const [R, G, B] = NEUTRE.map((n, i) => Math.round(n + (pole[i] - n) * t));
  const lum = (0.2126 * R + 0.7152 * G + 0.0722 * B) / 255;
  return { fond: `rgb(${R}, ${G}, ${B})`, texte: lum > 0.5 ? "#0b1620" : "#ffffff" };
}

/** Carte de chaleur des corrélations entre les actifs détenus : bleu = ils bougent ensemble, orange = en sens opposés. */
export default function Correlations({ symboles, matrice, max = 10 }: Props) {
  const theme = useTheme();
  const n = Math.min(symboles.length, max);
  const noms = symboles.slice(0, n);
  return (
    <div className="correl">
      <div className="correl-grille" role="table" aria-label="Corrélations entre les actifs détenus" style={{ gridTemplateColumns: `4.5rem repeat(${n}, minmax(2.6rem, 1fr))` }}>
        <div role="row" className="correl-ligne">
          <span role="columnheader" aria-label="Actif" />
          {noms.map((s) => <span key={s} role="columnheader" className="correl-tete">{s.replace("-USD", "").replace("=F", "")}</span>)}
        </div>
        {noms.map((a, i) => (
          <div role="row" className="correl-ligne" key={a}>
            <span role="rowheader" className="correl-tete correl-tete-ligne">{a.replace("-USD", "").replace("=F", "")}</span>
            {noms.map((b, j) => {
              const r = matrice[i][j];
              const c = couleur(r, theme);
              return (
                <span key={b} role="cell" tabIndex={-1} className="correl-cellule" style={{ background: c.fond, color: c.texte }}
                  title={`${a} et ${b} : ${nombre(r, 2)}`}>
                  {i === j ? "1" : nombre(r, 2)}
                </span>
              );
            })}
          </div>
        ))}
      </div>
      <p className="correl-legende" aria-hidden="true">
        <span>−1 : sens opposés</span>
        <i className="correl-degrade" />
        <span>+1 : ensemble</span>
      </p>
      {symboles.length > n && <p className="aide">Seuls les {n} premiers actifs détenus sont affichés.</p>}
    </div>
  );
}
