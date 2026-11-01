"use client";

import { definirTheme, useTheme } from "@/lib/theme";

/** Bascule entre le thème sombre et le thème clair. Le choix est mémorisé dans le navigateur. */
export default function BoutonTheme() {
  const theme = useTheme();
  const versClair = theme === "sombre";
  return (
    <button className="btn btn-theme" onClick={() => definirTheme(versClair ? "clair" : "sombre")}
      aria-label={versClair ? "Passer au thème clair" : "Passer au thème sombre"} title={versClair ? "Thème clair" : "Thème sombre"}>
      <span aria-hidden="true">{versClair ? "☀" : "☾"}</span> {versClair ? "Clair" : "Sombre"}
    </button>
  );
}
