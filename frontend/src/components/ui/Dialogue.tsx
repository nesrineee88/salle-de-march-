"use client";

import { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

/** Fenêtre modale native : focus enfermé, Échap pour fermer, retour du focus à la fermeture. À monter seulement quand elle est ouverte. */
export default function Dialogue({ titre, fermer, children }: { titre: string; fermer: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => {
    const d = ref.current;
    const avant = document.activeElement as HTMLElement | null;
    if (d && !d.open) d.showModal();
    return () => {
      if (d?.open) d.close();
      if (avant?.isConnected) avant.focus({ preventScroll: true });
    };
  }, []);
  return (
    <dialog ref={ref} className="seance-dialogue" aria-labelledby={id}
      onCancel={(e) => { e.preventDefault(); fermer(); }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) fermer(); }}>
      <div className="seance-dialogue-corps">
        <header>
          <h2 id={id}>{titre}</h2>
          <button type="button" className="btn-icone" onClick={fermer} aria-label="Fermer"><X size={18} aria-hidden="true" /></button>
        </header>
        {children}
      </div>
    </dialog>
  );
}
