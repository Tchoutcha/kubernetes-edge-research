#!/usr/bin/env python3
"""
policy.py -- Decision Policy : la logique de bascule, pure et testable.

 quand faut-il basculer entre local1core et apiserver, selon quel signal de débit. Ce module ne dépend
d'aucun cluster réel, d'aucun MetricsProvider concret -- il ne connaît que
des nombres (débit, temps) en entrée. Testable intégralement en isolation
(voir test_policy.py).

À NE PAS mélanger avec :
  - metrics_provider.py : COMMENT on obtient le débit (détail d'implémentation)
  - cluster_actions.py  : COMMENT on applique une bascule sur le cluster réel
"""

from dataclasses import dataclass
from enum import Enum


class Mode(Enum):
    LOCAL1CORE = "local1core"
    APISERVER = "apiserver"


@dataclass
class PolicyConfig:
    """Paramètres génériques de la politique de décision -- HighThreshold,
    LowThreshold, Cooldown, RequiredHighSamples, RequiredLowSamples dans
    Algorithm 1 (voir ALGORITHM.md). Aucune constante codée en dur : ces
    valeurs viennent de la section `policy:` de config.yaml, construites
    par controller.py (ce module reste volontairement sans I/O, cf.
    docstring de fichier).

    RequiredHighSamples et RequiredLowSamples sont volontairement
    DISTINCTS (pas un seul required_samples symétrique) : monter vers
    apiserver protège le control plane d'une surcharge (confirmation
    rapide, quitte à un faux positif occasionnel), alors que redescendre
    vers local1core doit être plus prudent (une désescalade prématurée
    suivie d'un re-pic force une bascule coûteuse évitable) -- même
    principe que les fenêtres de stabilisation scale-up/scale-down
    asymétriques d'un autoscaler Kubernetes standard.
    """
    high_threshold: float
    low_threshold: float
    cooldown_s: float = 15.0
    required_high_samples: int = 3
    required_low_samples: int = 6

    def __post_init__(self):
        if self.low_threshold >= self.high_threshold:
            raise ValueError("low_threshold doit être strictement < high_threshold")
        if self.required_high_samples < 1 or self.required_low_samples < 1:
            raise ValueError("required_high_samples et required_low_samples "
                              "doivent être >= 1")
        if self.cooldown_s < 0:
            raise ValueError("cooldown_s doit être >= 0")

    def build_policy(self) -> "HysteresisPolicy":
        return HysteresisPolicy(low=self.low_threshold, high=self.high_threshold,
                                 cooldown_s=self.cooldown_s,
                                 required_high_samples=self.required_high_samples,
                                 required_low_samples=self.required_low_samples)


class HysteresisPolicy:
    """Politique de bascule à deux seuils, avec bande morte, confirmation
    par échantillons répétés (asymétrique selon la direction), et cooldown.

    - rate >= high, actuellement local1core -> candidat pour apiserver,
      confirmé après `required_high_samples` lectures consécutives
    - rate <= low,  actuellement apiserver  -> candidat pour local1core,
      confirmé après `required_low_samples` lectures consécutives
    - entre low et high : aucune action (bande morte, évite le flapping
      sur un débit qui oscille autour d'un seuil unique)
    - la confirmation par échantillons protège contre une bascule
      déclenchée par une seule lecture bruitée -- indépendant du cooldown,
      qui protège contre le flapping APRÈS une bascule déjà effectuée
    - même confirmé, aucune nouvelle bascule n'est autorisée avant
      `cooldown_s` secondes après la précédente
    - rate=None (pas encore de signal exploitable, ex: délai de chauffe
      d'un MetricsProvider) -> aucune décision, réinitialise le compteur
      de confirmation, jamais de bascule à l'aveugle
    """

    def __init__(self, low: float, high: float, cooldown_s: float,
                 required_high_samples: int = 3, required_low_samples: int = 6):
        if low >= high:
            raise ValueError("low doit être strictement < high (bande d'hystérésis)")
        if required_high_samples < 1 or required_low_samples < 1:
            raise ValueError("required_high_samples et required_low_samples "
                              "doivent être >= 1")
        if cooldown_s < 0:
            raise ValueError("cooldown_s doit être >= 0")
        self.low = low
        self.high = high
        self.cooldown_s = cooldown_s
        self.required_high_samples = required_high_samples
        self.required_low_samples = required_low_samples
        self._last_switch_time = None
        self._pending_direction = None
        self._pending_count = 0

    def _required_for(self, candidate: Mode) -> int:
        return (self.required_high_samples if candidate == Mode.APISERVER
                else self.required_low_samples)

    def decide(self, current_mode: Mode, rate: float | None, now: float) -> Mode | None:
        """Retourne le nouveau Mode si une bascule est justifiée maintenant,
        sinon None (rester dans le mode courant)."""
        if rate is None:
            self._pending_direction = None
            self._pending_count = 0
            return None

        candidate = None
        if current_mode == Mode.LOCAL1CORE and rate >= self.high:
            candidate = Mode.APISERVER
        elif current_mode == Mode.APISERVER and rate <= self.low:
            candidate = Mode.LOCAL1CORE

        if candidate is None:
            self._pending_direction = None
            self._pending_count = 0
            return None

        required = self._required_for(candidate)

        if candidate == self._pending_direction:
            self._pending_count = min(self._pending_count + 1, required)
        else:
            self._pending_direction = candidate
            self._pending_count = 1

        if self._pending_count < required:
            return None  # pas encore confirmé par assez d'échantillons consécutifs

        if self._last_switch_time is not None and \
                (now - self._last_switch_time) < self.cooldown_s:
            return None

        return candidate

    def record_switch(self, now: float):
        """À appeler par l'orchestrateur après avoir effectivement appliqué
        une bascule décidée par `decide()`, pour armer le cooldown et
        réinitialiser la confirmation par échantillons."""
        self._last_switch_time = now
        self._pending_direction = None
        self._pending_count = 0

    @property
    def pending_count(self) -> int:
        """Nombre de lectures consécutives allant dans le même sens,
        pas encore confirmées. Lecture seule, pour observabilité externe
        (ex: ralentir le polling quand rien ne bouge) -- ne fait pas
        partie de la logique de décision elle-même."""
        return self._pending_count
