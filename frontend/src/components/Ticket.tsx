"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { montant, prix, quantite as fq } from "@/lib/format";
import type { Actif, CotationLigne, Ordre, Portefeuille, Verification } from "@/lib/types";
import type { Mode } from "./Contexte";

export interface CorpsOrdre {
  symbole: string;
  sens: "achat" | "vente";
  quantite: number;
  type: "marche" | "limite" | "stop";
  prix_limite?: number;
  prix_stop?: number;
}

interface Props {
  actif: Actif | undefined;
  cotation: CotationLigne | undefined;
  pf: Portefeuille | null;
  mode: Mode;
  onEnvoyer: (corps: CorpsOrdre) => Promise<Ordre>;
}

const AIDE_TYPE: Record<string, string> = {
  marche: "Exécuté tout de suite, aux meilleurs prix disponibles dans le carnet. Un gros ordre peut obtenir un prix moyen moins bon.",
  limite: "Exécuté seulement à votre prix ou mieux. S'il n'est pas atteint, l'ordre attend.",
  stop: "Se déclenche quand le prix touche votre niveau, puis passe au marché. Si le prix saute au-delà (un gap), vous obtenez le prix du marché, pas le vôtre.",
};

const nombre = (s: string) => Number(s.replace(/\s/g, "").replace(",", "."));

export default function Ticket({ actif, cotation, pf, mode, onEnvoyer }: Props) {
  const [sens, setSens] = useState<"achat" | "vente">("achat");
  const [type, setType] = useState<"marche" | "limite" | "stop">("marche");
  const [q, setQ] = useState("1");
  const [pLimite, setPLimite] = useState("");
  const [pStop, setPStop] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; texte: string } | null>(null);

  const [verif, setVerif] = useState<Verification | null>(null);
  const symbole = actif?.symbole;
  const quantiteSaisie = Number(q.replace(/\s/g, "").replace(",", "."));
  // Vérification du risque côté serveur, avec un court délai pendant la frappe. Les alertes ne bloquent jamais l'ordre.
  useEffect(() => {
    if (!symbole || !actif?.tradable || !Number.isFinite(quantiteSaisie) || quantiteSaisie <= 0) { setVerif(null); return; }
    const minuteur = setTimeout(() => {
      api<Verification>(`/api/v1/verification-ordre?symbole=${encodeURIComponent(symbole)}&sens=${sens}&quantite=${quantiteSaisie}`)
        .then(setVerif).catch(() => setVerif(null));
    }, 450);
    return () => clearTimeout(minuteur);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbole, sens, quantiteSaisie]);

  if (!actif) return <section className="ticket"><h2>Ordre</h2><p className="vide">Choisissez un actif dans la liste.</p></section>;

  const position = pf?.positions.find((p) => p.symbole === actif.symbole)?.quantite ?? 0;
  const prixCourant = cotation?.prix ?? null;
  const qte = nombre(q);
  const qteValide = Number.isFinite(qte) && qte > 0;
  const prixRef = type === "limite" ? nombre(pLimite) : type === "stop" ? nombre(pStop) : prixCourant;
  const estimation = qteValide && prixRef !== null && Number.isFinite(prixRef) ? qte * prixRef : null;

  const maxQte = sens === "vente" ? position : prixCourant && prixCourant > 0 && pf ? Math.floor((pf.cash_disponible / (prixCourant * 1.002)) * 1e4) / 1e4 : 0;
  const remplir = (part: number) => setQ(String(Math.floor(maxQte * part * 1e4) / 1e4));

  const manque =
    !actif.tradable ? "Cet indice sert de référence, il ne se négocie pas." :
    prixCourant === null ? "Pas de cotation à cette date." :
    !qteValide ? "Saisissez une quantité supérieure à zéro." :
    type === "limite" && !Number.isFinite(nombre(pLimite)) ? "Saisissez le prix limite." :
    type === "stop" && !Number.isFinite(nombre(pStop)) ? "Saisissez le prix du stop." : null;

  async function soumettre(e: React.FormEvent) {
    e.preventDefault();
    if (manque) return;
    setEnvoi(true);
    setMessage(null);
    try {
      const o = await onEnvoyer({
        symbole: actif!.symbole, sens, quantite: qte, type,
        prix_limite: type === "limite" ? nombre(pLimite) : undefined,
        prix_stop: type === "stop" ? nombre(pStop) : undefined,
      });
      const verbe = sens === "achat" ? "Acheté" : "Vendu";
      if (o.statut === "execute") setMessage({ ok: true, texte: `${verbe} : ${fq(o.quantite_executee)} × ${o.symbole} à ${prix(o.prix_moyen)} en moyenne.` });
      else if (o.statut === "annule") setMessage({ ok: true, texte: `${verbe} en partie : ${fq(o.quantite_executee)} × ${o.symbole}. ${o.motif ?? ""}` });
      else if (o.statut === "rejete") setMessage({ ok: false, texte: `Ordre refusé : ${o.motif ?? "motif inconnu"}.` });
      else setMessage({ ok: true, texte: `Ordre enregistré, en attente d'exécution${o.quantite_executee > 0 ? ` (${fq(o.quantite_executee)} déjà exécutés)` : ""}.` });
    } catch (err) {
      setMessage({ ok: false, texte: err instanceof Error ? err.message : "L'ordre n'a pas pu être envoyé." });
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <section className="ticket" aria-labelledby="titre-ticket">
      <h2 id="titre-ticket">Ordre sur {actif.symbole}</h2>
      <div className="onglets onglets-sens" role="tablist" aria-label="Sens de l'ordre">
        <button role="tab" aria-selected={sens === "achat"} data-sens="achat" className="onglet" onClick={() => setSens("achat")}>Acheter</button>
        <button role="tab" aria-selected={sens === "vente"} data-sens="vente" className="onglet" onClick={() => setSens("vente")}>Vendre</button>
      </div>

      <form onSubmit={soumettre} noValidate>
        <div className="champ">
          <label htmlFor="type-ordre">Type d&apos;ordre</label>
          <select id="type-ordre" value={type} onChange={(e) => setType(e.target.value as typeof type)}>
            <option value="marche">Au marché</option>
            <option value="limite">Limite</option>
            <option value="stop">Stop</option>
          </select>
          {mode === "apprenant" && <p className="aide">{AIDE_TYPE[type]}</p>}
        </div>

        <div className="champ">
          <label htmlFor="quantite">Quantité</label>
          <input id="quantite" inputMode="decimal" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="raccourcis" role="group" aria-label="Quantité en pourcentage du maximum">
            {[0.25, 0.5, 1].map((part) => (
              <button type="button" key={part} onClick={() => remplir(part)} disabled={maxQte <= 0}>{part * 100} %</button>
            ))}
          </div>
          <p className="aide">
            {sens === "vente" ? `Vous détenez ${fq(position)}.` : `Disponible : ${pf ? montant(pf.cash_disponible) : "–"} ${actif.devise}.`}
          </p>
        </div>

        {type === "limite" && (
          <div className="champ">
            <label htmlFor="prix-limite">Prix limite</label>
            <input id="prix-limite" inputMode="decimal" value={pLimite} onChange={(e) => setPLimite(e.target.value)} placeholder={prixCourant !== null ? prix(prixCourant) : ""} />
          </div>
        )}
        {type === "stop" && (
          <div className="champ">
            <label htmlFor="prix-stop">Prix du stop</label>
            <input id="prix-stop" inputMode="decimal" value={pStop} onChange={(e) => setPStop(e.target.value)} placeholder={prixCourant !== null ? prix(prixCourant) : ""} />
            {mode === "apprenant" && (
              <p className="aide">{sens === "vente" ? "Un stop de vente se place sous le prix actuel : c'est le stop-loss." : "Un stop d'achat se place au-dessus du prix actuel."}</p>
            )}
          </div>
        )}

        <dl className="recap">
          <div><dt>Prix actuel</dt><dd>{prix(prixCourant)}</dd></div>
          <div><dt>Montant estimé</dt><dd>{estimation !== null ? `${montant(estimation)} ${actif.devise}` : "–"}</dd></div>
        </dl>
        {mode === "apprenant" && <p className="aide">Des frais de courtage s&apos;ajoutent à chaque exécution.</p>}

        {verif && verif.alertes.length > 0 && (
          <ul className="alertes-risque" aria-label="Vérification du risque avant l'ordre">
            {verif.alertes.map((a) => (
              <li key={a.code} className={`alerte alerte-${a.niveau}`}>
                <span className="alerte-icone" aria-hidden="true">{a.niveau === "attention" ? "!" : "i"}</span>
                <span><span className="sr-only">{a.niveau === "attention" ? "Attention : " : "À savoir : "}</span>{a.texte}</span>
              </li>
            ))}
          </ul>
        )}

        {manque && <p className="aide" role="status">{manque}</p>}
        <button className={`btn btn-ordre ${sens === "achat" ? "btn-achat" : "btn-vente"}`} type="submit" disabled={envoi || !!manque}>
          {envoi ? "Envoi…" : `${sens === "achat" ? "Acheter" : "Vendre"} ${actif.symbole}`}
        </button>
      </form>

      <div aria-live="polite">
        {message && <p className={message.ok ? "message-ok" : "erreur"}>{message.texte}</p>}
      </div>
    </section>
  );
}
