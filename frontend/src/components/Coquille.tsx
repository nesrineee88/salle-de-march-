"use client";

import { useEffect, useState } from "react";
import Auth from "./Auth";
import BarreTemps from "./BarreTemps";
import { FournisseurMarche, useMarche } from "./Contexte";
import Entete from "./Entete";
import { deconnexion, enregistrerSurDeconnexion, restaurerSession } from "@/lib/api";
import { dateLongue } from "@/lib/format";
import type { Utilisateur } from "@/lib/types";

function Bandeaux() {
  const { inst, erreurReseau } = useMarche();
  return (
    <div className="bandeaux">
      {erreurReseau && <p className="bandeau erreur" role="alert">{erreurReseau}</p>}
      {inst?.synthetiques && (
        <p className="bandeau avertissement" role="note">
          Données de démonstration générées au hasard : ce ne sont pas de vrais prix. Pour les vraies données, lancez <code>python -m pipeline tout</code>.
        </p>
      )}
      {inst?.direct && (
        <p className="bandeau avertissement" role="status">
          {inst.direct_flux?.demo
            ? "Mode Direct (bêta), FLUX DE DÉMONSTRATION : les prix sont inventés, ce ne sont pas de vrais cours."
            : "Mode Direct (bêta) : prix Yahoo Finance, souvent différés d'environ 15 minutes, à l'heure réelle."}
          {inst.direct_flux?.age_secondes != null && ` Dernière mise à jour il y a ${inst.direct_flux.age_secondes} s.`}
          {inst.direct_flux?.erreur && ` Flux momentanément indisponible, derniers prix conservés (${inst.direct_flux.erreur}).`}
        </p>
      )}
      {inst?.termine && (
        <p className="bandeau info" role="status">
          La période rejouée est terminée ({dateLongue(inst.instant)}). Consultez votre bilan dans « Portefeuille », ou revenez en arrière avec la frise du temps.
        </p>
      )}
    </div>
  );
}

function Interieur({ children }: { children: React.ReactNode }) {
  const { inst } = useMarche();
  const sansDonnees = inst !== null && inst.cotations.length === 0;
  return (
    <div className="coquille">
      <Entete />
      <BarreTemps />
      <Bandeaux />
      <div className="contenu">
        {sansDonnees ? (
          <main className="espace-vide">
            <h1>Aucune donnée de marché</h1>
            <p>Le serveur n&apos;a pas encore de prix à rejouer. Dans le dossier <code>backend</code>, lancez :</p>
            <pre>python -m pipeline tout</pre>
            <p>Cette commande télécharge les prix, les nettoie et prépare le simulateur. Rechargez ensuite cette page.</p>
          </main>
        ) : children}
      </div>
    </div>
  );
}

export default function Coquille({ children }: { children: React.ReactNode }) {
  const [utilisateur, setUtilisateur] = useState<Utilisateur | null>(null);
  const [pret, setPret] = useState(false);

  useEffect(() => {
    enregistrerSurDeconnexion(() => setUtilisateur(null));
    restaurerSession().then((u) => { setUtilisateur(u); setPret(true); });
  }, []);

  if (!pret) return <p className="chargement" role="status">Chargement…</p>;
  if (!utilisateur) return <Auth onConnecte={setUtilisateur} />;
  return (
    <FournisseurMarche
      utilisateur={utilisateur}
      majUtilisateur={setUtilisateur}
      deconnecter={async () => { await deconnexion(); setUtilisateur(null); }}
    >
      <Interieur>{children}</Interieur>
    </FournisseurMarche>
  );
}
