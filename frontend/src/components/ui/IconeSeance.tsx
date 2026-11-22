/** Les icônes dessinées pour l'identité Séance : les mêmes tracés que dans docs/design/seance-prototype.html. */
const TRACES = {
  dashboard: "M4 4h7v9H4zM15 4h5v5h-5zM15 13h5v7h-5zM4 17h7v3H4z",
  marche: "M6 3v3M6 15v6M4 6h4v9H4zM12 3v7M12 17v4M10 10h4v7h-4zM18 3v2M18 12v9M16 5h4v7h-4z",
  portefeuille: "M3 7h18v13H3zM8 7V4h8v3M3 12h18M10 12v3h4v-3",
  analyse: "M3 3v18h18M7 15l4-5 3 3 6-7",
  jeu: "M4 8h16v12H4zM4 8l1.5-4 14.5 2M9 4.5l1 3.5M14 5.2l1 2.8M10 11.5v5l5-2.5z",
  banque: "M3 9 12 3l9 6zM5 12v6M10 12v6M14 12v6M19 12v6M3 21h18",
  ecole: "M2 9l10-5 10 5-10 5zM6 11.5V17c3 3 9 3 12 0v-5.5M22 9v6",
  bouclier: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM8.5 12l2.5 2.5 4.5-5",
  xai: "M4 5h16v12h-9l-5 4v-4H4zM8.5 10v2M12 8.5v5M15.5 10v2",
  plus: "M5 12h.01M12 12h.01M19 12h.01",
} as const;

export type NomIcone = keyof typeof TRACES;

export default function IconeSeance({ nom, taille = 21 }: { nom: NomIcone; taille?: number }) {
  return (
    <svg className="seance-trace" width={taille} height={taille} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={nom === "plus" ? 3.5 : 1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={TRACES[nom]} />
    </svg>
  );
}
