"""Répondre : chaque chiffre vient d'un calcul déjà utilisé par le projet, à la date du portefeuille, jamais après.

Une réponse = un texte + une preuve (méthode, données, barres, limite) + un lien vers la page concernée.
Rien n'est écrit : l'assistant ne passe pas d'ordre, ne change pas de date, n'entraîne aucun modèle.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..actuariat import routes as actuariat
from ..actuariat import tarification
from ..analyse.indicateurs import rsi
from ..contexte import Bac, Contexte
from ..formation.contenu import LECONS
from ..jeu import service as jeu
from ..jeu.modeles import PartieJeu
from ..marche.stockage import DonneeIndisponible
from ..risque.suivi import resumer
from ..risque.synthese import niveau_risque
from ..routes_portefeuille import _analyser_bac, _courbe
from ..trading.carnet import FRAIS_BPS
from ..utilisateurs.modeles import Utilisateur
from .comprendre import GLOSSAIRE, Lecture

FINE, NBSP, MOINS = " ", " ", "−"
MOIS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")
FAMILLES = {"volatilite": "Volatilité", "var": "VaR 95 %", "cvar": "CVaR 95 %", "drawdown": "Pire baisse", "concentration": "Concentration"}
NIVEAUX = {"faible": "faible", "modere": "modéré", "eleve": "élevé"}
CLASSES = {"action": "les actions", "crypto": "les cryptomonnaies", "matiere": "les matières premières"}
SEANCES_RECENTES = 20


def nombre(x: float, decimales: int = 0, signe: bool = False) -> str:
    v = round(x, decimales)
    corps = f"{abs(v):,.{decimales}f}".replace(",", "#").replace(".", ",").replace("#", FINE)
    return (MOINS if v < 0 else "+" if signe and v > 0 else "") + corps


def usd(x: float, decimales: int = 0, signe: bool = False) -> str:
    return f"{nombre(x, decimales, signe)}{NBSP}USD"


def part(x: float, decimales: int = 1, signe: bool = False) -> str:
    return f"{nombre(x * 100, decimales, signe)}{NBSP}%"


def cours(x: float) -> str:
    return usd(x, 2 if abs(x) >= 1 else 4)


def quantite(x: float) -> str:
    return nombre(x, 0 if abs(x - round(x)) < 1e-9 else 4)


def jour(t) -> str:
    return f"{t.day}{NBSP}{MOIS[t.month - 1]}{NBSP}{t.year}"


def preuve(methode: str, donnees=(), barres=(), limite: str = "Le passé ne garantit rien pour la suite.") -> dict:
    return {"methode": methode, "donnees": list(donnees), "limite": limite,
            "barres": [{"nom": n, "valeur": float(v), "affiche": a} for n, v, a in barres]}


def reponse(texte: str, p: dict, href: str | None = None, libelle: str = "") -> dict:
    texte = re.sub(r" ([:?!;%»])", NBSP + r"\1", texte).replace("« ", "«" + NBSP)      # la ponctuation ne passe pas à la ligne
    return {"texte": texte, "preuve": p, "lien": {"href": href, "libelle": libelle} if href else None}


@dataclass
class Situation:
    ctx: Contexte
    bac: Bac
    t: datetime                     # date du portefeuille : en Direct elle reste figée
    utilisateur: Utilisateur
    session: Session
    lecture: Lecture
    q: str = ""                     # question normalisée, pour les détails (leçon citée, « autre choix »)

    def nom(self, symbole: str) -> str:
        return self.ctx.univers[symbole].nom if symbole in self.ctx.univers else symbole

    def valo(self) -> dict:
        return self.bac.salle.valorisation(self.bac.compte_id, self.t)


def prediction(s: Situation) -> dict:
    return reponse(
        f"Je ne peux pas le savoir : je ne connais rien après le {jour(s.t)}, votre date simulée. Je peux en revanche chiffrer ce que "
        "vous perdriez si cela baissait. Demandez par exemple « et si tout baisse de 10 % ? ».",
        preuve("Refus volontaire de prédire", [f"Dernier jour connu : {jour(s.t)}"], limite="Aucune promesse de résultat financier."),
        "/portefeuille", "Voir mon risque")


def conseil(s: Situation) -> dict:
    return reponse(
        "Je ne choisis pas à votre place. Je peux expliquer un actif, chiffrer un choc sur votre portefeuille et montrer ce qui pèse "
        "dans votre risque. La décision reste la vôtre.",
        preuve("Garde-fou : aucun conseil personnalisé", limite="Plateforme pédagogique, argent fictif."),
        "/strategies", "Comparer des stratégies")


LIBELLES_PAGES = {"/": "le dashboard", "/marche": "le marché", "/portefeuille": "le portefeuille", "/strategies": "l’analyse",
                  "/jeu": "le jeu", "/stress": "le stress test", "/actuariat": "l’assurance", "/credit": "le crédit",
                  "/actualites": "les actualités", "/ia": "les modèles IA", "/xai": "l’assistant", "/formation": "la formation"}


def definition(s: Situation) -> dict:
    _, texte, href = GLOSSAIRE[s.lecture.terme]
    return reponse(texte,
                   preuve("Définition du glossaire", ["Rédigé par l’équipe, à vérifier", f"À voir dans {LIBELLES_PAGES.get(href, 'l’application')}"],
                          limite="Définition simplifiée, rédigée de mémoire : à vérifier pour un usage académique."),
                   href, f"Voir dans {LIBELLES_PAGES.get(href, 'l’application')}")


def identite(s: Situation) -> dict:
    return reponse(
        "Je suis l’assistant XAI de Séance. Je ne suis pas un modèle de langage : je reconnais votre question avec des règles, "
        "puis je lance les vrais calculs du projet et je montre la méthode, les données et la limite.",
        preuve("Règles explicables, calculées sur le serveur", ["Aucun appel internet", "Aucun modèle de langage", "Lecture seule : aucun ordre passé"],
               limite="Une question formulée autrement peut ne pas être reconnue."),
        "/xai", "Ouvrir l’assistant")


def accueil(s: Situation) -> dict:
    return reponse(
        "Bonjour. Je réponds sur votre résultat, votre risque, les indices, chaque actif, le jeu, le stress test, l’assurance et la "
        "formation. Essayez « pourquoi ce niveau de risque ? » ou « et si les actions baissent de 10 % ? ».",
        preuve("Périmètre de l’assistant", ["Portefeuille et risque", "Marché et indices", "La Salle Obscure", "Stress test", "Assurance", "Glossaire"],
               limite="Hors de ce périmètre, je le dis au lieu d’inventer."))


def inconnu(s: Situation) -> dict:
    return reponse(
        "Je n’ai pas compris cette question, et je préfère le dire plutôt qu’inventer. Essayez votre risque, votre résultat, un actif "
        "par son nom, une banque ou une définition.",
        preuve("Aucune intention reconnue", ["Aucune donnée inventée"], limite="L’assistant reconnaît un périmètre fixé, pas toute la langue."))


def ordre(s: Situation) -> dict:
    return reponse(
        "Dans Marché, choisissez l’actif, puis Acheter ou Vendre, le type d’ordre et la quantité. Un ordre au marché part tout de "
        "suite si le marché est ouvert, un ordre limite attend votre prix.",
        preuve("Règles du simulateur", [f"Frais actions : {nombre(FRAIS_BPS['action'], 1)} points de base",
                                        f"Frais cryptomonnaies : {nombre(FRAIS_BPS['crypto'], 1)} points de base"],
               limite="L’écart achat-vente et l’impact du volume s’ajoutent aux frais."),
        "/marche", "Passer un ordre")


def temps(s: Situation) -> dict:
    fenetre = s.ctx.univers
    return reponse(
        f"Votre portefeuille est au {jour(s.t)}. Cliquez la date en haut pour avancer. Revenir en arrière recommence le portefeuille, "
        "sinon vous joueriez en connaissant la suite.",
        preuve("Horloge personnelle du rejeu", [f"Période rejouée : du {jour(fenetre.debut)} au {jour(fenetre.fin)}"],
               limite="En Direct, le portefeuille reste figé à sa date."))


def sources(s: Situation) -> dict:
    return reponse(
        "Les cours du rejeu sont de vrais cours journaliers, figés sur le serveur. Entre l’ouverture et la clôture, le chemin est "
        "simulé, comme le carnet d’ordres. Le Direct lit Yahoo Finance, souvent en différé, et reste en lecture seule.",
        preuve("Sources déclarées du projet",
               [f"Rejeu : Yahoo Finance, du {jour(s.ctx.univers.debut)} au {jour(s.ctx.univers.fin)}", "Jeu : fichiers de cours figés",
                "Banques du stress test : 9 vraies banques saoudiennes, rapports Pilier 3 au 31/12/2025", "Crises injectées par l’administrateur : scénarios fictifs"],
               limite="Yahoo Finance n’est pas une source officielle de bourse."),
        "/marche", "Ouvrir le marché")


def formation(s: Situation) -> dict:
    from .couverture import lecon
    precise = lecon(s)
    if precise:
        return precise
    return reponse(
        f"La formation compte {len(LECONS)} leçons avec quiz. Pour débuter : « {LECONS[0]['titre']} », puis la leçon sur le risque.",
        preuve("Catalogue de la formation", [f"{x['titre']} ({x['niveau']})" for x in LECONS], limite="Contenu pédagogique."),
        "/formation", "Commencer")


def analyses_absentes(s: Situation) -> dict:
    return reponse(
        "Je n’ai pas de données comptables ni de sentiment fiables à expliquer dans le projet actuel, donc je n’invente pas de note. "
        "Pour un actif, je peux donner sa tendance, son RSI, sa volatilité et votre position.",
        preuve("Donnée absente", ["Fondamentale : pas de comptes d’entreprises chargés", "Ton des actualités : demandez « que dit la presse sur Tesla ? »"],
               limite="Prévu avec le module Analyse."),
        "/strategies", "Ouvrir l’analyse")


def portefeuille(s: Situation) -> dict:
    v = s.valo()
    lignes = sorted(v["positions"], key=lambda p: -p["valeur"])
    if not lignes:
        return reponse(f"Votre portefeuille vaut {usd(v['equity'])}, entièrement en liquidités. Vous n’avez aucune position.",
                       preuve("Liquidités + quantités × derniers cours", [f"Disponible : {usd(v['cash_disponible'])}"]),
                       "/marche", "Choisir un actif")
    barres = [(s.nom(p["symbole"]), p["valeur"], usd(p["valeur"])) for p in lignes] + [("Liquidités", v["cash"], usd(v["cash"]))]
    return reponse(
        f"Votre portefeuille vaut {usd(v['equity'])} : {usd(v['valeur_positions'])} investis dans {len(lignes)} "
        f"position{'s' if len(lignes) > 1 else ''} et {usd(v['cash'])} en liquidités, dont {usd(v['cash_disponible'])} disponibles.",
        preuve("Liquidités + quantités × derniers cours",
               [f"{p['symbole']} : {quantite(p['quantite'])} × {cours(p['prix_marche'])}" for p in lignes], barres,
               "Derniers cours connus, sans le coût d’une revente."),
        "/portefeuille", "Voir le portefeuille")


def resultat(s: Situation) -> dict:
    v = s.valo()
    gain = v["pnl_total"]
    parts = [(s.nom(p["symbole"]), p["pnl_latent"]) for p in v["positions"]]
    parts += [("Ventes réalisées", v["pnl_realise"]), ("Frais", -v["frais_cumules"])]
    reste = gain - sum(x for _, x in parts)
    if abs(reste) >= 0.01:
        parts.append(("Autres écarts", reste))
    parts = sorted([p for p in parts if abs(p[1]) >= 0.005], key=lambda p: -abs(p[1]))
    if not parts:
        return reponse("Votre résultat est nul : vous n’avez encore rien acheté ni vendu.",
                       preuve("Valeur actuelle − capital de départ", [f"Capital : {usd(v['capital_initial'])}"]), "/marche", "Passer un ordre")
    texte = (f"Vous {'gagnez' if gain >= 0 else 'perdez'} {usd(abs(gain))} depuis le départ, soit "
             f"{part(gain / v['capital_initial'], 2, True)}. Ce qui pèse le plus : {parts[0][0]}, {usd(parts[0][1], 0, True)}.")
    return reponse(texte,
                   preuve("Latent par position + réalisé − frais",
                          [f"Valeur : {usd(v['equity'], 2)}", f"Capital de départ : {usd(v['capital_initial'], 2)}"],
                          [(n, x, usd(x, 0, True)) for n, x in parts], "La somme des barres égale le résultat, aux arrondis d’affichage près."),
                   "/portefeuille", "Voir le portefeuille")


def risque(s: Situation) -> dict:
    v = s.valo()
    a = _analyser_bac(s.ctx, s.bac, s.t, s.utilisateur, v, _courbe(s.ctx, s.bac, s.t, v)[1])
    r = niveau_risque(a)
    if r["niveau"] == "aucun":
        return reponse("Vous n’avez aucune position : votre risque de marché est nul pour l’instant.",
                       preuve("Aucune position", ["100 % de liquidités"]), "/marche", "Choisir un actif")
    if r["niveau"] == "incomplet":
        c = next(f for f in r["familles"] if f["cle"] == "concentration")
        return reponse(
            f"Je ne peux pas encore noter votre risque : il faut plus de séances communes à vos positions. Votre concentration est "
            f"connue : {c['libelle']} pèse {part(c['valeur'])}.",
            preuve("Niveau incomplet, rien n’est inventé", [f"Séances disponibles : {r['jours']}"]), "/portefeuille", "Voir le portefeuille")
    familles = sorted(r["familles"], key=lambda f: -f["points"])
    p = r["plancher"]
    suite = (f"Le plancher de sécurité relève le niveau, car « {FAMILLES[p['cle']]} » est trop haut." if p["releve"]
             else "La moyenne pondérée suffit, le plancher ne joue pas.")
    texte = (f"Votre risque est {NIVEAUX[r['niveau']]}, à {nombre(r['score'])} points sur 100. Ce qui pèse le plus : "
             f"{FAMILLES[familles[0]['cle']]}, {nombre(familles[0]['points'], 1)} points. {suite}")
    donnees = [f"{FAMILLES[f['cle']]} : {part(f['valeur'])}, note {nombre(f['note'])} × poids {part(f['poids'], 0)}" for f in familles]
    return reponse(texte,
                   preuve("Σ poids × note, puis plancher de sécurité", donnees,
                          [(FAMILLES[f["cle"]], f["points"], f"{nombre(f['points'], 1)}{NBSP}pts") for f in familles],
                          "Seuils pédagogiques, sans valeur réglementaire. Mesuré sur le passé."),
                   "/portefeuille", "Voir le détail")


def indice(s: Situation) -> dict:
    v = s.valo()
    debut, points = _courbe(s.ctx, s.bac, s.t, v)
    r = resumer(s.ctx, points, v, s.bac.salle.compte(s.bac.compte_id).executions, debut, s.t)
    refs = [x for x in r["references"] if x["depuis_debut"] is not None]
    if not refs:
        return reponse("Aucun indice n’a de cours à votre date.", preuve("Référence absente"))
    if not r["a_commence"]:
        return reponse("La comparaison commence à votre première transaction. Achetez un actif, puis je compare aux mêmes dates.",
                       preuve("Même début pour vous et pour l’indice", [f"{x['nom']} : {nombre(x['niveau'], 0)}" for x in refs]),
                       "/marche", "Choisir un actif")
    x = refs[0]
    ecart = x["ecart_points"]
    texte = (f"Depuis le {jour(debut)}, votre rendement total est de {part(r['rendement_total'], 2, True)} et celui du {x['nom']} de "
             f"{part(x['depuis_debut'], 2, True)}. Vous êtes {'devant' if ecart >= 0 else 'derrière'}, de {nombre(abs(ecart), 2)} point{'s' if abs(ecart) >= 2 else ''}.")
    barres = [("Vous", r["rendement_total"], part(r["rendement_total"], 2, True))]
    barres += [(y["nom"], y["depuis_debut"], part(y["depuis_debut"], 2, True)) for y in refs]
    return reponse(texte,
                   preuve("Valeur actuelle ÷ valeur au début − 1, mêmes dates",
                          [f"Début commun : {jour(debut)}", "S&P 500 : dividendes inclus" if x.get("dividendes") else "Indice hors dividendes"],
                          barres, "Battre un indice sur une courte période ne prouve pas un talent."),
                   "/", "Voir le dashboard")


def actif(s: Situation) -> dict:
    sym = s.lecture.symbole
    a = s.ctx.univers[sym]
    try:
        if not s.ctx.magasin.a_des_donnees(sym):
            raise DonneeIndisponible(sym)
        c = s.ctx.moteur.cotation(sym, s.t)
    except DonneeIndisponible:
        return reponse(f"{a.nom} n’a pas de cours au {jour(s.t)}.", preuve("Aucune donnée à cette date"), "/marche", "Ouvrir le marché")
    df = s.ctx.magasin.barres_terminees(sym, s.t.date(), n=250)
    clo = df["close"].astype(float)
    phrases = [f"{a.nom} cote {cours(c.prix)}"
               + (f", {part((c.prix - c.reference_variation) / abs(c.reference_variation), 2, True)} sur la séance." if c.reference_variation else ".")]
    donnees = [f"Clôtures connues utilisées : {len(clo)}"]
    if len(df):
        donnees.append(f"Dernière clôture : {jour(df.index[-1])}")
    barres = []
    if len(clo) > 14:
        r = float(rsi(clo)[-1])
        if math.isfinite(r):
            zone = "zone de surachat" if r > 70 else "zone de survente" if r < 30 else "zone neutre"
            phrases.append(f"Son RSI vaut {nombre(r)}, en {zone}.")
            donnees.append(f"RSI sur 14 séances : {nombre(r, 1)}")
    if len(clo) >= 50:
        m = float(clo.iloc[-50:].mean())
        phrases.append(f"Il est {'au-dessus' if c.prix >= m else 'en dessous'} de sa moyenne de 50 séances.")
        donnees.append(f"Moyenne 50 séances : {cours(m)}")
    if len(clo) > SEANCES_RECENTES:
        rets = clo.pct_change().iloc[-SEANCES_RECENTES:]
        vol = float(rets.std()) * math.sqrt(365 if a.calendrier == "continu" else 252)
        donnees.append(f"Volatilité annualisée sur 20 séances : {part(vol)}")
        for n in (5, 20, 60, 249):
            if len(clo) > n and clo.iloc[-1 - n] > 0:
                x = float(clo.iloc[-1] / clo.iloc[-1 - n] - 1)
                barres.append((f"{n} séances" if n < 249 else "1 an de séances", x, part(x, 1, True)))
    v = s.valo()
    p = next((p for p in v["positions"] if p["symbole"] == sym), None)
    phrases.append(f"Vous en détenez {quantite(p['quantite'])}, soit {part(p['poids'])} du portefeuille, pour {usd(p['pnl_latent'], 0, True)}."
                   if p else "Vous n’en détenez pas.")
    return reponse(" ".join(phrases),
                   preuve("Lecture des séances terminées, puis du cours de l’instant", donnees, barres, "Un indicateur décrit le passé, il n’annonce pas la suite."),
                   f"/actif/{sym}", "Voir la fiche")


def choc(s: Situation) -> dict:
    lu = s.lecture
    v = s.valo()
    touchees = [p for p in v["positions"]
                if (lu.symbole is None or p["symbole"] == lu.symbole)
                and (lu.classe is None or s.ctx.univers[p["symbole"]].classe == lu.classe)]
    cible = s.nom(lu.symbole) if lu.symbole else CLASSES.get(lu.classe, "toutes vos positions")
    if not touchees:
        return reponse(f"Un choc de {part(lu.choc, 1, True)} sur {cible} ne vous touche pas directement : vous n’en détenez pas.",
                       preuve("Valeur détenue × choc", limite="Les effets indirects sur vos autres positions ne sont pas calculés."),
                       "/portefeuille", "Voir le portefeuille")
    effets = sorted(((s.nom(p["symbole"]), p["valeur"] * lu.choc) for p in touchees), key=lambda e: -abs(e[1]))
    total = sum(x for _, x in effets)
    texte = (f"Avec {part(lu.choc, 1, True)} sur {cible}, vous {'gagneriez' if total >= 0 else 'perdriez'} {usd(abs(total))}, soit "
             f"{part(total / v['equity'], 2, True)} du portefeuille. Il vaudrait {usd(v['equity'] + total)}.")
    return reponse(texte,
                   preuve("Valeur détenue × choc, position par position", [f"Valeur actuelle : {usd(v['equity'])}"],
                          [(n, x, usd(x, 0, True)) for n, x in effets],
                          "Hypothèse, pas prévision. Les liquidités ne bougent pas et les stops ne sont pas simulés."),
                   "/portefeuille", "Voir le portefeuille")


def assurance(s: Situation) -> dict:
    if re.search(r"proteg|protection|couvrir mon|mon portefeuille", s.q):
        v = s.valo()
        return reponse(
            f"Votre portefeuille vaut {usd(v['equity'])} au {jour(s.t)}. Le chiffrage d’une protection de portefeuille (option de vente) "
            "n’est pas encore dans cette version : je ne l’invente pas. Je peux expliquer un put, ou la tarification de la page Assurance.",
            preuve("Module de protection absent de cette version", [f"Valeur à protéger : {usd(v['equity'])}"],
                   limite="Le module de protection du portefeuille doit être fusionné par l’autre poste."),
            "/actuariat", "Ouvrir l’assurance")
    m = tarification.charger(actuariat.dossier_modeles())
    if m is None:
        return reponse("Le modèle de tarification n’est pas encore préparé. Ouvrez la page Assurance une fois, puis redemandez-moi.",
                       preuve("Modèle absent, rien n’est inventé"), "/actuariat", "Ouvrir l’assurance")
    p = m.prime({})
    invente = m.source == "synthetique"
    texte = (f"Pour le profil type de la page Assurance (assurance auto), la prime annuelle est de {nombre(p['prime_commerciale'], 2)} : "
             f"{nombre(p['frequence_annuelle'], 4)} sinistre par an × {nombre(p['cout_moyen'], 2)} de coût moyen, plus marge et frais. "
             f"La probabilité d’au moins un sinistre est de {part(p['probabilite_sinistre'])}.")
    facteurs = [f"{f.get('libelle') or f.get('variable')} : × {nombre(f['facteur'], 3)} sur la fréquence" for f in p["facteurs_frequence"][:4]]
    return reponse(texte,
                   preuve("Prime pure = fréquence × coût moyen, puis marge et frais", facteurs,
                          [("Prime pure", p["prime_pure"], nombre(p["prime_pure"], 2)), ("Marge", p["marge_securite"], nombre(p["marge_securite"], 2)),
                           ("Frais", p["frais"], nombre(p["frais"], 2))],
                          "Contrats et sinistres INVENTÉS : montants non réalistes, sans lien avec votre portefeuille." if invente
                          else "Jeu public français d’assurance auto, sans lien avec votre portefeuille."),
                   "/actuariat", "Ouvrir l’assurance")


def note_du_jeu(s: Situation) -> dict:
    from .couverture import autre_choix
    alternative = autre_choix(s)
    if alternative:
        return alternative
    p = s.session.scalars(
        select(PartieJeu).where(PartieJeu.utilisateur_id == s.utilisateur.id, PartieJeu.statut == jeu.TERMINEE, PartieJeu.note.is_not(None))
        .order_by(PartieJeu.maj_le.desc())).first()
    regle = ["40 % résultat contre le double immobile", "35 % protection du capital", "25 % respect de votre plan",
             "Plan respecté à moins de 50 % : note plafonnée à 55"]
    if p is None:
        return reponse(
            "Dans La Salle Obscure, vous écrivez votre plan, le film projette une vraie crise et s’arrête trois fois. La note pèse le "
            "résultat, la protection et le respect de votre propre plan.",
            preuve("Règle de notation du jeu", regle, [("Résultat", 40, "40 %"), ("Protection", 35, "35 %"), ("Plan", 25, "25 %")],
                   "Vous n’avez pas encore de partie notée."),
            "/jeu", "Entrer dans la salle")
    v = jeu.vue(p)                  # la porte de sortie du jeu : une séance mystère non devinée reste masquée
    g = v["generique"]
    w = g["poids"]
    apports = [("Résultat", g["resultat"] * w["resultat"]), ("Protection", g["protection"] * w["protection"]),
               ("Respect du plan", g["plan"]["note"] * w["plan"])]
    texte = (f"Votre dernière note est {g['note']}/100 sur « {v['titre']} ». Le résultat apporte {nombre(apports[0][1], 1)} points, "
             f"la protection {nombre(apports[1][1], 1)}, le respect du plan {nombre(apports[2][1], 1)}."
             + (f" Elle est plafonnée à {g['plafond']}, car le plan n’a pas été tenu." if g["plafonnee"] else ""))
    donnees = [f"{r['regle']} : {r['fait']} ({'tenu' if r['note'] >= 1 else 'non tenu'})" for r in g["plan"]["regles"]]
    return reponse(texte,
                   preuve("Σ poids × composante, puis plafond", donnees, [(n, x, f"{nombre(x, 1)}{NBSP}pts") for n, x in apports],
                          "Une décision qui a rapporté n’était pas forcément une bonne décision."),
                   "/jeu", "Rejouer")


def expliquer_modele(nom: str, r: dict) -> dict:
    """Le modèle logistique existant de la page IA : chaque barre est sa contribution exacte au logit."""
    lr = next(x for x in r["resultats"] if x["cle"] == "logistique")
    c = r["contributions"]
    verdict = ("C’est dans le bruit : il ne prédit pas mieux que le hasard." if r["dans_le_bruit"]
               else "Cet avantage passé ne garantit rien, surtout après frais.")
    texte = (f"Pour {nom}, le modèle sort {part(r['proba_hausse'], 0)} pour une séance en hausse. Ce n’est pas une prévision fiable : "
             f"il a eu raison {part(lr['precision'])} du temps, contre {part(r['reference_max'])} pour une règle naïve. {verdict} "
             f"Ce qui pèse le plus : {c[0]['libelle']}.")
    return reponse(texte,
                   preuve("Régression logistique : constante + somme des contributions",
                          [f"Données jusqu’au {r['dernier_jour']}", f"Testé en marche avant sur {r['n_test']} séances",
                           f"Constante : {nombre(r['intercept'], 3, True)}"],
                          [(x["libelle"], x["contribution"], nombre(x["contribution"], 3, True)) for x in c],
                          "Un score de modèle, pas un conseil ni une promesse."),
                   "/ia", "Ouvrir les modèles")


REPONSES = {
    "prediction": prediction, "conseil": conseil, "definition": definition, "identite": identite, "accueil": accueil,
    "inconnu": inconnu, "ordre": ordre, "temps": temps, "sources": sources, "formation": formation, "analyses": analyses_absentes,
    "portefeuille": portefeuille, "resultat": resultat, "risque": risque, "indice": indice, "actif": actif, "choc": choc,
    "assurance": assurance, "jeu": note_du_jeu,
}
# Les réponses de `couverture.py` (tableau de bord, ordres, comparaison, presse, crédit, banques réelles, page) s'ajoutent à
# cette table quand le paquet est importé : voir `app/xai/__init__.py`.
