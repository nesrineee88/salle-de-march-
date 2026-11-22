import type { Metadata } from "next";
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "./globals.css";
import "./seance.css";
import "./jeu.css";
import "./xai.css";
import "./protection.css";
import "./lecture.css";
import Coquille from "@/components/Coquille";

export const metadata: Metadata = {
  title: "Séance",
  description: "Simulateur de salle de marché : rejouez les marchés de 2019 à octobre 2026 avec de l'argent virtuel.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <Coquille>{children}</Coquille>
      </body>
    </html>
  );
}
