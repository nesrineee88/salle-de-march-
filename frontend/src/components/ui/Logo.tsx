/** Le symbole de Séance : trois bougies décroissantes qui dessinent un bouton « lecture ». */
export function Logo({ taille = 36 }: { taille?: number }) {
  return (
    <svg className="seance-logo" width={taille} height={taille} viewBox="0 0 48 48" aria-hidden="true">
      <path d="M12.5 1v46" stroke="var(--accent)" strokeWidth="2" />
      <path d="M24.5 9v30" stroke="var(--turquoise)" strokeWidth="2" />
      <path d="M36.5 16v16" stroke="var(--turquoise-sombre)" strokeWidth="2" />
      <rect x="8" y="6" width="9" height="36" rx="2" fill="var(--accent)" />
      <rect x="20" y="13" width="9" height="22" rx="2" fill="var(--turquoise)" />
      <rect x="32" y="19.5" width="9" height="9" rx="2" fill="var(--turquoise-sombre)" />
    </svg>
  );
}

export function MotSeance() {
  return <span className="seance-mot">Séance<i>.</i></span>;
}
