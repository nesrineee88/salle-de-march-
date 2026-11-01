"""Repères historiques de 2018 à 2025 et modèles de crises. Aucun repère pour 2026 : les connaissances de l'assistant s'arrêtent avant.

Les repères sont des **faits connus rédigés par l'assistant, de mémoire** : la date retenue est le jour de parution, le plus souvent
le lendemain de l'événement (pour ne pas annoncer à l'avance ce que le marché a fait pendant la journée). Ils doivent être
vérifiés avant une présentation ; les chiffres ont été évités autant que possible."""
from __future__ import annotations

NOTE_HISTORIQUE = "Repère historique rédigé par l'assistant de mémoire : à vérifier avant présentation (date = jour de parution)."

# (date de parution, titre, texte, symboles concernés ; vide = marché général)
REPERES: list[tuple[str, str, str, list[str]]] = [
    ("2018-02-06", "Brusque flambée de la volatilité à Wall Street",
     "Les actions américaines ont connu la veille une forte baisse et l'indice de volatilité VIX a bondi, mettant fin à une période d'accalmie exceptionnelle.", ["^GSPC"]),
    ("2018-12-20", "La Fed relève ses taux pour la quatrième fois de l'année",
     "La banque centrale américaine a relevé ses taux directeurs la veille. Les investisseurs craignent un ralentissement de la croissance.", ["^GSPC"]),
    ("2019-08-06", "Tensions commerciales : la Chine laisse sa monnaie se déprécier",
     "Les tensions entre Washington et Pékin s'aggravent. Les marchés actions ont reculé la veille.", ["^GSPC"]),
    ("2020-03-10", "Guerre des prix du pétrole entre l'Arabie saoudite et la Russie",
     "Faute d'accord au sein de l'OPEP+, l'Arabie saoudite a baissé ses prix. Le pétrole a chuté d'environ un quart la veille (ordre de grandeur de mémoire, à vérifier).", ["CL=F", "BZ=F", "XOM", "CVX"]),
    ("2020-03-12", "L'OMS qualifie l'épidémie de Covid-19 de pandémie",
     "L'Organisation mondiale de la santé a déclaré la veille que l'épidémie est une pandémie. Les craintes d'un arrêt de l'économie mondiale pèsent sur les marchés.", []),
    ("2020-03-16", "La Fed ramène ses taux à zéro et relance ses achats d'actifs",
     "Dimanche soir, la banque centrale américaine a baissé ses taux à presque zéro et annoncé de nouveaux achats d'actifs pour calmer les marchés.", ["^GSPC"]),
    ("2020-04-21", "Le prix du pétrole américain passe sous zéro",
     "Le contrat à terme du WTI pour mai a fini la veille en territoire négatif : faute de place de stockage, les vendeurs payaient pour s'en défaire.", ["CL=F"]),
    ("2020-11-10", "Un laboratoire annonce un vaccin très efficace contre le Covid-19",
     "Pfizer et BioNTech ont annoncé la veille des résultats préliminaires très encourageants. L'espoir d'une reprise économique soutient les marchés.", ["PFE", "^GSPC"]),
    ("2021-11-11", "Le Bitcoin atteint un record historique",
     "Le Bitcoin a touché la veille un nouveau sommet, autour de 69 000 dollars (de mémoire, à vérifier).", ["BTC-USD", "ETH-USD"]),
    ("2022-02-24", "La Russie envahit l'Ukraine",
     "L'armée russe a lancé une offensive en Ukraine. Les craintes de guerre et de sanctions font grimper les matières premières et inquiètent les marchés.", ["CL=F", "BZ=F", "NG=F", "GC=F", "ZW=F"]),
    ("2022-03-09", "Les États-Unis interdisent les importations de pétrole russe",
     "Le président américain a annoncé la veille l'interdiction des importations de pétrole russe, ce qui accroît la tension sur l'énergie.", ["CL=F", "BZ=F", "XOM", "CVX"]),
    ("2022-03-17", "Première hausse des taux de la Fed depuis 2018",
     "La banque centrale américaine a relevé la veille ses taux directeurs pour lutter contre l'inflation.", ["^GSPC"]),
    ("2022-05-13", "Effondrement de l'écosystème Terra (UST et LUNA)",
     "Le stablecoin UST a décroché de son cours de un dollar cette semaine et la cryptomonnaie LUNA s'est effondrée, entraînant tout le marché des cryptomonnaies.", ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD"]),
    ("2022-06-16", "La Fed relève ses taux de trois quarts de point",
     "La banque centrale américaine a opéré la veille sa plus forte hausse de taux depuis près de trente ans (de mémoire, à vérifier).", ["^GSPC"]),
    ("2022-11-14", "La plateforme FTX fait faillite",
     "La plateforme d'échange de cryptomonnaies FTX s'est placée sous la protection de la loi sur les faillites vendredi. La confiance dans le secteur s'effondre.", ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"]),
    ("2023-03-13", "Faillite de la Silicon Valley Bank",
     "Les autorités américaines ont repris vendredi le contrôle de la Silicon Valley Bank. Les craintes de contagion pèsent sur les banques.", ["JPM", "BAC", "GS", "^GSPC"]),
    ("2023-12-14", "La Fed laisse entrevoir des baisses de taux en 2024",
     "Après sa réunion, la banque centrale américaine a indiqué que des baisses de taux étaient envisagées pour 2024. Les marchés progressent.", ["^GSPC"]),
    ("2024-01-11", "Les premiers fonds cotés sur le Bitcoin au comptant sont approuvés aux États-Unis",
     "Le régulateur américain a donné son feu vert la veille aux fonds cotés qui détiennent directement du Bitcoin.", ["BTC-USD", "ETH-USD"]),
    ("2024-09-19", "La Fed baisse ses taux pour la première fois depuis 2020",
     "La banque centrale américaine a abaissé la veille ses taux directeurs, une baisse d'un demi-point.", ["^GSPC"]),
    ("2024-12-06", "Le Bitcoin dépasse les 100 000 dollars",
     "Le Bitcoin a franchi la veille pour la première fois la barre symbolique des 100 000 dollars.", ["BTC-USD", "ETH-USD"]),
    ("2025-01-28", "Un modèle d'IA chinois bon marché secoue le secteur technologique",
     "L'annonce du modèle DeepSeek a fait chuter la veille les valeurs liées à l'intelligence artificielle, NVIDIA en tête.", ["NVDA", "MSFT", "^GSPC"]),
    ("2025-04-03", "Annonce de nouveaux droits de douane américains",
     "Le président américain a annoncé la veille des droits de douane étendus sur les importations. Les craintes d'un ralentissement mondial montent.", ["^GSPC"]),
    ("2025-04-10", "Les États-Unis suspendent une partie des nouveaux droits de douane",
     "Les droits de douane réciproques annoncés la semaine précédente sont suspendus pour 90 jours (sauf pour la Chine). Les marchés rebondissent fortement.", ["^GSPC"]),
]

# Modèles de scénarios proposés à l'administrateur (valeurs pédagogiques ; il peut tout modifier avant de valider).
MODELES: list[dict] = [
    {"cle": "krach_actions", "nom": "Krach des actions", "description": "Chute brutale des actions, suivie d'un rebond partiel.",
     "portee_type": "classe", "portee_valeurs": ["action"], "choc_pct": -30, "recuperation_pct": 60, "duree_recuperation_jours": 180,
     "annonce": "Panique sur les marchés actions : les indices chutent fortement dès l'ouverture."},
    {"cle": "choc_petrolier", "nom": "Choc pétrolier", "description": "Effondrement du secteur de l'énergie (pétrole, gaz et producteurs).",
     "portee_type": "secteur", "portee_valeurs": ["Énergie"], "choc_pct": -40, "recuperation_pct": 50, "duree_recuperation_jours": 120,
     "annonce": "Le pétrole s'effondre : les producteurs d'énergie sont durement touchés."},
    {"cle": "hiver_crypto", "nom": "Hiver des cryptomonnaies", "description": "Chute des cryptomonnaies, sans rebond.",
     "portee_type": "classe", "portee_valeurs": ["crypto"], "choc_pct": -50, "recuperation_pct": 0, "duree_recuperation_jours": 0,
     "annonce": "Les cryptomonnaies s'effondrent, la confiance du secteur est ébranlée."},
    {"cle": "envolee_or", "nom": "Ruée vers l'or", "description": "Les métaux précieux flambent en période d'incertitude.",
     "portee_type": "secteur", "portee_valeurs": ["Métaux précieux"], "choc_pct": 15, "recuperation_pct": 40, "duree_recuperation_jours": 90,
     "annonce": "Les investisseurs se réfugient dans l'or et les métaux précieux."},
    {"cle": "rallye", "nom": "Rallye généralisé", "description": "Hausse brutale de tous les marchés (annonce de soutien massif).",
     "portee_type": "tous", "portee_valeurs": [], "choc_pct": 15, "recuperation_pct": 0, "duree_recuperation_jours": 0,
     "annonce": "Annonce de mesures de soutien exceptionnelles : tous les marchés bondissent."},
    {"cle": "secheresse", "nom": "Sécheresse", "description": "Flambée des cours agricoles.",
     "portee_type": "secteur", "portee_valeurs": ["Agricole"], "choc_pct": 25, "recuperation_pct": 60, "duree_recuperation_jours": 150,
     "annonce": "Une sécheresse sévère menace les récoltes : les cours agricoles s'envolent."},
]
