import { pct } from "./format";
import type { Regle, TypeRegle } from "./types";

export const TYPES_REGLE: {
  type: TypeRegle; titre: string; champ: string; defaut: string; avecPart: boolean; partDefaut: string; aide: string;
}[] = [
  { type: "stop_loss", titre: "Stop-loss", champ: "Perte maximale", defaut: "30", avecPart: false, partDefaut: "100",
    aide: "Vend toute la position si le prix perd ce pourcentage par rapport à votre prix de revient. Sur un gap, la vente se fait au prix du marché, pas au seuil." },
  { type: "take_profit", titre: "Prise de profit", champ: "Gain visé", defaut: "50", avecPart: true, partDefaut: "50",
    aide: "Vend une partie de la position quand le prix gagne ce pourcentage : vous encaissez une partie du gain et gardez le reste." },
  { type: "stop_suiveur", titre: "Stop suiveur", champ: "Recul accepté", defaut: "10", avecPart: false, partDefaut: "100",
    aide: "Vend toute la position si le prix recule de ce pourcentage depuis son plus haut atteint depuis la pose. Il monte avec le prix, jamais il ne descend." },
  { type: "achat_complementaire", titre: "Achat complémentaire", champ: "Gain déclencheur", defaut: "50", avecPart: true, partDefaut: "25",
    aide: "Renforce la position quand elle gagne ce pourcentage : vous rachetez la part indiquée de ce que vous détenez, si vos liquidités le permettent." },
];

const MOTS: Record<TypeRegle, string> = {
  stop_loss: "Stop-loss", take_profit: "Prise de profit", stop_suiveur: "Stop suiveur", achat_complementaire: "Achat complémentaire",
};

/** Texte court d'une règle : « Stop-loss −30 % », « Prise de profit +50 % (vend 50 %) ». */
export function libelleRegle(r: Regle): string {
  const base = MOTS[r.type];
  const seuil = Math.abs(r.seuil);
  if (r.type === "stop_loss") return `${base} −${pct(seuil, 0)}${r.part < 1 ? ` (vend ${pct(r.part, 0)})` : ""}`;
  if (r.type === "stop_suiveur") return `${base} ${pct(seuil, 0)}`;
  if (r.type === "take_profit") return `${base} +${pct(seuil, 0)} (vend ${pct(r.part, 0)})`;
  return `${base} +${pct(seuil, 0)} (rachète ${pct(r.part, 0)})`;
}

export const LIBELLE_STATUT_REGLE: Record<Regle["statut"], string> = {
  active: "Active", declenchee: "Déclenchée", annulee: "Annulée", echec: "Échec",
};
