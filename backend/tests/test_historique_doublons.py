"""Courbe de valeur après des allers-retours dans le temps : un seul point par jour, triés par date."""
from .test_portefeuille_api import acheter, aller


def test_aller_retour_dans_le_temps_sans_doublon(client, utilisateur):
    u = utilisateur()
    aller(client, u, "2020-03-06T17:00:00")
    assert acheter(client, u, 10)["statut"] == "execute"
    aller(client, u, "2020-03-09T17:00:00")
    aller(client, u, "2020-01-02T17:00:00")          # retour en arrière : un point d'un jour antérieur est ajouté
    aller(client, u, "2020-03-09T18:00:00")          # retour au même jour : sans correction, 2020-03-09 apparaît deux fois
    points = client.get("/api/v1/portefeuille/historique", headers=u.h).json()["points"]
    jours = [p["jour"] for p in points]
    assert len(jours) == len(set(jours)), jours
    assert jours == sorted(jours)
