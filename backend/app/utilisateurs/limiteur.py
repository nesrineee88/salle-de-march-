"""Limiteur de débit en mémoire (fenêtre glissante). Suffisant pour un seul processus ;
avec plusieurs processus, il faudra un stockage partagé (Redis)."""
from __future__ import annotations

import time
from collections import defaultdict, deque


class LimiteurFenetre:
    def __init__(self, maximum: int, fenetre_s: float, horloge=time.monotonic):
        self._max, self._fenetre, self._horloge = maximum, fenetre_s, horloge
        self._appels: dict[str, deque] = defaultdict(deque)

    def autoriser(self, cle: str) -> bool:
        maintenant = self._horloge()
        file = self._appels[cle]
        while file and maintenant - file[0] > self._fenetre:
            file.popleft()
        if len(file) >= self._max:
            return False
        file.append(maintenant)
        return True
