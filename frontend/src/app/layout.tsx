import type { Metadata } from "next";
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "./globals.css";
import Coquille from "@/components/Coquille";
import { SCRIPT_THEME } from "@/lib/theme";

export const metadata: Metadata = {
  title: "Salle de marché",
  description: "Simulateur de salle de marché : rejouez les marchés de 2018 à octobre 2026 avec de l'argent virtuel.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_THEME }} />
      </head>
      <body>
        <Coquille>{children}</Coquille>
      </body>
    </html>
  );
}
