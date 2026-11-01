import jwt
import pytest

from app.utilisateurs import securite
from app.utilisateurs.limiteur import LimiteurFenetre
from app.utilisateurs.profil_risque import ReponsesInvalides, evaluer_profil


@pytest.mark.parametrize("mdp,attendu", [
    ("court1", "au moins 10"),
    ("uniquementdeslettres", "lettre et un chiffre"),
    ("1234567890123", "lettre et un chiffre"),
    ("password123", "trop courant"),
    ("x" * 129 + "1", "128"),
])
def test_politique_de_mot_de_passe_refus(mdp, attendu):
    assert attendu in securite.valider_mot_de_passe(mdp)


def test_politique_refuse_email_et_nom_dans_le_mot_de_passe():
    assert "e-mail" in securite.valider_mot_de_passe("zayene-2026-ok", email="zayene@example.com")
    assert "nom" in securite.valider_mot_de_passe("Mon-Marouma-2026", nom="Marouma")
    assert securite.valider_mot_de_passe("Motdepasse-2026x", email="alice@example.com", nom="Alice") is None


def test_hachage_argon2id_sel_et_verification():
    h1, h2 = securite.hacher("Motdepasse-2026x"), securite.hacher("Motdepasse-2026x")
    assert h1.startswith("$argon2id$") and h1 != h2 and "Motdepasse" not in h1
    assert securite.verifier_mot_de_passe("Motdepasse-2026x", h1) == (True, None)
    assert securite.verifier_mot_de_passe("autre-mot-de-passe1", h1) == (False, None)
    assert securite.verifier_mot_de_passe("x", "pas-un-hash") == (False, None)


def test_jwt_aller_retour_et_rejets():
    secret = "s" * 40
    jeton = securite.creer_jeton_acces(7, "trader", secret=secret)
    charge = securite.lire_jeton_acces(jeton, secret=secret)
    assert charge["sub"] == "7" and charge["role"] == "trader" and charge["typ"] == "acces"

    with pytest.raises(securite.JetonInvalide):
        securite.lire_jeton_acces(jeton, secret="autre" * 10)                      # mauvais secret
    with pytest.raises(securite.JetonInvalide):
        securite.lire_jeton_acces(securite.creer_jeton_acces(7, "trader", secret=secret, duree_min=-1), secret=secret)
    sans_signature = jwt.encode({"sub": "7", "typ": "acces", "exp": 9999999999}, key=None, algorithm="none")
    with pytest.raises(securite.JetonInvalide):                                    # attaque « alg: none »
        securite.lire_jeton_acces(sans_signature, secret=secret)
    mauvais_type = jwt.encode({"sub": "7", "typ": "autre", "exp": 9999999999}, secret, algorithm="HS256")
    with pytest.raises(securite.JetonInvalide):
        securite.lire_jeton_acces(mauvais_type, secret=secret)
    with pytest.raises(securite.JetonInvalide):
        securite.lire_jeton_acces(jeton[:-3] + "abc", secret=secret)               # signature altérée


def test_jetons_de_rafraichissement_uniques_et_haches():
    (j1, e1), (j2, e2) = securite.nouveau_jeton_rafraichissement(), securite.nouveau_jeton_rafraichissement()
    assert j1 != j2 and e1 != e2 and len(e1) == 64 and e1 == securite.empreinte(j1) and j1 not in e1


def test_limiteur_fenetre_glissante():
    t = [0.0]
    lim = LimiteurFenetre(3, 60, horloge=lambda: t[0])
    assert [lim.autoriser("ip") for _ in range(4)] == [True, True, True, False]
    assert lim.autoriser("autre-ip")
    t[0] = 61
    assert lim.autoriser("ip")


def test_profil_de_risque():
    prudent = evaluer_profil({f"q{i}": 1 for i in range(1, 7)})
    assert prudent["categorie"] == "prudent" and prudent["perte_max_toleree_pct"] == 5.0
    audacieux = evaluer_profil({f"q{i}": 4 for i in range(1, 7)})
    assert audacieux["categorie"] == "audacieux" and audacieux["perte_max_toleree_pct"] == 35.0
    assert evaluer_profil({**{f"q{i}": 2 for i in range(1, 6)}, "q6": 3})["perte_max_toleree_pct"] == 20.0
    for mauvais in ({}, {f"q{i}": 1 for i in range(1, 6)}, {**{f"q{i}": 1 for i in range(1, 7)}, "q7": 1},
                    {**{f"q{i}": 1 for i in range(1, 6)}, "q6": 5}, {**{f"q{i}": 1 for i in range(1, 6)}, "q6": True}):
        with pytest.raises(ReponsesInvalides):
            evaluer_profil(mauvais)
