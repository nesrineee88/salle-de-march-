"""Module 2, La Salle Obscure : données, règles, rien du futur, portefeuille intact."""
import json
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.jeu import donnees, moteur, service
from app.jeu.catalogue import FILMS
from app.jeu.modeles import PartieJeu
from app.trading import persistance

PLAN = {"perte_max": 15, "reaction": "tenir"}
IDS = sorted(FILMS)


def bobine(film="covid"):
    return donnees.cinematheque().bobines[film]


def creer(client, u, mode="solo", film="covid", plan=PLAN, difficulte="acteur"):
    r = client.post("/api/v1/jeu/parties", json={"mode": mode, "film": film, "plan": plan, "difficulte": difficulte}, headers=u.h)
    assert r.status_code == 201, r.text
    return r.json()


def poster(client, u, p, action, **corps):
    return client.post(f"/api/v1/jeu/parties/{p['id']}/{action}", json={"version": p["version"], **corps}, headers=u.h)


def jusqu_au_bout(session, uid, acte="tenir", mode="solo", film="covid", plan=PLAN):
    """Le service, sans HTTP : des centaines de séances restent rapides."""
    p = service.creer(session, uid, mode, film, "acteur", plan if mode != "jury" else None)
    b = bobine(p.film)
    while p.statut == "en_cours":
        if moteur.arret_en_attente(b, p.seance, p.choix) is not None:
            p = service.choisir(session, p, p.version, acte)
        else:
            cible = b.arrets[len(p.choix)] if len(p.choix) < 3 else b.dernier
            # saut direct : on place la séance juste avant la cible, le dernier pas passe par `avancer`
            if cible - 1 > p.seance:
                p = service._ecrire(session, p, p.version, seance=cible - 1)
            p = service.avancer(session, p, p.version)
    return p


# ------------------------------------------------------------------ données
@pytest.mark.parametrize("film", IDS)
def test_les_quatre_controles_passent(film):
    assert donnees.cinematheque().defauts == {}
    assert donnees.controler(FILMS[film], donnees.lire_brut(film)) == []
    b = bobine(film)
    assert len(b.arrets) == 3 and 0 < b.arrets[0] < b.arrets[1] < b.arrets[2] < b.dernier
    assert all(v[0] == pytest.approx(100) for v in b.clotures.values()) and all(0 <= x <= 100 for x in b.peur)


@pytest.mark.parametrize("defaut, mot", [("trou", "trou"), ("aberrant", "variation"), ("date", "sans cours"),
                                         ("temoin", "mal calé"), ("ouverture", "recopiées"), ("negatif", "négatif")])
def test_chaque_controle_detecte_son_defaut(defaut, mot):
    film = FILMS["covid"]
    s = donnees.lire_brut("covid")
    jours = sorted(j for j in s["actions"] if film.debut <= j <= film.fin)
    if defaut == "trou":
        for j in jours[60:66]:
            for serie in s.values():
                serie.pop(j, None)
    elif defaut == "aberrant":
        s["or"][jours[70]] = (s["or"][jours[70]][0], s["or"][jours[70]][1] * 2)
    elif defaut == "date":
        s["brent"].pop(jours[50])
    elif defaut == "temoin":                                  # la série entière décalée d'une séance
        tous = sorted(s["actions"])
        valeurs = [s["actions"][j] for j in tous]
        s["actions"] = dict(zip(tous[1:], valeurs[:-1])) | {tous[0]: valeurs[0]}
    elif defaut == "ouverture":
        s["banques"] = {j: (c, c) for j, (_, c) in s["banques"].items()}
    elif defaut == "negatif":
        s["brent"][jours[55]] = (1.0, -37.0)
    assert any(mot in d for d in donnees.controler(film, s))


def test_un_fichier_modifie_retire_le_film(tmp_path):
    for f in donnees.DOSSIER.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes())
    chemin = tmp_path / "covid.csv"
    chemin.write_bytes(chemin.read_bytes().replace(b"2020-03-16", b"2020-03-15", 1))
    c = donnees.charger(tmp_path)
    assert "covid" not in c.bobines and "covid" in c.defauts and "crypto" in c.bobines


def test_les_fins_de_ligne_de_git_ne_retirent_aucun_film(tmp_path):
    for f in donnees.DOSSIER.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert donnees.charger(tmp_path).defauts == {}


def test_le_jeu_ne_demande_pas_internet(monkeypatch):
    import socket

    def interdit(*_a, **_k):
        raise AssertionError("accès réseau")

    monkeypatch.setattr(socket, "create_connection", interdit)
    monkeypatch.setattr(socket.socket, "connect", interdit)
    assert donnees.charger().defauts == {}


@pytest.mark.parametrize("film", IDS)
def test_la_peur_ne_lit_pas_le_futur(film):
    s = donnees.lire_brut(film)
    complet = donnees.monter_bobine(FILMS[film], s)
    coupe = complet.jours[50]
    alteree = {c: {j: ((o, v) if j <= coupe else (o * 1.4, v * 1.4)) for j, (o, v) in serie.items()} for c, serie in s.items()}
    assert donnees.monter_bobine(FILMS[film], alteree).peur[:51] == complet.peur[:51]


def test_le_public_fuit_au_pire_de_chaque_crise():
    for film, b in donnees.cinematheque().bobines.items():
        assert max(b.peur) >= 80, film
        assert min(b.peur) <= 35, film


# ------------------------------------------------------------------ moteur
def test_un_ordre_part_a_l_ouverture_suivante():
    b = bobine()
    i = 10
    e = moteur.rejouer(b, i + 1, 0.002, [{"jour": i, "cle": "actions", "sens": "achat"}], [])
    [x] = e.executions
    assert x["jour"] == i + 1 and x["prix"] == b.ouvertures["actions"][i + 1] and x["prix"] != b.clotures["actions"][i]
    _, q0 = moteur.depart(b)
    assert e.q["actions"] - q0["actions"] == pytest.approx(moteur.MISE / 1.002 / x["prix"])
    assert moteur.rejouer(b, i, 0.002, [{"jour": i, "cle": "actions", "sens": "achat"}], []).executions == []


def test_sans_decision_on_egale_son_double():
    b = bobine()
    assert moteur.rejouer(b, b.dernier, 0.004, [], []).valeurs == pytest.approx(moteur.double_immobile(b, b.dernier))


def test_le_rejeu_ne_lit_rien_apres_la_seance():
    b = bobine()
    i = 40
    ordres = [{"jour": 12, "cle": "or", "sens": "achat"}]
    altere = donnees.Bobine(b.film, b.jours, {c: v[:i + 1] + (1e9,) * (b.dernier - i) for c, v in b.ouvertures.items()},
                            {c: v[:i + 1] + (1e9,) * (b.dernier - i) for c, v in b.clotures.items()},
                            b.peur, b.peur_mesure, b.scenes, b.arrets)
    assert moteur.rejouer(altere, i, 0.002, ordres, []).valeurs == moteur.rejouer(b, i, 0.002, ordres, []).valeurs


@pytest.mark.parametrize("film", IDS)
@pytest.mark.parametrize("acte", sorted(moteur.ACTES))
def test_jamais_de_liquidites_negatives(film, acte):
    b = bobine(film)
    ordres = [{"jour": j, "cle": b.film.actifs[0].cle, "sens": "achat"} for j in range(1, 12) for _ in range(3)]
    e = moteur.rejouer(b, b.dernier, 0.004, ordres, [{"jour": j, "acte": acte} for j in b.arrets])
    assert e.cash >= -1e-6 and all(q >= 0 for q in e.q.values())


def test_les_frais_de_sortie():
    b = bobine()
    j = b.arrets[0]
    e = moteur.rejouer(b, j + 1, 0.004, [], [{"jour": j, "acte": "sortir"}])
    cash0, q0 = moteur.depart(b)
    brut = sum(q * b.ouvertures[c][j + 1] for c, q in q0.items())
    assert e.cash == pytest.approx(cash0 + brut * 0.996) and e.frais == pytest.approx(brut * 0.004)


def test_le_sang_froid_juge_le_plan_et_pas_le_resultat():
    b = bobine()
    choix = [{"jour": j, "acte": "tenir"} for j in b.arrets]
    e = moteur.rejouer(b, b.dernier, 0.002, [], choix)
    chute = moteur.baisses(e.valeurs)
    r = moteur.respect_du_plan(b, {"perte_max": 25, "reaction": "tenir"}, e, [], choix)
    for k, j in enumerate(b.arrets):
        assert r["regles"][k]["note"] == (0.0 if chute[j] >= 0.25 else 1.0)
    serre = moteur.respect_du_plan(b, {"perte_max": 5, "reaction": "tenir"}, e, [], choix)
    assert serre["note"] < r["note"]                         # même partie, même résultat, plan non tenu
    assert any("franchie" in x["regle"] and x["note"] == 0 for x in serre["regles"])


def test_sortir_comme_annonce_est_un_plan_tenu():
    b = bobine()
    plan = {"perte_max": 25, "reaction": "sortir"}
    choix = [{"jour": j, "acte": "sortir"} for j in b.arrets]
    e = moteur.rejouer(b, b.dernier, 0.002, [], choix)
    assert moteur.respect_du_plan(b, plan, e, [], choix)["note"] == 100


def test_la_note_est_la_somme_ponderee_et_le_jury_n_est_pas_note():
    b = bobine()
    choix = [{"jour": j, "acte": "tenir"} for j in b.arrets]
    r = moteur.noter(b, 0.002, PLAN, [], choix)
    assert r["resultat"] == pytest.approx(50)                # égal au double immobile
    assert r["note"] == round(0.40 * r["resultat"] + 0.35 * r["protection"] + 0.25 * r["plan"]["note"])
    jury = moteur.noter(b, 0.002, None, [], choix)
    assert jury["note"] is None and jury["plan"] is None and jury["prix"] == "Verdict du jury"


@pytest.mark.parametrize("film", IDS)
def test_le_montage_change_une_seule_decision(film):
    b = bobine(film)
    choix = [{"jour": j, "acte": a} for j, a in zip(b.arrets, ("reduire", "tenir", "renforcer"))]
    ordres = [{"jour": 5, "cle": "or", "sens": "achat"}]
    reel = moteur.rejouer(b, b.dernier, 0.002, ordres, choix).valeurs
    m = moteur.montage(b, 0.002, ordres, choix)
    assert len(m) == 3 and all(len(x["autres"]) == 3 for x in m)
    for k, x in enumerate(m):
        for autre in x["autres"]:
            assert autre["courbe"][: b.arrets[k] + 1] == pytest.approx(reel[: b.arrets[k] + 1], abs=0.01)   # même passé
            attendu = moteur.rejouer(b, b.dernier, 0.002, ordres, [*choix[:k], {**choix[k], "acte": autre["acte"]}, *choix[k + 1:]])
            assert autre["valeur"] == pytest.approx(attendu.valeurs[-1])


def test_deja_sorti_se_lit_dans_les_positions():
    b = bobine()
    vendu = [{"jour": 0, "cle": a.cle, "sens": "vente"} for a in b.film.actifs if a.risque for _ in range(8)]
    choix = [{"jour": j, "acte": "tenir"} for j in b.arrets]
    e = moteur.rejouer(b, b.dernier, 0.002, vendu, choix)
    assert e.expositions[1] < moteur.SEUIL_SORTI
    annonce = moteur.respect_du_plan(b, {"perte_max": 25, "reaction": "sortir"}, e, vendu, choix)
    assert annonce["note"] == 100
    contredit = moteur.respect_du_plan(b, {"perte_max": 25, "reaction": "tenir"}, e, vendu, choix)
    assert contredit["note"] < 50


def test_vendre_de_l_or_n_allege_pas_le_risque():
    b = bobine()
    plan, choix = {"perte_max": 5, "reaction": "tenir"}, [{"jour": j, "acte": "tenir"} for j in b.arrets]
    chute = moteur.baisses(moteur.rejouer(b, b.dernier, 0.002, [], choix).valeurs)
    jour = next(i for i, x in enumerate(chute) if x >= 0.05)

    def regle(cle):
        ordres = [{"jour": jour, "cle": cle, "sens": "vente"}]
        r = moteur.respect_du_plan(b, plan, moteur.rejouer(b, b.dernier, 0.002, ordres, choix), ordres, choix)
        return next(x["note"] for x in r["regles"] if "franchie" in x["regle"])

    assert regle("or") == 0 and regle("actions") == 1


def test_paniquer_contre_son_plan_plafonne_la_note():
    b = bobine("2008")
    choix = [{"jour": j, "acte": "sortir"} for j in b.arrets]
    chance = moteur.noter(b, 0.002, PLAN, [], choix)
    assert chance["plafonnee"] is True and chance["note"] == moteur.PLAFOND_PLAN_NON_TENU
    annonce = moteur.noter(b, 0.002, {"perte_max": 15, "reaction": "sortir"}, [], choix)
    assert annonce["plafonnee"] is False and annonce["note"] > chance["note"]


# ------------------------------------------------------------------ API : rien du futur
def test_connexion_exigee(client):
    assert client.get("/api/v1/jeu/accueil").status_code == 401
    assert client.post("/api/v1/jeu/parties", json={}).status_code == 401


def test_accueil(client, utilisateur):
    a = client.get("/api/v1/jeu/accueil", headers=utilisateur().h).json()
    assert [f["id"] for f in a["films"]] == ["covid", "crypto", "2008"] and all(f["disponible"] for f in a["films"])
    assert a["pertes_max"] == [5, 10, 15, 20, 25] and a["reprise"] is None and a["mystere"]["classable"] is True


def test_le_plan_est_obligatoire_et_borne(client, utilisateur):
    u = utilisateur()
    url = "/api/v1/jeu/parties"
    assert client.post(url, json={"mode": "solo", "film": "covid"}, headers=u.h).status_code == 422
    for perte in (99, 0, 30):
        r = client.post(url, json={"mode": "solo", "film": "covid", "plan": {"perte_max": perte, "reaction": "tenir"}}, headers=u.h)
        assert r.status_code == 422
    assert client.post(url, json={"mode": "solo", "film": "inconnu", "plan": PLAN}, headers=u.h).status_code == 422


def test_un_jour_a_la_fois_et_rien_du_futur(client, utilisateur):
    u = utilisateur()
    b = bobine()
    p = creer(client, u)
    for i in range(0, 9):
        assert p["seance"] == i
        for a in p["actifs"]:
            assert len(a["clotures"]) == len(a["ouvertures"]) == i + 1
        brut = json.dumps(p, ensure_ascii=False)
        assert (b.jours[i] + timedelta(days=1)).isoformat() not in brut and b.jours[b.arrets[0]].isoformat() not in brut
        assert b.film.fin.isoformat() not in brut and p["generique"] is None and "Les foyers" not in brut
        assert not {"total", "dernier", "fin", "arrets", "scenes"} & set(p)
        p = poster(client, u, p, "avancer").json()


def test_le_client_ne_peut_pas_sauter_ni_ecrire_son_score(client, utilisateur):
    u = utilisateur()
    p = creer(client, u)
    assert poster(client, u, p, "avancer", jusqu_a_l_arret=True).status_code == 409
    q = poster(client, u, p, "avancer", seance=140, note=100, statut="terminee").json()
    assert q["seance"] == 1 and q["statut"] == "en_cours" and q["generique"] is None


def test_deux_actions_du_meme_etat(client, utilisateur):
    u = utilisateur()
    p = creer(client, u)
    assert poster(client, u, p, "avancer").status_code == 200
    r = poster(client, u, p, "avancer")
    assert r.status_code == 409 and r.json()["code"] == "version_perimee"


def test_un_arret_bloque_le_film(client, utilisateur, base_test):
    u = utilisateur()
    p = creer(client, u)
    arret = bobine().arrets[0]
    with base_test.session() as s:
        ligne = s.get(PartieJeu, p["id"])
        ligne.seance = arret - 1
        s.commit()
    assert poster(client, u, p, "choix", acte="tenir").status_code == 409
    p = poster(client, u, p, "avancer").json()
    assert p["arret"]["numero"] == 0 and len(p["arret"]["options"]) == 4 and "foyers" in p["arret"]["evenement"]
    assert poster(client, u, p, "avancer").status_code == 409
    assert poster(client, u, p, "ordres", rang=0, sens="achat").status_code == 409
    p = poster(client, u, p, "choix", acte="reduire").json()
    assert p["arret"] is None
    avant = p["liquidites"]
    assert poster(client, u, p, "avancer").json()["liquidites"] > avant       # la vente part à l'ouverture suivante


def test_ordre_en_attente_puis_execute(client, utilisateur):
    u = utilisateur()
    p = creer(client, u)
    apres = poster(client, u, p, "ordres", rang=0, sens="achat").json()
    assert apres["actifs"][0]["en_attente"] == ["achat"] and apres["engage"] == moteur.MISE
    assert apres["liquidites"] == p["liquidites"]                              # rien n'est exécuté aujourd'hui
    suivant = poster(client, u, apres, "avancer").json()
    assert suivant["liquidites"] == pytest.approx(p["liquidites"] - moteur.MISE) and suivant["engage"] == 0


def test_on_ne_peut_pas_engager_plus_que_ses_liquidites(client, utilisateur):
    u = utilisateur()
    p = creer(client, u)
    n = 0
    while True:
        r = poster(client, u, p, "ordres", rang=0, sens="achat")
        if r.status_code != 200:
            break
        p = r.json()
        n += 1
        assert n < 9
    assert r.status_code == 409 and n * moteur.MISE >= p["liquidites"] - 1 > (n - 1) * moteur.MISE


def test_une_partie_est_privee(client, utilisateur):
    p = creer(client, utilisateur())
    bob = utilisateur("bob@example.com", "Bob")
    assert client.get(f"/api/v1/jeu/parties/{p['id']}", headers=bob.h).status_code == 404
    assert poster(client, bob, p, "avancer").status_code == 404


def test_la_seance_mystere_masque_tout(client, utilisateur, base_test):
    u = utilisateur()
    p = creer(client, u, mode="mystere", film=None)
    assert p["film"] is None and p["date"] is None and p["peur_mesure"] is None and p["classable"] is None
    assert sorted(a["nom"] for a in p["actifs"]) == ["Actif A", "Actif B", "Actif C", "Actif D"]
    with base_test.session() as s:
        ligne = s.get(PartieJeu, p["id"])
        b = bobine(ligne.film)
        ligne.seance = b.arrets[0] - 1
        s.commit()
    p = poster(client, u, p, "avancer").json()
    brut = json.dumps(p, ensure_ascii=False)
    interdits = [b.film.titre, b.film.sujet, "Bitcoin", "Banques", "VIX", "Lehman", "pandémie", "UST", "2008", "2020-", "2022-"]
    interdits += [a.detail for a in b.film.actifs]
    assert not [x for x in interdits if x in brut]


def test_la_seance_mystere_refuse_un_film_choisi(client, utilisateur):
    r = client.post("/api/v1/jeu/parties", json={"mode": "mystere", "film": "covid", "plan": PLAN}, headers=utilisateur().h)
    assert r.status_code == 422


def test_generique_mystere_puis_revelation(client, utilisateur, base_test):
    u = utilisateur()
    with base_test.session() as s:
        fini = jusqu_au_bout(s, u.id, mode="mystere", film=None)
        pid, film = fini.id, fini.film
    p = client.get(f"/api/v1/jeu/parties/{pid}", headers=u.h).json()
    g = p["generique"]
    assert p["statut"] == "terminee" and p["film"] is None and g["lecon"] is None and len(g["a_deviner"]) == 3
    assert all(m["date"] is None and m["evenement"] is None for m in g["montage"])
    r = poster(client, u, p, "deviner", film=film).json()
    assert r["film"] == film and r["generique"]["devine"]["juste"] is True and r["generique"]["lecon"]
    assert poster(client, u, r, "deviner", film=film).status_code == 409


@pytest.mark.parametrize("film", IDS)
def test_partie_complete_note_recalculee_par_le_serveur(client, utilisateur, base_test, film):
    u = utilisateur()
    with base_test.session() as s:
        fini = jusqu_au_bout(s, u.id, acte="renforcer", film=film)
        pid, note = fini.id, fini.note
    g = client.get(f"/api/v1/jeu/parties/{pid}", headers=u.h).json()["generique"]
    b = bobine(film)
    attendu = moteur.noter(b, 0.002, PLAN, [], [{"jour": j, "acte": "renforcer"} for j in b.arrets])
    assert g["note"] == note == attendu["note"] and len(g["courbe"]) == len(b.jours) and len(g["montage"]) == 3


def test_le_jury_decide_hors_classement(client, utilisateur):
    u = utilisateur()
    p = creer(client, u, mode="jury", film="covid", plan=None)
    assert p["plan"] is None and p["classable"] is False
    for k, acte in enumerate(("reduire", "tenir", "renforcer")):
        p = poster(client, u, p, "avancer", jusqu_a_l_arret=True).json()
        assert p["arret"]["numero"] == k and p["seance"] == bobine().arrets[k]
        p = poster(client, u, p, "choix", acte=acte).json()
    p = poster(client, u, p, "avancer", jusqu_a_l_arret=True).json()
    assert p["statut"] == "terminee" and p["generique"]["note"] is None and len(p["generique"]["montage"]) == 3
    assert client.get("/api/v1/jeu/accueil", headers=u.h).json()["classement"] == []


def test_seule_la_premiere_rencontre_est_classee(client, utilisateur, base_test):
    u = utilisateur()
    with base_test.session() as s:
        for f in IDS:                                          # il a déjà vu les trois films
            service.creer(s, u.id, "solo", f, "acteur", PLAN)
        assert jusqu_au_bout(s, u.id, mode="mystere", film=None).premiere is False
        assert service.classement(s) == []
    bob = utilisateur("bob@example.com", "Bob")
    with base_test.session() as s:
        note = jusqu_au_bout(s, bob.id, mode="mystere", film=None).note
        assert service.classement(s) == [{"rang": 1, "nom": "Bob", "note": note, "parties": 1}]


def test_avoir_vu_deux_films_ne_revele_pas_le_troisieme(utilisateur, base_test):
    u = utilisateur()
    with base_test.session() as s:
        for f in IDS[:2]:
            service.creer(s, u.id, "solo", f, "acteur", PLAN)
        assert {service.creer(s, u.id, "mystere", None, "acteur", PLAN).film for _ in range(120)} == set(IDS)


def test_l_accueil_ne_trahit_pas_la_partie_mystere_en_cours(utilisateur, base_test):
    u = utilisateur()
    with base_test.session() as s:
        for f in IDS[:2]:
            jusqu_au_bout(s, u.id, film=f)
        service.creer(s, u.id, "mystere", None, "acteur", PLAN)
        assert service.accueil(s, u.id)["mystere"]["classable"] is True     # quel que soit le film tiré


def test_les_montants_de_depart_ne_revelent_pas_le_film(utilisateur, base_test):
    u = utilisateur()
    montants = set()
    with base_test.session() as s:
        for f in IDS:
            p = service.creer(s, u.id, "solo", f, "acteur", PLAN)
            p.mode = "mystere"                                  # la même vue, masquée, sur chacun des films
            v = service.vue(p)
            assert all(a["ouvertures"] == [100.0] for a in v["actifs"])
            montants.add((v["liquidites"], v["engage"], round(v["valeur"], 2), tuple(sorted(a["valeur"] for a in v["actifs"]))))
            s.rollback()
    assert len(montants) == 1


def test_reprise_apres_redemarrage(client, utilisateur, base_test):
    from app.utilisateurs.db import BaseUtilisateurs

    u = utilisateur()
    p = creer(client, u)
    for _ in range(4):
        p = poster(client, u, p, "avancer").json()
    p = poster(client, u, p, "ordres", rang=1, sens="vente").json()
    neuve = BaseUtilisateurs(str(base_test.moteur.url))
    with neuve.session() as s:
        assert service.vue(service.lire_partie(s, u.id, p["id"])) == p
    neuve.moteur.dispose()
    assert client.get("/api/v1/jeu/accueil", headers=u.h).json()["reprise"]["id"] == p["id"]


def test_une_nouvelle_partie_abandonne_la_precedente(client, utilisateur, base_test):
    u = utilisateur()
    ancienne = creer(client, u)
    creer(client, u, film="crypto")
    assert poster(client, u, ancienne, "avancer").status_code == 409
    with base_test.session() as s:
        assert s.scalar(select(func.count()).select_from(PartieJeu).where(PartieJeu.statut == "en_cours")) == 1


def test_le_portefeuille_est_intact(client, utilisateur, base_test):
    u = utilisateur()
    client.post("/api/v1/horloge/aller-a", json={"instant": "2020-02-10T17:00:00"}, headers=u.h)
    achat = {"symbole": "TST", "sens": "achat", "quantite": 12, "type": "marche"}
    assert client.post("/api/v1/ordres", json=achat, headers=u.h).json()["statut"] == "execute"
    avant = client.get("/api/v1/portefeuille", headers=u.h).json()
    with base_test.session() as s:
        etat = persistance.charger(s, u.id)
    p = creer(client, u)
    p = poster(client, u, p, "ordres", rang=0, sens="vente").json()
    for _ in range(5):
        p = poster(client, u, p, "avancer").json()
    with base_test.session() as s:
        jusqu_au_bout(s, u.id, acte="sortir")
        assert persistance.charger(s, u.id) == etat
    assert client.get("/api/v1/portefeuille", headers=u.h).json() == avant
