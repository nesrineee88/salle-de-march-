"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ExternalLink, Star, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import { avatarActif, lienActif, variationCotation } from "@/lib/actif";
import { NOMS_CLASSES, nombre, pctSigne, prix, variation } from "@/lib/format";
import { useLecture } from "@/lib/hooks";
import { useSuivis } from "@/lib/suivis";
import type { Actualite, Barre } from "@/lib/types";
import { useMarche } from "./Contexte";
import Graphique from "./Graphique";

interface Profil {
  symbole: string; nom: string; classe: string; secteur: string; devise: string; calendrier: string; tradable: boolean;
  premiere_cotation?: string; derniere_cotation?: string;
  description: { texte: string; source: string; url: string | null; lu_le: string } | null;
}

const ONGLETS = ["À propos", "Graphique", "Actualités", "Indicateurs", "Ma position"] as const;
type Onglet = (typeof ONGLETS)[number];
const JOUR = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const jourFr = (iso: string) => JOUR.format(Date.parse(`${iso.slice(0, 10)}T00:00:00Z`));

function Fait({ libelle, valeur }: { libelle: string; valeur: React.ReactNode }) {
  return <div className="fait"><dt>{libelle}</dt><dd>{valeur}</dd></div>;
}

/** Fiche d'un actif, comme un profil d'entreprise : en-tête, bouton Suivre, puis cinq onglets. */
export default function FicheActif({ symbole }: { symbole: string }) {
  const { actifs, inst, pf, ordres, utilisateur } = useMarche();
  const { estSuivi, basculer } = useSuivis(utilisateur.email);
  const [onglet, setOnglet] = useState<Onglet>("À propos");
  const [barres, setBarres] = useState<Barre[]>([]);
  const refOnglets = useRef<(HTMLButtonElement | null)[]>([]);

  const actif = actifs.find((a) => a.symbole === symbole);
  const cotation = inst?.cotations.find((c) => c.symbole === symbole);
  const v = cotation ? variationCotation(cotation) : null;
  const enc = encodeURIComponent(symbole);
  const { donnees: profil } = useLecture<Profil>(`/api/v1/actifs/${enc}/profil`, 600000);
  const { donnees: actus } = useLecture<{ actualites: Actualite[] }>(onglet === "Actualités" ? `/api/v1/actualites?symbole=${enc}&limite=30` : null, 8000);

  useEffect(() => {
    let vivant = true;
    const lire = () => api<Barre[]>(`/api/v1/historique/${enc}?barres=300`).then((b) => vivant && setBarres(b)).catch(() => undefined);
    void lire();
    const t = setInterval(() => { if (document.visibilityState === "visible") void lire(); }, 4000);
    return () => { vivant = false; clearInterval(t); };
  }, [enc]);

  const stats = useMemo(() => {
    const c = barres.filter((b) => !b.en_formation).map((b) => b.close);
    if (c.length < 2) return null;
    const dernier = c[c.length - 1];
    const sur = (n: number) => (c.length > n ? dernier / c[c.length - 1 - n] - 1 : null);
    const rend = c.slice(1).map((x, i) => x / c[i] - 1);
    const moy = rend.reduce((a, b) => a + b, 0) / rend.length;
    const ecart = Math.sqrt(rend.reduce((a, b) => a + (b - moy) ** 2, 0) / Math.max(rend.length - 1, 1));
    const an = actif?.calendrier === "continu" ? 365 : 252;
    const fenetre = c.slice(-252);
    return { m1: sur(21), m3: sur(63), a1: sur(252), haut: Math.max(...fenetre), bas: Math.min(...fenetre), vol: ecart * Math.sqrt(an), n: c.length };
  }, [barres, actif]);

  if (!actif) {
    return (
      <main className="page">
        <p className="vide panneau">Cet actif n&apos;existe pas dans le simulateur. <Link href="/actions">Retour aux marchés</Link></p>
      </main>
    );
  }

  const av = avatarActif(actif);
  const position = pf?.positions.find((p) => p.symbole === symbole);
  const ordresActif = ordres.filter((o) => o.symbole === symbole);
  const sens = v !== null && v > 0 ? "gain" : v !== null && v < 0 ? "perte" : "";
  const suivi = estSuivi(symbole);

  const toucheOnglet = (e: React.KeyboardEvent, i: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const j = (i + (e.key === "ArrowRight" ? 1 : ONGLETS.length - 1)) % ONGLETS.length;
    setOnglet(ONGLETS[j]);
    refOnglets.current[j]?.focus();
  };

  return (
    <main className="page fiche">
      <Link href="/actions" className="fiche-retour"><ArrowLeft size={14} aria-hidden="true" /> Marchés</Link>

      <header className="fiche-tete panneau">
        <span className="avatar-actif" style={{ ["--teinte" as string]: av.teinte }} aria-hidden="true">{av.initiales}</span>
        <div className="fiche-titre">
          <h1>{actif.nom} <span className="discret">· {symbole}</span></h1>
          <p className="discret">{actif.secteur && actif.secteur !== "-" ? `${actif.secteur} · ` : ""}{NOMS_CLASSES[actif.classe] ?? actif.classe}</p>
        </div>
        <div className="fiche-cours">
          <strong className="fiche-prix">{cotation ? prix(cotation.prix) : "—"} <small className="discret">{actif.devise}</small></strong>
          <span className={sens}>{v !== null && v !== 0 ? (v > 0 ? "▲ " : "▼ ") : ""}{variation(v)}</span>
        </div>
        <div className="fiche-actions">
          <button type="button" className="btn btn-icone-texte" aria-pressed={suivi} onClick={() => basculer(symbole)}>
            <Star size={16} aria-hidden="true" fill={suivi ? "currentColor" : "none"} /> {suivi ? "Suivi" : "Suivre"}
          </button>
          {actif.tradable && <Link className="btn btn-principal btn-icone-texte" href={lienActif(actif)}><TrendingUp size={16} aria-hidden="true" /> Trader</Link>}
        </div>
      </header>

      <div className="onglets onglets-fiche" role="tablist" aria-label={`Fiche ${symbole}`}>
        {ONGLETS.map((o, i) => (
          <button key={o} ref={(el) => { refOnglets.current[i] = el; }} role="tab" id={`onglet-${i}`} aria-selected={onglet === o} aria-controls="panneau-fiche"
            tabIndex={onglet === o ? 0 : -1} className="onglet" onClick={() => setOnglet(o)} onKeyDown={(e) => toucheOnglet(e, i)}>{o}</button>
        ))}
      </div>

      <section id="panneau-fiche" role="tabpanel" aria-labelledby={`onglet-${ONGLETS.indexOf(onglet)}`} className="fiche-corps">
        {onglet === "À propos" && (
          <div className="fiche-apropos">
            <div className="panneau">
              <h2>À propos</h2>
              {profil?.description ? (
                <>
                  <p className="fiche-description">{profil.description.texte}</p>
                  <p className="aide">Source : {profil.description.url ? <a href={profil.description.url} target="_blank" rel="noreferrer">{profil.description.source} <ExternalLink size={12} aria-hidden="true" /></a> : profil.description.source}, lu le {jourFr(profil.description.lu_le)}.</p>
                </>
              ) : (
                <p className="discret">Aucune description disponible pour le moment (la source, Wikipédia, n&apos;a pas répondu). Les données ci-contre viennent du catalogue du simulateur.</p>
              )}
            </div>
            <div className="panneau">
              <h2>Fiche technique</h2>
              <dl className="faits">
                <Fait libelle="Type" valeur={NOMS_CLASSES[actif.classe] ?? actif.classe} />
                {actif.secteur && actif.secteur !== "-" && <Fait libelle="Secteur" valeur={actif.secteur} />}
                <Fait libelle="Devise" valeur={actif.devise} />
                <Fait libelle="Séances" valeur={actif.calendrier === "continu" ? "7 jours sur 7" : "Du lundi au vendredi"} />
                <Fait libelle="Négociable" valeur={actif.tradable ? "Oui" : "Non (référence seulement)"} />
                {profil?.premiere_cotation && <Fait libelle="Données" valeur={`${jourFr(profil.premiere_cotation)} → ${jourFr(profil.derniere_cotation ?? profil.premiere_cotation)}`} />}
              </dl>
            </div>
          </div>
        )}

        {onglet === "Graphique" && (
          <div className="panneau">
            {barres.length > 0 ? <Graphique barres={barres} symbole={symbole} /> : <p className="vide">Pas encore de bougies à cette date : avancez dans le temps.</p>}
          </div>
        )}

        {onglet === "Actualités" && (
          <div className="fiche-actus">
            {(actus?.actualites ?? []).length === 0 && <p className="vide panneau">Aucune actualité parue sur cet actif à votre date simulée.</p>}
            {(actus?.actualites ?? []).map((a) => (
              <article key={a.id} className="panneau actu">
                <p className="aide">{jourFr(a.date)} · {a.type_source === "historique" ? "Repère historique" : "Actualité fictive"}</p>
                <h3>{a.titre}</h3>
                {a.texte && <p>{a.texte}</p>}
              </article>
            ))}
            <p className="aide">Toutes les actualités et leur analyse de ton : page « Actualités et sentiment ».</p>
          </div>
        )}

        {onglet === "Indicateurs" && (
          <div className="panneau">
            <h2>Repères chiffrés</h2>
            {stats ? (
              <>
                <dl className="faits">
                  <Fait libelle="Sur 1 mois" valeur={stats.m1 === null ? "—" : <span className={stats.m1 >= 0 ? "gain" : "perte"}>{stats.m1 >= 0 ? "▲ " : "▼ "}{pctSigne(stats.m1, 1)}</span>} />
                  <Fait libelle="Sur 3 mois" valeur={stats.m3 === null ? "—" : <span className={stats.m3 >= 0 ? "gain" : "perte"}>{stats.m3 >= 0 ? "▲ " : "▼ "}{pctSigne(stats.m3, 1)}</span>} />
                  <Fait libelle="Sur 1 an" valeur={stats.a1 === null ? "—" : <span className={stats.a1 >= 0 ? "gain" : "perte"}>{stats.a1 >= 0 ? "▲ " : "▼ "}{pctSigne(stats.a1, 1)}</span>} />
                  <Fait libelle="Plus haut (1 an)" valeur={prix(stats.haut)} />
                  <Fait libelle="Plus bas (1 an)" valeur={prix(stats.bas)} />
                  <Fait libelle="Volatilité annualisée" valeur={`${nombre(stats.vol * 100, 1)} %`} />
                </dl>
                <p className="aide">Calculé sur les {stats.n} dernières séances terminées avant votre date simulée. La volatilité mesure l&apos;ampleur habituelle des variations : plus elle est haute, plus le prix bouge.</p>
              </>
            ) : <p className="vide">Pas assez de séances à cette date pour calculer des repères.</p>}
            <p className="aide">Moyennes mobiles, RSI, MACD et Bandes de Bollinger se tracent sur la page de négociation.</p>
          </div>
        )}

        {onglet === "Ma position" && (
          <div className="panneau">
            <h2>Ma position</h2>
            {position ? (
              <dl className="faits">
                <Fait libelle="Quantité" valeur={nombre(position.quantite, 4)} />
                <Fait libelle="Prix moyen d'achat" valeur={prix(position.prix_moyen)} />
                <Fait libelle="Valeur actuelle" valeur={`${prix(position.valeur)} ${actif.devise}`} />
                <Fait libelle="Gain ou perte latent" valeur={<span className={position.pnl_latent >= 0 ? "gain" : "perte"}>{position.pnl_latent >= 0 ? "▲ +" : "▼ "}{prix(position.pnl_latent)}</span>} />
                <Fait libelle="Poids du portefeuille" valeur={`${nombre(position.poids * 100, 1)} %`} />
              </dl>
            ) : <p className="discret">Vous ne détenez pas cet actif.</p>}
            {ordresActif.length > 0 && <p className="aide">{ordresActif.length} ordre(s) enregistré(s) sur cet actif (détail dans la page Portefeuille).</p>}
            {actif.tradable && <Link className="btn btn-principal btn-icone-texte" href={lienActif(actif)}><TrendingUp size={16} aria-hidden="true" /> Passer un ordre sur {symbole}</Link>}
          </div>
        )}
      </section>
    </main>
  );
}
