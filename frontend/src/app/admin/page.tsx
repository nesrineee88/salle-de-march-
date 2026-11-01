"use client";

import Admin from "@/components/Admin";
import { useMarche } from "@/components/Contexte";

export default function Page() {
  const { utilisateur } = useMarche();
  if (utilisateur.role !== "admin") {
    return <main className="page"><h1>Accès réservé</h1><p className="aide">Cette page est réservée aux administrateurs.</p></main>;
  }
  return <Admin />;
}
