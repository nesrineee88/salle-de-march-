"""Les films : période, actifs, événements, arrêts sur image.

Pourquoi des fonds cotés (SPY, KBE, BNO, GLD, TLT) plutôt que des indices ou des contrats continus :
 - en 2008 l'ouverture publiée du S&P 500 Total Return recopie la clôture (165 séances sur 230) : impossible d'y exécuter
   honnêtement « à l'ouverture suivante » ;
 - le Brent continu (BZ=F) change d'échéance chaque mois et invente des gains : −16,8 % sur le film de 2020, quand un fonds
   Brent réellement achetable (BNO) perd 33,1 %.

Les événements sont rédigés de mémoire : à relire avant présentation. Un événement apparaît à la clôture de sa séance, une
décision part à l'ouverture suivante.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ActifJeu:
    cle: str
    nom: str
    detail: str
    symbole: str                  # symbole chez la source
    depart: float                 # part investie au début : la même à chaque position dans les trois films (sinon fuite en mystère)
    risque: bool = True           # concerné par « réduire »


@dataclass(frozen=True)
class Temoin:
    """Fait connu qui prouve que les dates sont calées : ce jour-là la série a bougé au moins d'autant."""
    cle: str
    jour: date
    variation: float              # négatif : baisse au moins aussi forte ; positif : hausse


@dataclass(frozen=True)
class Film:
    id: str
    titre: str
    sujet: str
    accroche: str
    lecon: str
    debut: date
    fin: date
    intensite: int
    actifs: tuple[ActifJeu, ...]
    vedette: str                  # actif projeté au lancement
    cible_renforcer: str          # où va l'argent de « renforcer »
    peur: tuple[str, str]         # ("vix", clé de la série) ou ("chute", clé de l'actif)
    scenes: tuple[tuple[date, str], ...]
    arrets: tuple[date, date, date]
    temoins: tuple[Temoin, ...]

    @property
    def calendrier(self) -> str:
        """La série dont les séances rythment le film."""
        return self.actifs[-1].cle if self.id == "crypto" else self.actifs[0].cle


d = date.fromisoformat

COVID = Film(
    id="covid", titre="Villes Fermées", sujet="Corona, 2020",
    accroche="Le monde s’arrête en trois semaines. Le marché repartira avant lui.",
    lecon="Le marché remonte souvent quand les nouvelles sont encore mauvaises. Celui qui sort au creux rate le rebond.",
    debut=d("2020-02-03"), fin=d("2020-08-31"), intensite=4,
    actifs=(
        ActifJeu("actions", "Actions", "S&P 500, fonds SPY", "SPY", 0.40),
        ActifJeu("banques", "Banques", "Banques américaines, fonds KBE", "KBE", 0.15),
        ActifJeu("brent", "Pétrole Brent", "Fonds BNO, roulement compris", "BNO", 0.10),
        ActifJeu("or", "Or", "Fonds GLD", "GLD", 0.10, risque=False),
    ),
    vedette="actions", cible_renforcer="actions", peur=("vix", "vix"),
    scenes=(
        (d("2020-02-03"), "Un virus respiratoire inquiète. Les marchés restent confiants."),
        (d("2020-02-24"), "Les foyers se multiplient hors de Chine. Les actions décrochent."),
        (d("2020-03-09"), "Guerre des prix entre Riyad et Moscou : le pétrole s’effondre."),
        (d("2020-03-11"), "L’OMS parle de pandémie."),
        (d("2020-03-12"), "Les frontières se ferment. Wall Street vit l’une de ses pires séances."),
        (d("2020-03-16"), "La Fed a ramené ses taux à zéro la veille. La panique continue."),
        (d("2020-03-23"), "La Fed promet des achats sans limite fixée."),
        (d("2020-04-20"), "Le pétrole américain passe sous zéro sur le contrat de mai."),
        (d("2020-06-05"), "L’emploi américain surprend par son rebond."),
    ),
    arrets=(d("2020-02-24"), d("2020-03-12"), d("2020-03-23")),
    temoins=(Temoin("actions", d("2020-03-16"), -0.09), Temoin("actions", d("2020-03-24"), 0.07), Temoin("brent", d("2020-03-09"), -0.15)),
)

CRYPTO = Film(
    id="crypto", titre="Retraits Suspendus", sujet="Hiver crypto, 2022",
    accroche="Votre solde s’affiche. Mais pouvez-vous le retirer ?",
    lecon="Le risque de contrepartie existe même si le prix ne bouge pas : qui détient vraiment votre argent ?",
    debut=d("2022-04-01"), fin=d("2022-12-30"), intensite=5,
    actifs=(
        ActifJeu("btc", "Bitcoin", "En dollars", "BTC-USD", 0.40),
        ActifJeu("eth", "Ethereum", "En dollars", "ETH-USD", 0.15),
        ActifJeu("sol", "Solana", "En dollars", "SOL-USD", 0.10),
        ActifJeu("or", "Or", "Fonds GLD", "GLD", 0.10, risque=False),
    ),
    vedette="btc", cible_renforcer="btc", peur=("chute", "btc"),
    scenes=(
        (d("2022-04-01"), "Des rendements de 20 % sont promis sur des jetons « stables »."),
        (d("2022-05-09"), "Le jeton UST perd son ancrage au dollar."),
        (d("2022-05-12"), "Le jeton Luna ne vaut presque plus rien."),
        (d("2022-06-13"), "La plateforme Celsius suspend les retraits."),
        (d("2022-07-06"), "Le prêteur Voyager se déclare en faillite."),
        (d("2022-11-08"), "FTX bloque des retraits."),
        (d("2022-11-11"), "FTX se déclare en faillite."),
    ),
    arrets=(d("2022-05-09"), d("2022-06-13"), d("2022-11-08")),
    temoins=(Temoin("btc", d("2022-06-13"), -0.10), Temoin("sol", d("2022-11-09"), -0.30)),
)

CRISE_2008 = Film(
    id="2008", titre="Le Dernier Guichet", sujet="Crise financière, 2008",
    accroche="Les banques ne se prêtent plus. Qui tombera ensuite ?",
    lecon="Une banque solvable peut mourir d’un manque de liquidité. Pendant la panique, presque tout baisse ensemble.",
    debut=d("2008-08-01"), fin=d("2009-06-30"), intensite=5,
    actifs=(
        ActifJeu("actions", "Actions", "S&P 500, fonds SPY", "SPY", 0.40),
        ActifJeu("banques", "Banques", "Banques américaines, fonds KBE", "KBE", 0.15),
        ActifJeu("or", "Or", "Fonds GLD", "GLD", 0.10, risque=False),
        ActifJeu("obligations", "Obligations d’État", "Trésor américain, fonds TLT", "TLT", 0.10, risque=False),
    ),
    vedette="actions", cible_renforcer="actions", peur=("vix", "vix"),
    scenes=(
        (d("2008-08-01"), "Le crédit immobilier craque. Les banques se méfient les unes des autres."),
        (d("2008-09-15"), "Lehman Brothers se déclare en faillite."),
        (d("2008-09-29"), "Le Congrès rejette le plan de sauvetage des banques."),
        (d("2008-10-03"), "Le plan de sauvetage est finalement adopté."),
        (d("2008-10-15"), "La récession s’installe. Wall Street replonge."),
        (d("2008-11-25"), "La Fed annonce des achats massifs de créances immobilières."),
        (d("2009-03-09"), "Les actions touchent un nouveau plus bas. Le pessimisme est total."),
        (d("2009-04-02"), "Le G20 annonce un soutien coordonné à l’économie."),
    ),
    arrets=(d("2008-09-15"), d("2008-09-29"), d("2009-03-09")),
    temoins=(Temoin("banques", d("2008-09-15"), -0.06), Temoin("banques", d("2008-09-29"), -0.10), Temoin("actions", d("2008-10-15"), -0.07)),
)

FILMS: dict[str, Film] = {f.id: f for f in (COVID, CRYPTO, CRISE_2008)}

DIFFICULTES = {
    "spectateur": {"nom": "Spectateur", "detail": "Film lent, conseils affichés", "ms": 850, "frais": 0.001, "conseils": True, "pause": True},
    "acteur": {"nom": "Acteur", "detail": "Rythme normal, pas de conseil", "ms": 480, "frais": 0.002, "conseils": False, "pause": True},
    "realisateur": {"nom": "Réalisateur", "detail": "Film rapide, frais élevés, sans pause", "ms": 280, "frais": 0.004, "conseils": False, "pause": False},
}
