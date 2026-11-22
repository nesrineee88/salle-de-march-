"""Comptes enregistrés quand on pouvait reculer : la courbe garde un seul point par jour, triés par date."""
from datetime import datetime

from .test_portefeuille_api import acheter, aller


def test_aller_retour_dans_le_temps_sans_doublon(client, utilisateur, ctx_test):
    u = utilisateur()
    aller(client, u, "2020-03-06T17:00:00")
    assert acheter(client, u, 10)["statut"] == "execute"
    aller(client, u, "2020-03-09T17:00:00")
    ctx_test.bac(u.id).horloge.aller_a(datetime(2020, 1, 2, 17))          # ancien compte : un point d'un jour antérieur est ajouté
    client.get("/api/v1/portefeuille", headers=u.h)
    aller(client, u, "2020-03-09T18:00:00")          # retour au même jour : sans correction, 2020-03-09 apparaît deux fois
    points = client.get("/api/v1/portefeuille/historique", headers=u.h).json()["points"]
    jours = [p["jour"] for p in points]
    assert len(jours) == len(set(jours)), jours
    assert jours == sorted(jours)
