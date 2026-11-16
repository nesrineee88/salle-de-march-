"""Identité comptable affichée sur la page Portefeuille :
résultat total = valeur − capital de départ = réalisé + latent − frais ; performance = résultat total / capital de départ."""
import pytest

from .test_portefeuille_api import acheter, aller


def _verifier(pf: dict) -> None:
    total = pf["equity"] - pf["capital_initial"]
    assert pf["pnl_total"] == pytest.approx(total, abs=1e-6)
    assert pf["pnl_total"] == pytest.approx(pf["pnl_realise"] + pf["pnl_latent"] - pf["frais_cumules"], abs=1e-6)


def test_identite_resultat_sur_un_parcours(client, utilisateur):
    u = utilisateur()
    lire = lambda: client.get("/api/v1/portefeuille", headers=u.h).json()  # noqa: E731
    aller(client, u, "2020-02-10T17:00:00")
    _verifier(lire())                                                     # compte neuf : tout vaut 0
    assert acheter(client, u, 120)["statut"] == "execute"
    _verifier(lire())                                                     # achat : seuls les frais et le latent bougent
    aller(client, u, "2020-02-20T17:00:00")
    assert acheter(client, u, 50, sens="vente")["statut"] == "execute"   # vente partielle : du réalisé apparaît
    _verifier(lire())
    assert acheter(client, u, 30)["statut"] == "execute"                 # rachat : nouveau prix de revient moyen
    aller(client, u, "2020-03-05T17:00:00")
    pf = lire()
    _verifier(pf)
    assert pf["pnl_realise"] != 0 and pf["frais_cumules"] > 0
    perf = pf["pnl_total"] / pf["capital_initial"]
    assert perf == pytest.approx(pf["equity"] / pf["capital_initial"] - 1)
