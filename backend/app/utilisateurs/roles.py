"""Rôles et permissions (RBAC). Une permission est vérifiée côté serveur à chaque requête."""
APPRENANT, TRADER, FORMATEUR, ADMIN = "apprenant", "trader", "formateur", "admin"
ROLES = (APPRENANT, TRADER, FORMATEUR, ADMIN)

TOUS = frozenset(ROLES)
PERMISSIONS: dict[str, frozenset[str]] = {
    "marche.lire": TOUS,
    "trading.passer_ordre": TOUS,                   # le bac à sable de trading est ouvert à tous
    "trading.levier": frozenset({TRADER, ADMIN}),   # réservé aux modules avancés (Sprint 3)
    "ia.utiliser": frozenset({TRADER, FORMATEUR, ADMIN}),
    "formation.suivre": TOUS,
    "formation.gerer": frozenset({FORMATEUR, ADMIN}),
    "classe.voir": frozenset({FORMATEUR, ADMIN}),
    "admin.utilisateurs": frozenset({ADMIN}),
    "admin.audit": frozenset({ADMIN}),
    "admin.crises": frozenset({ADMIN}),
    "admin.ia": frozenset({ADMIN}),
}


def a_permission(role: str, permission: str) -> bool:
    return role in PERMISSIONS.get(permission, frozenset())
