from datetime import datetime, timedelta

import pytest

from app.marche.horloge import FACTEURS_PREDEFINIS, HorlogeSimulation, facteur_depuis


class Faux:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def avancer(self, secondes):
        self.t += secondes


D0 = datetime(2020, 1, 1)


def test_une_semaine_simulee_en_une_heure_reelle():
    faux = Faux()
    h = HorlogeSimulation(D0, facteur=FACTEURS_PREDEFINIS["1 semaine = 1 heure"], source_temps=faux)
    faux.avancer(3600)
    assert h.maintenant() == D0 + timedelta(weeks=1)


def test_facteur_depuis():
    assert facteur_depuis(timedelta(weeks=1), timedelta(hours=1)) == 168
    with pytest.raises(ValueError):
        facteur_depuis(timedelta(0), timedelta(hours=1))


def test_pause_fige_et_reprise_continue_sans_saut():
    faux = Faux()
    h = HorlogeSimulation(D0, facteur=24, source_temps=faux)
    faux.avancer(1800)
    h.pause()
    fige = h.maintenant()
    faux.avancer(9999)                      # le temps réel passe, pas le temps simulé
    assert h.maintenant() == fige and h.en_pause
    h.reprendre()
    assert h.maintenant() == fige
    faux.avancer(60)
    assert h.maintenant() == fige + timedelta(seconds=60 * 24)


def test_changer_le_facteur_ne_provoque_pas_de_saut():
    faux = Faux()
    h = HorlogeSimulation(D0, facteur=10, source_temps=faux)
    faux.avancer(100)
    avant = h.maintenant()
    h.regler_facteur(1000)
    assert h.maintenant() == avant
    faux.avancer(1)
    assert h.maintenant() == avant + timedelta(seconds=1000)


def test_aller_a():
    faux = Faux()
    h = HorlogeSimulation(D0, facteur=1, source_temps=faux)
    h.aller_a(datetime(2020, 3, 9))
    assert h.maintenant() == datetime(2020, 3, 9)
    faux.avancer(5)
    assert h.maintenant() == datetime(2020, 3, 9, 0, 0, 5)


@pytest.mark.parametrize("mauvais", [0, -1, 1e9])
def test_facteur_invalide(mauvais):
    with pytest.raises(ValueError):
        HorlogeSimulation(D0, facteur=mauvais)
    h = HorlogeSimulation(D0, facteur=1)
    with pytest.raises(ValueError):
        h.regler_facteur(mauvais)
