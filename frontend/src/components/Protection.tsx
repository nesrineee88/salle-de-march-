"use client";

import { useState } from "react";
import { ErreurApi } from "@/lib/api";
import { dateHeure, prix } from "@/lib/format";
import { LIBELLE_STATUT_REGLE, TYPES_REGLE, libelleRegle } from "@/lib/regles";
import type { Actif, Regle, TypeRegle } from "@/lib/types";
import { useMarche } from "./Contexte";

/** Règles automatiques posées sur la position de l'actif choisi : stop-loss, prise de profit, stop suiveur, achat complémentaire. */
export default function Protection({ actif }: { actif: Actif | undefined }) {
  const { pf, regles, mode, poserRegle, supprimerRegle } = useMarche();
  const [saisie, setSaisie] = useState<Record<string, { seuil: string; part: string }>>({});
  const [retour, setRetour] = useState<{ type: TypeRegle; ok: boolean; texte: string } | null>(null);
  const [envoi, setEnvoi] = useState<TypeRegle | null>(null);

  if (!actif || !actif.tradable) return null;
  const position = pf?.positions.find((p) => p.symbole === actif.symbole);
  const deLActif = regles.filter((r) => r.symbole === actif.symbole);

  const valeur = (t: (typeof TYPES_REGLE)[number]) => saisie[t.type] ?? { seuil: t.defaut, part: t.partDefaut };
  const maj = (type: TypeRegle, cle: "seuil" | "part", v: string, defaut: { seuil: string; part: string }) =>
    setSaisie({ ...saisie, [type]: { ...(saisie[type] ?? defaut), [cle]: v } });
  const nombre = (s: string) => Number(s.replace(",", "."));

  async function activer(t: (typeof TYPES_REGLE)[number]) {
    const v = valeur(t);
    setRetour(null);
    setEnvoi(t.type);
    try {
      const r = await poserRegle({ symbole: actif!.symbole, type: t.type, seuil_pct: nombre(v.seuil), part_pct: t.avecPart ? nombre(v.part) : 100 });
      setRetour({ type: t.type, ok: true, texte: `${libelleRegle(r)} : activé.` });
    } catch (e) {
      setRetour({ type: t.type, ok: false, texte: e instanceof ErreurApi ? e.message : "La règle n'a pas pu être posée." });
    } finally {
      setEnvoi(null);
    }
  }

  return (
    <section className="protection" aria-labelledby="titre-protection">
      <h2 id="titre-protection">Protection automatique</h2>
      {mode === "apprenant" && (
        <p className="aide">Des règles que le simulateur applique à votre place quand le prix franchit un seuil, calculé par rapport à votre prix de revient moyen. Elles agissent au marché : sur un gap, le prix obtenu peut être pire que le seuil.</p>
      )}
      {!position ? (
        <p className="vide">Aucune position sur {actif.symbole}. Achetez d&apos;abord : une règle protège une position existante.</p>
      ) : (
        <>
          <p className="protection-position">Prix de revient moyen : <strong>{prix(position.prix_moyen)}</strong> · prix actuel : <strong>{prix(position.prix_marche)}</strong></p>
          <ul className="regles-champs">
            {TYPES_REGLE.map((t) => {
              const active = deLActif.find((r) => r.type === t.type && r.statut === "active");
              const derniere = deLActif.find((r) => r.type === t.type && (r.statut === "declenchee" || r.statut === "echec"));
              const v = valeur(t);
              const defaut = { seuil: t.defaut, part: t.partDefaut };
              return (
                <li key={t.type} className="regle">
                  <div className="regle-tete">
                    <strong>{t.titre}</strong>
                    {active && <span className="pastille pastille-active">Active</span>}
                  </div>
                  {mode === "apprenant" && <p className="aide">{t.aide}</p>}
                  <div className="regle-champs">
                    <label>
                      <span className="sr-only">{t.champ} en pourcentage</span>
                      <input inputMode="decimal" value={v.seuil} onChange={(e) => maj(t.type, "seuil", e.target.value, defaut)} aria-label={`${t.titre} : ${t.champ} en pourcentage`} />
                    </label>
                    <span>%</span>
                    {t.avecPart && (
                      <>
                        <span className="discret">de la position :</span>
                        <input inputMode="decimal" value={v.part} onChange={(e) => maj(t.type, "part", e.target.value, defaut)} aria-label={`${t.titre} : part de la position en pourcentage`} />
                        <span>%</span>
                      </>
                    )}
                    <button className="btn" onClick={() => void activer(t)} disabled={envoi !== null}>{active ? "Remplacer" : "Activer"}</button>
                  </div>
                  {active && (
                    <p className="regle-etat">
                      {libelleRegle(active)} · se déclenche vers <strong>{active.niveau !== null ? prix(active.niveau) : "–"}</strong>
                      {t.type === "stop_suiveur" && active.plus_haut ? ` (plus haut suivi : ${prix(active.plus_haut)})` : ""}
                      {" "}<button className="lien" onClick={() => void supprimerRegle(active.id)}>Retirer</button>
                    </p>
                  )}
                  {!active && derniere && (
                    <p className="regle-etat discret">
                      {LIBELLE_STATUT_REGLE[derniere.statut]} {derniere.declenchee_le ? `le ${dateHeure(derniere.declenchee_le)}` : ""} : {derniere.motif}
                    </p>
                  )}
                  {retour && retour.type === t.type && <p className={retour.ok ? "message-ok" : "erreur"} role={retour.ok ? "status" : "alert"}>{retour.texte}</p>}
                </li>
              );
            })}
          </ul>
          {mode === "apprenant" && <p className="aide">Un seul stop-loss, une seule prise de profit… par actif : en poser une nouvelle remplace l&apos;ancienne. Si une règle solde toute la position, les autres sont annulées. La part s&apos;exprime en % de la position détenue (100 % = toute la position).</p>}
        </>
      )}
    </section>
  );
}
