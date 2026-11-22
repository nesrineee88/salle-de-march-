/** Affiches originales, dessinées en SVG : aucune image à télécharger, le jeu marche sans internet. */

function tirage(graine: number) {
  let g = graine;
  return () => {
    g = (g + 0x6d2b79f5) | 0;
    let t = Math.imul(g ^ (g >>> 15), 1 | g);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const VILLE = (() => {
  const r = tirage(11);
  return Array.from({ length: 13 }, (_, i) => {
    const h = Math.round(70 + r() * 135);
    const fenetres: [number, number][] = [];
    for (let y = 340 - h; y < 315; y += 17) if (r() > 0.6) fenetres.push([Math.round(i * 31 + 6 + r() * 10), y]);
    return { x: i * 31, h, fenetres };
  });
})();

function Virus() {
  return (
    <>
      <circle cx="200" cy="120" r="54" fill="none" stroke="#3be3ea" strokeWidth="3" />
      {Array.from({ length: 14 }, (_, i) => {
        const a = (i * Math.PI) / 7;
        const p = (r: number) => `${(200 + Math.cos(a) * r).toFixed(1)} ${(120 + Math.sin(a) * r).toFixed(1)}`;
        return <path key={i} d={`M${p(54)}L${p(73)}`} stroke="#3be3ea" strokeWidth="3" strokeLinecap="round" />;
      })}
      {VILLE.map((b) => (
        <g key={b.x}>
          <rect x={b.x} y={330 - b.h} width="28" height={b.h} fill="#061423" />
          {b.fenetres.map(([x, y]) => <rect key={`${x}-${y}`} x={x} y={y} width="6" height="7" fill="#f2c46d" opacity="0.75" />)}
        </g>
      ))}
    </>
  );
}

function Guichet() {
  return (
    <>
      <path d="M62 168L200 92 338 168Z" fill="#1b4c70" stroke="#3be3ea" strokeWidth="3" />
      {[0, 1, 2, 3, 4].map((i) => (
        <rect key={i} x={84 + i * 54} y="174" width="26" height={i === 2 ? 70 : 128} fill="#1b4c70" stroke="#3be3ea" strokeOpacity="0.7" strokeWidth="2" />
      ))}
      <path d="M200 92l-9 34 16 22-19 28 17 30-10 24" fill="none" stroke="#ff8580" strokeWidth="4" />
      <path d="M186 302l30-34 26 34Z" fill="#0b1d31" />
      <rect x="56" y="304" width="288" height="14" fill="#0b1d31" />
    </>
  );
}

function Coffre() {
  return (
    <>
      <circle cx="200" cy="170" r="100" fill="#0b1d31" stroke="#8b7cf0" strokeWidth="5" />
      <circle cx="200" cy="170" r="76" fill="none" stroke="#8b7cf0" strokeOpacity="0.5" strokeWidth="2" />
      <rect x="158" y="160" width="84" height="70" rx="8" fill="#14264a" stroke="#edf5fb" strokeWidth="3" />
      <path d="M172 160v-24a28 28 0 0 1 56 0v24" fill="none" stroke="#edf5fb" strokeWidth="6" />
      <path d="M200 184v24" stroke="#3be3ea" strokeWidth="7" />
      <path d="M140 88l22 34-18 16 25 30M270 262l-20-26 12-18" stroke="#3be3ea" fill="none" strokeWidth="2" />
    </>
  );
}

function Bobine() {
  return (
    <>
      <path d="M200 70L80 340h240Z" fill="#3be3ea" opacity="0.08" />
      <circle cx="200" cy="170" r="92" fill="#0b1d31" stroke="#3be3ea" strokeWidth="4" />
      {[0, 1, 2, 3, 4].map((i) => {
        const a = i * 1.2566 - 1.57;
        return <circle key={i} cx={(200 + Math.cos(a) * 54).toFixed(1)} cy={(170 + Math.sin(a) * 54).toFixed(1)} r="19" fill="#15283f" />;
      })}
      <text x="200" y="191" textAnchor="middle" fontSize="64" fontWeight="700" fill="#edf5fb" className="obscure-affiche-signe">?</text>
    </>
  );
}

const DECORS: Record<string, { ciel: string; dessin: () => React.JSX.Element }> = {
  covid: { ciel: "#0d4650", dessin: Virus },
  crypto: { ciel: "#2f2450", dessin: Coffre },
  "2008": { ciel: "#123a5c", dessin: Guichet },
  mystere: { ciel: "#15283f", dessin: Bobine },
};

export default function Affiche({ film }: { film: string }) {
  const { ciel, dessin: Dessin } = DECORS[film] ?? DECORS.mystere;
  const id = `obscure-ciel-${film}`;
  return (
    <svg viewBox="0 0 400 330" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop stopColor={ciel} />
          <stop offset="1" stopColor="#050e1a" />
        </linearGradient>
      </defs>
      <rect width="400" height="330" fill={`url(#${id})`} />
      <Dessin />
    </svg>
  );
}
