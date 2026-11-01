"""Rapport de qualité lisible (JSON + Markdown) à joindre au rapport du projet."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .nettoyer import RapportActif


def ecrire_rapports(rapports: list[RapportActif], dossier: Path) -> tuple[Path, Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
    chemin_json = dossier / "RAPPORT_QUALITE.json"
    chemin_json.write_text(
        json.dumps(
            {"genere_le": horodatage, "actifs": [r.en_dict() for r in rapports]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lignes = [
        "# Rapport de qualité des données",
        "",
        f"Généré le {horodatage} (UTC).",
        "",
        "| Actif | Lignes | Début | Fin | Doublons | Corrigées | Prix ≤ 0 supprimés | Prix < 0 gardés | Trous longs | Mouvements > 50 % |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rapports:
        lignes.append(
            f"| {r.symbole} | {r.lignes_propres} | {r.premiere_date or '-'} | {r.derniere_date or '-'} "
            f"| {r.doublons_supprimes} | {r.barres_corrigees} | {r.prix_non_positifs_supprimes} "
            f"| {r.prix_negatifs_conserves} | {len(r.trous_longs)} | {len(r.mouvements_suspects)} |"
        )
    corrigees = [r for r in rapports if r.barres_corrigees]
    if corrigees:
        lignes += [
            "", "## Bougies corrigées", "",
            "Une bougie est corrigée quand son plus haut est sous l'une de ses valeurs (ouverture, clôture, plus bas) ou son plus bas "
            "au-dessus : on aligne alors le plus haut et le plus bas sur les valeurs de la bougie. Ouverture et clôture ne sont jamais "
            "modifiées. La colonne « corrige » des fichiers propres marque chaque bougie concernée ; le brut reste intact.", "",
            "| Actif | Bougies corrigées | Part des lignes | Plus grand écart sur un plus haut ou un plus bas |",
            "|---|---:|---:|---:|",
        ]
        for r in corrigees:
            part = 100 * r.barres_corrigees / r.lignes_propres if r.lignes_propres else 0.0
            lignes.append(f"| {r.symbole} | {r.barres_corrigees} | {part:.1f} % | {r.correction_max_pct:.2f} % |")
    suspects = [(r.symbole, m) for r in rapports for m in r.mouvements_suspects]
    if suspects:
        lignes += [
            "", "## Mouvements de plus de 50 % en une séance", "",
            "Signalés, jamais supprimés : beaucoup sont réels (krach du pétrole, envolées des cryptomonnaies). À contrôler sur une source indépendante.", "",
            "| Actif | Date | Variation de la clôture |", "|---|---|---:|",
        ]
        lignes += [f"| {s} | {m['date']} | {m['variation'] * 100:+.1f} % |" for s, m in suspects]
    avertissements = [(r.symbole, a) for r in rapports for a in r.avertissements]
    if avertissements:
        lignes += ["", "## Avertissements", ""]
        lignes += [f"- **{s}** : {a}" for s, a in avertissements]
    chemin_md = dossier / "RAPPORT_QUALITE.md"
    chemin_md.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return chemin_json, chemin_md
