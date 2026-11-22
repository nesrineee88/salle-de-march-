"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

export default function BlocRepliable({
  titre,
  children,
  aide,
  ouvertParDefaut = false,
  cleMemoire,
}: {
  titre: string;
  children: ReactNode;
  aide?: string;
  ouvertParDefaut?: boolean;
  cleMemoire?: string;
}) {
  const [ouvert, setOuvert] = useState(ouvertParDefaut);

  useEffect(() => {
    if (!cleMemoire) return;
    try {
      const valeur = localStorage.getItem(`sdm.repliable.${cleMemoire}`);
      if (valeur === "ouvert" || valeur === "ferme") setOuvert(valeur === "ouvert");
    } catch {
      // Les préférences restent facultatives si le navigateur bloque le stockage.
    }
  }, [cleMemoire]);

  function changerOuverture(ouverte: boolean) {
    setOuvert(ouverte);
    if (!cleMemoire) return;
    try {
      localStorage.setItem(`sdm.repliable.${cleMemoire}`, ouverte ? "ouvert" : "ferme");
    } catch {
      // Le bloc reste utilisable même sans persistance des préférences.
    }
  }

  return (
    <details className="repliable" open={ouvert} onToggle={(e) => {
      const nouvelleOuverture = e.currentTarget.open;
      if (nouvelleOuverture !== ouvert) changerOuverture(nouvelleOuverture);
    }}>
      <summary>
        <span>{titre}</span>
        <ChevronDown size={16} aria-hidden="true" />
      </summary>
      {aide && <p className="aide">{aide}</p>}
      <div className="repliable-contenu">{children}</div>
    </details>
  );
}
