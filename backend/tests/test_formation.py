"""Formation : leçons, correction côté serveur, progression, ligue, vue du formateur."""
import pytest

from app.formation import contenu, service


def reponses_justes(client, u, lecon_id):
    """Retrouve, à partir de la leçon affichée à l'utilisateur, l'indice affiché de chaque bonne réponse."""
    d = client.get(f"/api/v1/formation/lecons/{lecon_id}", headers=u.h).json()
    bonnes = []
    for q, original in zip(d["questions"], contenu.INDEX[lecon_id]["questions"]):
        bonnes.append(q["choix"].index(original["choix"][original["bonne"]]))
    return bonnes


def test_le_contenu_est_coherent():
    assert len({l["id"] for l in contenu.LECONS}) == 8
    for l in contenu.LECONS:
        assert l["questions"] and l["sections"] and l["exercices"]
        for q in l["questions"]:
            assert len(q["choix"]) == 4 and 0 <= q["bonne"] < 4 and len(set(q["choix"])) == 4 and q["explication"]


def test_les_bonnes_reponses_ne_sont_jamais_envoyees(client, utilisateur):
    u = utilisateur()
    d = client.get("/api/v1/formation/lecons/ordres", headers=u.h).json()
    brut = str(d)
    assert "bonne" not in brut and "explication" not in brut
    assert len(d["questions"]) == 3 and all(len(q["choix"]) == 4 for q in d["questions"])
    assert sorted(d["questions"][0]["choix"]) == sorted(contenu.INDEX["ordres"]["questions"][0]["choix"])        # mêmes choix, ordre mélangé


def test_l_ordre_des_choix_est_stable_mais_differe_selon_l_utilisateur(client, utilisateur):
    a, b = utilisateur("a@example.com", "Aline"), utilisateur("b@example.com", "Bruno")
    ordre = lambda u: [q["choix"] for q in client.get("/api/v1/formation/lecons/risque", headers=u.h).json()["questions"]]
    assert ordre(a) == ordre(a)
    assert ordre(a) != ordre(b)


def test_correction_et_progression(client, utilisateur):
    u = utilisateur()
    j = reponses_justes(client, u, "ordres")
    r = client.post("/api/v1/formation/lecons/ordres/repondre", json={"reponses": j}, headers=u.h).json()
    assert r["score"] == 1 and r["reussie"] and all(c["juste"] and c["explication"] for c in r["corrections"])
    mauvaises = [(x + 1) % 4 for x in j]
    r2 = client.post("/api/v1/formation/lecons/ordres/repondre", json={"reponses": mauvaises}, headers=u.h).json()
    assert r2["score"] == 0 and not r2["reussie"] and [c["bonne_reponse"] for c in r2["corrections"]] == j      # la correction révèle la bonne réponse
    liste = client.get("/api/v1/formation/lecons", headers=u.h).json()
    o = next(l for l in liste["lecons"] if l["id"] == "ordres")
    assert o["tentatives"] == 2 and o["meilleur_score"] == 1 and o["reussie"]                                   # le meilleur score et la réussite sont conservés
    assert liste["progression"]["lecons_reussies"] == 1 and liste["progression"]["lecons_actives"] == 8
    partiel = client.post("/api/v1/formation/lecons/risque/repondre", json={"reponses": [reponses_justes(client, u, "risque")[0], None, None]}, headers=u.h).json()
    assert partiel["bonnes"] == 1 and not partiel["reussie"] and partiel["score"] == pytest.approx(1 / 3)


@pytest.mark.parametrize("corps", [{"reponses": [0]}, {"reponses": [0, 1, 9]}, {"reponses": "x"}, {"reponses": [0, 1, 2, 3]}])
def test_reponses_invalides(client, utilisateur, corps):
    u = utilisateur()
    assert client.post("/api/v1/formation/lecons/ordres/repondre", json=corps, headers=u.h).status_code == 422


def test_lecon_inconnue_et_acces(client, utilisateur):
    u = utilisateur()
    assert client.get("/api/v1/formation/lecons/nope", headers=u.h).status_code == 404
    assert client.post("/api/v1/formation/lecons/nope/repondre", json={"reponses": []}, headers=u.h).status_code == 404
    assert client.get("/api/v1/formation/lecons").status_code == 401


def test_desactivation_par_le_formateur(client, utilisateur):
    appr = utilisateur()
    formateur = utilisateur("f@example.com", "Fatma", role="formateur")
    assert client.patch("/api/v1/formation/lecons/ordres/activation", json={"actif": False}, headers=appr.h).status_code == 403
    assert client.patch("/api/v1/formation/lecons/ordres/activation", json={"actif": False}, headers=formateur.h).json() == {"id": "ordres", "active": False}
    ids = lambda u: [l["id"] for l in client.get("/api/v1/formation/lecons", headers=u.h).json()["lecons"]]
    assert "ordres" not in ids(appr) and "ordres" in ids(formateur)                                           # le formateur la voit toujours, désactivée
    assert client.get("/api/v1/formation/lecons/ordres", headers=appr.h).status_code == 404
    assert client.get("/api/v1/formation/lecons/ordres", headers=formateur.h).status_code == 200
    assert client.get("/api/v1/formation/lecons", headers=appr.h).json()["progression"]["lecons_actives"] == 7
    client.patch("/api/v1/formation/lecons/ordres/activation", json={"actif": True}, headers=formateur.h)
    assert "ordres" in ids(appr)
    assert client.patch("/api/v1/formation/lecons/zz/activation", json={"actif": True}, headers=formateur.h).status_code == 404


def acheter_et_avancer(client, u, jusqu_a="2020-03-10"):
    client.post("/api/v1/horloge/aller-a", json={"instant": "2020-01-20T17:00:00"}, headers=u.h)
    client.post("/api/v1/ordres", json={"symbole": "TST", "sens": "achat", "quantite": 200, "type": "marche"}, headers=u.h)
    for jour in range(21, 29):
        client.post("/api/v1/horloge/aller-a", json={"instant": f"2020-02-{jour}T17:00:00"}, headers=u.h)
    client.post("/api/v1/horloge/aller-a", json={"instant": f"{jusqu_a}T17:00:00"}, headers=u.h)


def test_ligue_et_vue_du_formateur(client, utilisateur):
    a, b = utilisateur("a@example.com", "Aline"), utilisateur("b@example.com", "Bruno")
    formateur = utilisateur("f@example.com", "Fatma", role="formateur")
    acheter_et_avancer(client, a)
    client.post("/api/v1/horloge/aller-a", json={"instant": "2020-01-10T17:00:00"}, headers=b.h)             # Bruno : trop peu de jours
    ligue = client.get("/api/v1/formation/ligue", headers=a.h).json()
    assert [l["nom"] for l in ligue["classement"]] == ["Aline"] and ligue["classement"][0]["rang"] == 1 and "prudence" in ligue["regle"]
    l = ligue["classement"][0]
    assert l["points"] >= 5 and l["date_simulee"] == "2020-03-10" and "email" not in str(ligue)                # aucun e-mail dans le classement
    assert l["score"] == pytest.approx(l["rendement"] / max(l["drawdown"], 0.05))
    # date commune : seuls ceux qui l'ont atteinte sont classés
    assert client.get("/api/v1/formation/ligue?jusqu_au=2020-02-25", headers=a.h).json()["classement"][0]["date_simulee"] == "2020-02-25"
    assert client.get("/api/v1/formation/ligue?jusqu_au=2020-03-20", headers=a.h).json()["classement"] == []
    assert "même date" in client.get("/api/v1/formation/ligue?jusqu_au=2020-02-25", headers=a.h).json()["regle"]

    assert client.get("/api/v1/formation/classe", headers=a.h).status_code == 403
    c = client.get("/api/v1/formation/classe", headers=formateur.h).json()
    assert {x["nom"] for x in c} == {"Aline", "Bruno"}                                                          # le formateur n'est pas dans sa classe
    aline = next(x for x in c if x["nom"] == "Aline")
    assert aline["portefeuille"]["date_simulee"] == "2020-03-10" and next(x for x in c if x["nom"] == "Bruno")["portefeuille"] is None
    assert "@" not in str(c)


def test_performance_pire_baisse_a_la_main():
    pts = [{"jour": f"2020-01-0{i}", "equity": v} for i, v in zip(range(1, 7), [100_000, 110_000, 99_000, 105_000, 120_000, 108_000])]
    p = service._performance(pts, None)
    assert p["rendement"] == pytest.approx(0.08) and p["drawdown"] == pytest.approx(0.10)                      # 120 000 → 108 000 : −10 %
    assert p["score"] == pytest.approx(0.8)
    calme = service._performance([{"jour": f"2020-01-0{i}", "equity": 100_000 + 1000 * i} for i in range(1, 7)], None)
    assert calme["drawdown"] == 0 and calme["score"] == pytest.approx(calme["rendement"] / 0.05)                # plancher de 5 %
    assert service._performance(pts[:3], None) is None
