"""Réponses ajoutées pour couvrir chaque page : tableau de bord, ordres et règles, comparaison de deux actifs, presse, crédit,
stress test sur les vraies banques, leçon de formation, autre choix au jeu, et « explique cette page ».

Même contrat que `reponses.py` : chaque chiffre vient d'une fonction déjà utilisée par la page concernée, à la date du compte.
"""
from __future__ import annotations

import math

from sqlalchemy import select

from ..credit import zscore
from ..formation.contenu import LECONS
from ..jeu import service as jeu
from ..jeu.modeles import PartieJeu
from ..marche.stockage import DonneeIndisponible
from ..risque.suivi import resumer
from ..risque.synthese import niveau_risque
from ..routes_portefeuille import _analyser_bac, _courbe
from ..scenarios import service as actualites_service
from ..scenarios.modeles import ActualiteDb
from ..scenarios.sentiment import analyser as analyser_ton
from ..stress import credit as stress_credit
from ..stress import donnees_reelles, scenarios as stress_scenarios
from .comprendre import GLOSSAIRE, normaliser
from .reponses import NBSP, NIVEAUX, Situation, cours, jour, nombre, part, preuve, quantite, reponse, usd

LIMITE_BANQUES = ("Vraies banques saoudiennes (rapports Pilier 3, 31/12/2025). LGD et corrélation de Bâle : hypothèses. "
                  "Pas un test réglementaire, ni une prédiction de faillite.")


# ------------------------------------------------------------------ tableau de bord
def dashboard(s: Situation) -> dict:
    v = s.valo()
    debut, points = _courbe(s.ctx, s.bac, s.t, v)
    r = resumer(s.ctx, points, v, s.bac.salle.compte(s.bac.compte_id).executions, debut, s.t)
    capital, valeur = r["capital_initial"], r["valeur"]
    phrases = [f"Au {jour(s.t)}, votre portefeuille vaut {usd(valeur)}, soit {usd(r['gain'], 0, True)} depuis le départ "
               f"({part(r['rendement_total'], 2, True)})."]
    phrases.append(f"Sur la dernière journée : {usd(r['resultat_jour'], 0, True)}.")
    if v["positions"]:
        n = niveau_risque(_analyser_bac(s.ctx, s.bac, s.t, s.utilisateur, v, points))
        if n["score"] is not None:
            phrases.append(f"Votre risque est {NIVEAUX.get(n['niveau'], n['niveau'])}, à {nombre(n['score'])} sur 100.")
    refs = [x for x in r["references"] if x["depuis_debut"] is not None]
    if refs and r["a_commence"]:
        x = refs[0]
        e = abs(x["ecart_points"])
        phrases.append(f"Vous êtes {'devant' if x['ecart_points'] >= 0 else 'derrière'} le {x['nom']} de {nombre(e, 2)} point{'s' if e >= 2 else ''}.")
    return reponse(" ".join(phrases),
                   preuve("Valeur = capital de départ + gain depuis le départ",
                          [f"Capital de départ : {usd(capital, 2)}", f"Suivi depuis le {jour(debut)}", f"Positions : {len(v['positions'])}"],
                          [("Capital de départ", capital, usd(capital)), ("Gain depuis le départ", r["gain"], usd(r["gain"], 0, True))],
                          "La somme des deux barres donne la valeur actuelle. Le passé ne garantit rien."),
                   "/", "Ouvrir le dashboard")


# ------------------------------------------------------------------ ordres et règles (lecture seule)
LIBELLES_REGLES = {"stop_loss": "Stop-loss", "take_profit": "Prise de profit", "stop_suiveur": "Stop suiveur", "achat_complementaire": "Achat complémentaire"}


def ordres(s: Situation) -> dict:
    compte = s.bac.salle.compte(s.bac.compte_id)
    ouverts = [o for o in compte.ordres.values() if o.ouvert]
    actives = [r for r in compte.regles.values() if r.statut == "active"]
    # la dernière vente déclenchée par un stop ou une règle, pour « pourquoi mon stop a vendu plus bas ? »
    ventes = [e for e in compte.executions if e.sens == "vente" and e.instant <= s.t]
    auto = None
    for e in reversed(ventes):
        o = compte.ordres.get(e.ordre_id)
        if o is not None and (o.type == "stop" or (o.origine or "").startswith("regle:")):
            auto = (e, o)
            break
    if auto and _contient(s.q, r"stop|plus bas|declench|vendu|regle"):
        e, o = auto
        seuil = o.prix_stop
        if seuil is None and (o.origine or "").startswith("regle:"):
            r = compte.regles.get(int(o.origine.split(":")[1]))
            seuil = _seuil_regle(r, s) if r else None
        if seuil:
            ecart = e.prix - seuil
            texte = (f"Votre vente de {s.nom(e.symbole)} du {jour(e.instant)} visait {cours(seuil)} et a été exécutée à {cours(e.prix)}, "
                     f"soit {cours(abs(ecart))} {'plus bas' if ecart < 0 else 'plus haut'}. Un stop devient un ordre au marché une fois "
                     "le seuil franchi : après un saut de prix à l’ouverture, il vend au premier prix disponible.")
            return reponse(texte,
                           preuve("Prix obtenu = seuil + écart d’exécution",
                                  [f"Quantité vendue : {quantite(e.quantite)}", f"Frais : {usd(e.frais, 2)}"],
                                  [("Seuil", seuil, cours(seuil)), ("Écart d’exécution", ecart, nombre(ecart, 2, True))],
                                  "La somme des barres donne le prix obtenu. Un stop protège, il ne garantit pas son prix."),
                           "/portefeuille", "Voir l’historique")
    if not ouverts and not actives:
        return reponse("Vous n’avez aucun ordre en attente ni aucune règle active.",
                       preuve("Lecture des ordres et des règles du compte", [f"Exécutions passées : {len(ventes)} ventes"]),
                       "/marche", "Passer un ordre")
    donnees = [f"Ordre {o.sens} {o.type} : {quantite(o.reste)} {s.nom(o.symbole)}"
               + (f" à {cours(o.prix_limite)}" if o.prix_limite else "") + (f", seuil {cours(o.prix_stop)}" if o.prix_stop else "") for o in ouverts]
    donnees += [f"{LIBELLES_REGLES.get(r.type, r.type)} sur {s.nom(r.symbole)} : seuil {part(r.seuil, 0, True)}" for r in actives]
    texte = (f"Vous avez {len(ouverts)} ordre{'s' if len(ouverts) > 1 else ''} en attente et {len(actives)} règle{'s' if len(actives) > 1 else ''} "
             "active" + ("s" if len(actives) > 1 else "") + ". Ils sont vérifiés à chaque avance du temps, à l’ouverture du marché.")
    return reponse(texte, preuve("Lecture des ordres et des règles du compte", donnees, limite="Lecture seule : je ne modifie ni n’annule rien."),
                   "/portefeuille", "Gérer mes règles")


def _seuil_regle(r, s: Situation) -> float | None:
    p = next((p for p in s.valo()["positions"] if p["symbole"] == r.symbole), None)
    if r.type == "stop_suiveur" and r.plus_haut:
        return r.plus_haut * (1 - r.seuil)
    return p["prix_moyen"] * (1 + r.seuil) if p else None


def _contient(q: str, motif: str) -> bool:
    import re
    return re.search(motif, q) is not None


# ------------------------------------------------------------------ comparer deux actifs
def _profil(s: Situation, sym: str) -> dict | None:
    if not s.ctx.magasin.a_des_donnees(sym):
        return None
    df = s.ctx.magasin.barres_terminees(sym, s.t.date(), n=260)
    clo = df["close"].astype(float)
    if len(clo) < 25:
        return None
    a = s.ctx.univers[sym]
    n = min(len(clo) - 1, 249)
    rend = float(clo.iloc[-1] / clo.iloc[-1 - n] - 1)
    vol = float(clo.pct_change().iloc[-20:].std()) * math.sqrt(365 if a.calendrier == "continu" else 252)
    baisse = float((clo.iloc[-n - 1:] / clo.iloc[-n - 1:].cummax() - 1).min())
    return {"nom": a.nom, "rendement": rend, "seances": n, "vol": vol, "baisse": baisse, "dernier": float(clo.iloc[-1]), "jour": df.index[-1]}


def comparer(s: Situation) -> dict:
    a, b = s.lecture.symbole, s.lecture.symbole2
    pa, pb = _profil(s, a), _profil(s, b)
    if pa is None or pb is None:
        manque = s.nom(a) if pa is None else s.nom(b)
        return reponse(f"Je ne peux pas comparer : {manque} n’a pas assez de séances avant le {jour(s.t)}.",
                       preuve("Donnée absente, rien n’est inventé"), "/marche", "Ouvrir le marché")
    plus_volatil = pa if pa["vol"] >= pb["vol"] else pb
    texte = (f"Sur les {pa['seances']} dernières séances, {pa['nom']} a fait {part(pa['rendement'], 1, True)} et {pb['nom']} "
             f"{part(pb['rendement'], 1, True)}. Le plus agité ces 20 dernières séances est {plus_volatil['nom']} "
             f"({part(plus_volatil['vol'])} de volatilité annualisée). Pires baisses depuis un plus haut : {part(pa['baisse'], 1)} contre "
             f"{part(pb['baisse'], 1)}.")
    return reponse(texte,
                   preuve("Clôtures terminées : rendement, volatilité sur 20 séances, pire baisse",
                          [f"{p['nom']} : dernière clôture {cours(p['dernier'])} le {jour(p['jour'])}, volatilité {part(p['vol'])}" for p in (pa, pb)],
                          [(f"{pa['nom']} : rendement", pa["rendement"], part(pa["rendement"], 1, True)),
                           (f"{pb['nom']} : rendement", pb["rendement"], part(pb["rendement"], 1, True))],
                          "Comparer le passé ne dit pas lequel fera mieux ensuite."),
                   f"/actif/{a}", "Voir la fiche")


# ------------------------------------------------------------------ presse et ton des actualités
def actualites(s: Situation) -> dict:
    sym = s.lecture.symbole
    lignes = []
    for a in s.session.scalars(select(ActualiteDb).where(ActualiteDb.actif.is_(True), ActualiteDb.date <= s.t.date())
                               .order_by(ActualiteDb.date.desc(), ActualiteDb.id.desc())):
        if not actualites_service.visible(a, s.t):
            continue
        if sym and a.symboles and sym not in a.symboles:
            continue
        lignes.append((a, analyser_ton(f"{a.titre}. {a.texte}")))
    cible = f" sur {s.nom(sym)}" if sym else ""
    if not lignes:
        return reponse(f"Aucune actualité{cible} n’est parue avant le {jour(s.t)}. Je n’invente pas de ton.",
                       preuve("Actualités déjà parues à votre date", ["Aucune"]), "/actualites", "Ouvrir les actualités")
    comptes = {"positif": 0, "negatif": 0, "neutre": 0}
    for _, t in lignes:
        comptes[t.etiquette] = comptes.get(t.etiquette, 0) + 1
    recente, ton = lignes[0]
    fictive = recente.type_source != "historique"
    texte = (f"{len(lignes)} actualité{'s' if len(lignes) > 1 else ''}{cible} parue{'s' if len(lignes) > 1 else ''} avant le {jour(s.t)} : "
             f"{comptes['positif']} au ton positif, {comptes['negatif']} négatif, {comptes['neutre']} neutre. La plus récente, du "
             f"{jour(recente.date)} : « {recente.titre} » (ton {nombre(ton.score, 2, True)})." + (" Elle est étiquetée fictive." if fictive else ""))
    return reponse(texte,
                   preuve("Ton = (mots positifs − mots négatifs) ÷ (positifs + négatifs + 1)",
                          [f"Mots repérés dans la plus récente : {', '.join(ton.mots_positifs + ton.mots_negatifs) or 'aucun'}"],
                          [("Positives", comptes["positif"], str(comptes["positif"])), ("Négatives", comptes["negatif"], str(comptes["negatif"])),
                           ("Neutres", comptes["neutre"], str(comptes["neutre"]))],
                          "La somme des barres donne le nombre d’actualités. Lexique simple : il ne comprend ni l’ironie ni le contexte. "
                          "Les repères historiques ont été rédigés de mémoire, à vérifier."),
                   "/actualites", "Ouvrir les actualités")


# ------------------------------------------------------------------ crédit : score Z d'Altman, exemple fictif
def credit(s: Situation) -> dict:
    ex = zscore.EXEMPLES[0]
    r = zscore.calculer(ex["comptes"], "z")
    texte = (f"{GLOSSAIRE['z_score'][1]} Exemple avec « {ex['nom']} » : Z = {nombre(r['z'], 2)}, zone "
             f"{'saine' if r['zone'] == 'sain' else 'de détresse' if r['zone'] == 'detresse' else 'grise'}.")
    return reponse(texte,
                   preuve("Z = 1,2·X1 + 1,4·X2 + 3,3·X3 + 0,6·X4 + 1,0·X5",
                          [f"{c['ratio']} {c['libelle']} : {nombre(c['valeur'], 3)} × {nombre(c['coefficient'], 1)}" for c in r["contributions"]],
                          [(c["libelle"], c["contribution"], nombre(c["contribution"], 3)) for c in r["contributions"]],
                          "La somme des barres donne Z. Entreprise fictive ; repère statistique ancien, pas une probabilité de défaut."),
                   "/credit", "Ouvrir le crédit")


# ------------------------------------------------------------------ stress test sur les vraies banques
def stress_banques(s: Situation) -> dict:
    try:
        bs = donnees_reelles.charger()
    except (FileNotFoundError, donnees_reelles.ErreurDonneesBanques) as exc:
        return reponse(f"Les banques réelles ne se chargent pas : {exc}", preuve("Donnée absente, rien n’est inventé"), "/stress", "Ouvrir le stress test")
    p = stress_scenarios.parametres("recession", "extreme")
    comp = stress_credit.comparer_scenario(bs, p)
    res = comp["resultats"]
    classement = sorted(res, key=lambda r: r["hausse_vers_4_5"])
    cle = s.lecture.banque
    if cle:
        r = next((x for x in res if x["cle"] == cle), None)
        if r is None:
            return reponse("Cette banque n’est pas dans le panel.", preuve("Panel de 9 banques saoudiennes"), "/stress", "Ouvrir le stress test")
        rang = [x["cle"] for x in classement].index(cle) + 1
        b = next(x for x in bs if x.cle == cle)
        marge = r["capital_avant_md"] - 0.045 * r["actifs_ponderes_md"]
        texte = (f"{r['banque']} : CET1 de {part(r['cet1_avant'], 2)}, qui tombe à {part(r['cet1_apres'], 2)} en récession extrême "
                 f"(une année sur 1 000). Il faudrait {nombre(r['hausse_vers_4_5'] * 100, 1)} points de prêts en défaut en plus pour la "
                 f"faire passer sous 4,5 % : rang {rang} sur {len(res)}, 1 étant la plus fragile. Son capital au-dessus du minimum "
                 f"({nombre(marge, 2)} Md) est à rapporter à {nombre(r['prets_bruts_md'], 2)} Md de prêts.")
        return reponse(texte,
                       preuve("CET1 après = (capital − prêts × (PD stressée − PD de départ) × LGD) ÷ actifs pondérés",
                              [f"Capital CET1 : {nombre(r['capital_avant_md'], 2)} Md, actifs pondérés : {nombre(r['actifs_ponderes_md'], 2)} Md",
                               f"PD : {part(r['pd_avant'], 2)} → {part(r['pd_stressee'], 2)}, LGD {part(r['lgd'], 0)}",
                               f"Pire cas = ({nombre(r['capital_avant_md'], 2)} − 4,5 % × {nombre(r['actifs_ponderes_md'], 2)}) ÷ "
                               f"({nombre(r['prets_bruts_md'], 2)} × {part(r['lgd'], 0)})",
                               f"Source : rapport Pilier 3, p. {b.page_km1} et p. {b.page_cr1}"],
                              [("Capital de départ", r["capital_avant_md"], f"{nombre(r['capital_avant_md'], 2)}{NBSP}Md"),
                               ("Perte de crédit", -r["perte_md"], f"{nombre(-r['perte_md'], 2, True)}{NBSP}Md")],
                              "La somme des barres donne le capital restant. " + LIMITE_BANQUES),
                       "/stress", "Simuler cette banque")
    pire = classement[0]
    sous7 = sum(r["cet1_apres"] < 0.07 for r in res)
    g = comp["groupes"]
    texte = (f"La plus fragile est {pire['banque']} : il faudrait {nombre(pire['hausse_vers_4_5'] * 100, 1)} points de prêts en défaut en "
             f"plus pour la faire passer sous 4,5 % de CET1. La plus solide est {classement[-1]['banque']}, "
             f"{nombre(classement[-1]['hausse_vers_4_5'] * 100, 1)} points. En récession extrême, {sous7} banque{'s' if sous7 > 1 else ''} "
             f"sur {len(res)} {'passent' if sous7 > 1 else 'passe'} sous 7 %. Moyenne simple après choc : islamiques "
             f"{part(g['islamique']['cet1_apres'], 2)}, conventionnelles {part(g['conventionnelle']['cet1_apres'], 2)}.")
    return reponse(texte,
                   preuve("Pire cas = (capital − 4,5 % × actifs pondérés) ÷ (prêts × LGD), LGD 45 %",
                          [f"{r['banque']} : {part(r['cet1_avant'], 2)} → {part(r['cet1_apres'], 2)}" for r in classement],
                          [(r["banque"], r["hausse_vers_4_5"] * 100, f"{nombre(r['hausse_vers_4_5'] * 100, 1)}{NBSP}pts") for r in classement],
                          "Marge de chaque banque avant 4,5 %, en points de défauts. " + LIMITE_BANQUES),
                   "/stress", "Ouvrir le stress test")


# ------------------------------------------------------------------ formation : une leçon précise
def lecon(s: Situation) -> dict | None:
    """La leçon dont le titre ou le résumé partage le plus de mots avec la question ; None si rien ne correspond."""
    mots = {m for m in s.q.split() if len(m) >= 5}
    meilleure, score = None, 0
    for x in LECONS:
        texte = normaliser(f"{x['id']} {x['titre']} {x['resume']}")
        n = sum(m in texte for m in mots)
        if n > score:
            meilleure, score = x, n
    if meilleure is None or not _contient(s.q, r"lecon|explique|apprendre|cours"):
        return None
    sections = [sec["titre"] for sec in meilleure.get("sections", [])]
    texte = (f"La leçon « {meilleure['titre']} » ({meilleure['niveau']}, {meilleure['minutes']} minutes) : {meilleure['resume']} "
             f"Elle se termine par un quiz de {len(meilleure.get('questions', []))} questions.")
    return reponse(texte, preuve("Catalogue de la formation", [f"Partie : {t}" for t in sections], limite="Contenu pédagogique rédigé par l’équipe."),
                   "/formation", "Ouvrir la leçon")


# ------------------------------------------------------------------ jeu : et si j'avais choisi autrement ?
def autre_choix(s: Situation) -> dict | None:
    if not _contient(s.q, r"autre|autrement|si j'avais|aurait|montage|alternati"):
        return None
    p = s.session.scalars(
        select(PartieJeu).where(PartieJeu.utilisateur_id == s.utilisateur.id, PartieJeu.statut == jeu.TERMINEE, PartieJeu.note.is_not(None))
        .order_by(PartieJeu.maj_le.desc())).first()
    if p is None:
        return None
    v = jeu.vue(p)                  # la porte de sortie du jeu : une séance mystère non devinée reste masquée
    montage = v["generique"]["montage"]
    if not montage:
        return None
    meilleure = max(((m, a) for m in montage for a in m["autres"]), key=lambda x: x[1]["ecart"])
    m, a = meilleure
    texte = (f"Au {m['arret'] + 1}e arrêt, vous avez choisi « {m['nom']} ». Avec « {a['nom']} » et tout le reste identique, la partie "
             f"aurait fini à {usd(a['valeur'])}, soit {usd(a['ecart'], 0, True)} par rapport à votre fin. "
             "C’est le montage alternatif : on change une seule décision.")
    barres = [(f"Arrêt {x['arret'] + 1} : {y['nom']}", y["ecart"], usd(y["ecart"], 0, True)) for x in montage for y in x["autres"]]
    return reponse(texte, preuve("Rejouer la partie en changeant UNE décision", [f"Note de la partie : {p.note}/100"], barres,
                                 "Écart avec votre fin réelle. Savoir après coup ce qui aurait marché ne rend pas la décision meilleure."),
                   "/jeu", "Voir le montage")


# ------------------------------------------------------------------ « explique cette page »
PAGES = {
    "": ("Dashboard", "le résumé de votre portefeuille : valeur, résultat, niveau de risque et comparaison à l’indice",
         "Regardez d’abord la courbe de valeur contre l’indice, puis le niveau de risque."),
    "marche": ("Marché", "tous les actifs négociables, leur cours à votre date et le ticket pour passer un ordre",
               "Choisissez un actif, lisez sa fiche, puis décidez d’un ordre au marché ou limité."),
    "actif": ("Fiche actif", "le graphique d’un actif, ses indicateurs et votre position",
              "Regardez d’abord la tendance et la volatilité, puis votre poids dans cet actif."),
    "portefeuille": ("Portefeuille", "vos positions, leur résultat, les mesures de risque et vos règles automatiques",
                     "Regardez d’abord la position qui pèse le plus, puis le niveau de risque."),
    "strategies": ("Analyse", "des stratégies techniques rejouées sur l’historique, avec leurs indicateurs",
                   "Comparez une stratégie à « acheter et garder » avant de lui faire confiance."),
    "jeu": ("Jeu", "La Salle Obscure : vous écrivez un plan, puis un film rejoue une vraie crise séance par séance",
            "Écrivez votre plan avant le film : il compte pour un quart de la note."),
    "stress": ("Stress test", "le capital de 9 vraies banques saoudiennes face à une crise que vous choisissez",
               "Choisissez des banques, une crise et son intensité, puis lancez la simulation."),
    "formation": ("Formation", "des leçons courtes avec quiz, un défi et une ligue",
                  "Commencez par la leçon sur les ordres, puis celle sur le risque."),
    "actuariat": ("Assurance", "la tarification d’un contrat : fréquence, coût moyen, prime et provisions",
                  "Regardez comment chaque facteur multiplie la fréquence des sinistres."),
    "xai": ("Assistant XAI", "les réponses de l’assistant, avec la méthode, les données et la limite de chaque chiffre",
            "Ouvrez « Pourquoi cette réponse ? » sous chaque réponse."),
    "actualites": ("Actualités", "les nouvelles parues avant votre date, leur ton et ce que le marché a fait ensuite",
                   "Comparez le ton d’une nouvelle au mouvement du lendemain."),
    "credit": ("Crédit", "le score Z d’Altman sur des entreprises fictives et une probabilité de défaut de particuliers",
               "Regardez quelle part de Z vient de chaque ratio."),
    "ia": ("Modèles IA", "des modèles statistiques testés en marche avant, comparés à des règles naïves",
           "Vérifiez si le modèle bat la règle naïve avant de regarder sa prédiction."),
    "compte": ("Compte", "votre profil de risque, vos sessions et vos données",
               "Vérifiez que votre profil de risque correspond à ce que vous acceptez de perdre."),
    "admin": ("Administration", "les comptes, les crises injectées et les actualités",
              "Toute crise injectée touche tous les utilisateurs : elle est journalisée."),
}
ALIAS_PAGES = {"actions": "marche", "crypto": "marche", "matieres": "marche"}


def page(s: Situation) -> dict:
    cle = ALIAS_PAGES.get(s.lecture.page or "", s.lecture.page or "")
    if cle not in PAGES:
        cle = ""
    nom, montre, conseil = PAGES[cle]
    v = s.valo()
    lignes = sorted(v["positions"], key=lambda p: -p["valeur"])
    chiffres = [f"Au {jour(s.t)}, votre portefeuille vaut {usd(v['equity'])}"
                + (f", dont {usd(v['cash_disponible'])} disponibles." if lignes else ", entièrement en liquidités.")]
    if cle == "portefeuille" and lignes:
        chiffres.append(f"Votre plus grosse position est {s.nom(lignes[0]['symbole'])}, {part(lignes[0]['poids'])} du portefeuille.")
    elif cle == "marche":
        n = sum(1 for a in s.ctx.univers if a.tradable)
        chiffres.append(f"{n} actifs sont négociables ; vous en détenez {len(lignes)}.")
    elif cle == "actif" and s.lecture.symbole and s.lecture.symbole in s.ctx.univers:
        try:
            chiffres.append(f"{s.nom(s.lecture.symbole)} cote {cours(s.ctx.moteur.cotation(s.lecture.symbole, s.t).prix)}.")
        except DonneeIndisponible:
            pass
    elif cle == "jeu":
        n = s.session.scalars(select(PartieJeu).where(PartieJeu.utilisateur_id == s.utilisateur.id)).all()
        notees = [p.note for p in n if p.note is not None]
        chiffres.append(f"Vous avez {len(n)} partie{'s' if len(n) > 1 else ''}" + (f", dernière note {notees[-1]}/100." if notees else "."))
    elif cle == "stress":
        try:
            bs = donnees_reelles.charger()
            res = stress_credit.comparer_scenario(bs, stress_scenarios.parametres("recession", "severe"))["resultats"]
            pire = min(res, key=lambda r: r["cet1_apres"])
            chiffres.append(f"En récession sévère, la plus touchée est {pire['banque']}, à {part(pire['cet1_apres'], 2)} de CET1.")
        except (FileNotFoundError, donnees_reelles.ErreurDonneesBanques):
            pass
    elif cle == "formation":
        chiffres.append(f"{len(LECONS)} leçons sont disponibles.")
    elif cle == "xai":
        chiffres.append(f"Je connais {len(GLOSSAIRE)} termes du glossaire.")
    elif cle == "compte":
        pr = s.utilisateur.profil_risque or {}
        chiffres.append(f"Votre profil de risque : {pr.get('profil') or pr.get('nom') or ('renseigné' if pr else 'non renseigné')}.")
    texte = f"Cette page, {nom}, montre {montre}. {' '.join(chiffres)} {conseil}"
    return reponse(texte, preuve("Description de la page et chiffres de votre compte", [f"Page : {nom}", f"Date du compte : {jour(s.t)}"],
                                 limite="Je décris la page ; je ne choisis rien à votre place."))


# ------------------------------------------------------------------ deux questions de suite, selon l'intention
SUITES = {
    "risque": ["Et si tout baisse de 10 % ?", "Quelle position pèse le plus ?"],
    "resultat": ["Pourquoi ce niveau de risque ?", "Suis-je meilleur que l’indice ?"],
    "portefeuille": ["Pourquoi ai-je ce résultat ?", "Pourquoi ce niveau de risque ?"],
    "indice": ["Pourquoi ai-je ce résultat ?", "C’est quoi le rendement total ?"],
    "dashboard": ["Pourquoi ce niveau de risque ?", "Suis-je meilleur que l’indice ?"],
    "actif": ["Et si cet actif baisse de 10 % ?", "Que dit la presse sur cet actif ?"],
    "comparer": ["C’est quoi la volatilité ?", "Et si tout baisse de 10 % ?"],
    "choc": ["Pourquoi ce niveau de risque ?", "C’est quoi la VaR ?"],
    "stress": ["Pourquoi AlJazira est la plus fragile ?", "C’est quoi le CET1 ?"],
    "jeu": ["Qu’aurait donné un autre choix au jeu ?", "C’est quoi le VIX ?"],
    "assurance": ["C’est quoi une franchise ?", "C’est quoi la prime pure ?"],
    "ordres": ["C’est quoi un stop suiveur ?", "C’est quoi un gap ?"],
    "actualites": ["C’est quoi le ton d’une actualité ?", "Pourquoi ai-je ce résultat ?"],
    "credit": ["C’est quoi la PD ?", "Quelle banque est la plus fragile ?"],
    "definition": ["Explique cette page", "Pourquoi ce niveau de risque ?"],
    "formation": ["Explique la leçon sur le risque", "C’est quoi le ratio de Sharpe ?"],
    "page": ["Pourquoi ai-je ce résultat ?", "Pourquoi ce niveau de risque ?"],
    "prediction": ["Et si tout baisse de 10 % ?", "Pourquoi ce niveau de risque ?"],
    "conseil": ["Pourquoi ce niveau de risque ?", "Et si tout baisse de 10 % ?"],
    "temps": ["Pourquoi je ne peux pas reculer ?", "D’où viennent les données ?"],
    "sources": ["Quelle date on est ?", "Que dit la presse sur Apple ?"],
    "modele": ["C’est quoi la régression logistique ?", "Parle-moi d’Apple"],
}
SUITE_DEFAUT = ["Explique cette page", "Pourquoi ai-je ce résultat ?"]


def suites(lecture) -> list[str]:
    """Deux questions de suite. Pour une banque précise, on ne repropose pas la question qu'on vient de poser."""
    if lecture.intention == "stress" and lecture.banque:
        return ["Quelle banque est la plus fragile ?", "C’est quoi le pire cas ?"]
    return SUITES.get(lecture.intention, SUITE_DEFAUT)

REPONSES = {"dashboard": dashboard, "ordres": ordres, "comparer": comparer, "actualites": actualites, "credit": credit,
            "stress": stress_banques, "page": page}

from . import reponses as _reponses  # noqa: E402

_reponses.REPONSES.update(REPONSES)
