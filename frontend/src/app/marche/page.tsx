import PageMarche from "@/components/PageMarche";
import type { Classe } from "@/lib/types";

const CLASSES: Record<string, Classe> = {
  actions: "action",
  action: "action",
  crypto: "crypto",
  matieres: "matiere",
  matiere: "matiere",
};

export default async function Page({ searchParams }: {
  searchParams: Promise<{ classe?: string | string[] }>;
}) {
  const classeDemandee = (await searchParams).classe;
  const classe = typeof classeDemandee === "string" ? CLASSES[classeDemandee] ?? "action" : "action";
  return <PageMarche classe={classe} />;
}
