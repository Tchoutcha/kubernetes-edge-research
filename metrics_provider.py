#!/usr/bin/env python3
"""
metrics_provider.py -- Source du signal "request rate", interchangeable.

la politique de bascule (policy.py) ne connaît que `get_rate() -> float|None`,
jamais comment ce chiffre a été obtenu. N'importe quel provider respectant
cette interface peut remplacer un autre sans toucher à la politique ni aux
actions cluster.

Providers disponibles :
  - ClientSideRateProvider :
      débit offert côté client, calculé à partir d'un fichier de timestamps.

  - KourierMetricsProvider :
      débit traité côté serveur, calculé depuis le compteur cumulatif Envoy
      exposé par la passerelle Kourier. Provider recommandé sur le cluster
      actuel.

  - KnativeMetricsProvider :
      squelette expérimental utilisant les métriques de l'activator.
      Non fonctionnel sur le cluster actuel.
"""

from abc import ABC, abstractmethod
import re
import subprocess
import urllib.request
import urllib.error


class MetricsProvider(ABC):
    """Interface : n'importe quelle source de débit doit l'implémenter."""

    @abstractmethod
    def get_rate(self, now: float) -> float | None:
        """Retourne le débit courant en req/s, ou None si indisponible
        (pas encore de données, source injoignable, etc.)."""
        raise NotImplementedError


class ClientSideRateProvider(MetricsProvider):
    """Débit OFFERT (côté client) : fenêtre glissante en NOMBRE D'ÉCHANTILLONS
    (pas en temps fixe) sur un fichier de timestamps (un `time.time()` par
    ligne) écrit en direct par le benchmark au moment de l'envoi de chaque
    requête.

    Pourquoi une fenêtre en nombre d'échantillons plutôt qu'en temps fixe :
    ça s'adapte naturellement à la charge sans réglage manuel. À fort débit,
    `sample_count` requêtes s'accumulent en quelques centaines de ms ->
    détection quasi instantanée, exactement quand c'est critique. À faible
    débit, la même fenêtre prend plus de temps à se remplir -> mais
    l'urgence de détection est aussi plus faible à ce régime. Une fenêtre
    en temps fixe n'a pas cette propriété : elle impose le même délai de
    détection à tous les régimes de charge, ce qui est trop lent à fort
    débit et inutilement bruité à faible débit.

    Limite assumée (pas un bug) : au tout début d'un run, avant que
    `sample_count` requêtes ne soient arrivées, aucune estimation n'est
    possible -- délai de chauffe incompressible pour toute détection live
    pure (sans connaissance a priori du workload).

    Limitation méthodologique documentée (cf. README) : mesure la charge
    injectée (côté client), pas nécessairement la charge réellement
    absorbée par le control plane sous saturation.
    """

    def __init__(self, log_path: str, sample_count: int = 20):
        if sample_count < 2:
            raise ValueError("sample_count doit être >= 2")
        self.log_path = log_path
        self.sample_count = sample_count

    def get_rate(self, now: float) -> float | None:
        timestamps = self._read_timestamps()
        return compute_count_window_rate(timestamps, self.sample_count)

    def _read_timestamps(self) -> list[float]:
        try:
            with open(self.log_path) as f:
                lines = f.readlines()
        except FileNotFoundError:
            return []
        out = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(float(line))
            except ValueError:
                continue
        return out


class KnativeMetricsProvider(MetricsProvider):
    """Débit TRAITÉ (côté serveur) : scrape direct de l'endpoint /metrics
    de l'activator Knative (format Prometheus, pas besoin d'un serveur
    Prometheus -- juste lire l'endpoint HTTP nous-mêmes).

    STATUT : squelette non fonctionnel. Prérequis avant utilisation :
      1. `metrics.backend-destination: prometheus` dans la configmap
         `config-observability` (namespace knative-serving)
      2. Redémarrage des pods activator/autoscaler pour prise en compte
      3. Confirmer que le port metrics (9090) écoute réellement -- au
         moment de l'écriture, connection refused malgré la configmap
         patchée : possible incompatibilité de version Knative
         (backend OpenTelemetry attendu au lieu de `prometheus` ?), à
         investiguer séparément, sans bloquer le reste du système.
    """

    def __init__(self, activator_pod_ip: str, metrics_port: int = 9090):
        self.activator_pod_ip = activator_pod_ip
        self.metrics_port = metrics_port

    def get_rate(self, now: float) -> float | None:
        raise NotImplementedError(
            "KnativeMetricsProvider pas encore fonctionnel sur ce cluster "
            "(voir docstring de la classe). Utiliser KourierMetricsProvider."
        )


class KourierMetricsProvider(MetricsProvider):
    """Débit TRAITÉ (côté passerelle d'entrée) : lit le compteur cumulatif
    Envoy `envoy_http_downstream_rq_total{envoy_http_conn_manager_prefix=
    "ingress_http"}` exposé nativement par Kourier sur le port 9000
    (/stats/prometheus), sans backend Prometheus à configurer.

    Le compteur est cumulatif depuis le démarrage du pod -- le débit est
    dérivé en gardant la dernière valeur lue et en calculant le delta par
    rapport à l'appel précédent. Gère explicitement :
      - le premier appel (pas de valeur précédente -> retourne None)
      - le redémarrage du pod Kourier (compteur remis à zéro, détecté par
        changement de nom de pod OU par une valeur qui diminue) -> traité
        comme un nouveau départ, pas comme un delta négatif absurde
      - la découverte dynamique du pod (peut changer de nœud, y compris
        via nos propres suppressions en mode apiserver)
      - l'accès réseau : les IPs de pods (10.42.x.x, réseau overlay K3s)
        ne sont routables que depuis l'intérieur du cluster, pas depuis
        une machine de contrôle externe. Utiliser `ssh_proxy=<alias SSH
        d'un nœud du cluster>` pour relayer la lecture via SSH.
    """

    METRIC_PATTERN = re.compile(
        r'envoy_http_downstream_rq_total\{envoy_http_conn_manager_prefix='
        r'"ingress_http"\}\s+(\d+)'
    )

    def __init__(self, namespace="kourier-system",
                 pod_prefix="3scale-kourier-gateway",
                 metrics_port=9000, timeout=3.0, ssh_proxy=None,
                 max_sample_interval: float = 5.0):
        """ssh_proxy : nom/alias SSH d'un nœud DU cluster (ex: 'worker1'),
        utilisé comme relais pour joindre l'IP interne du pod Kourier
        (réseau overlay 10.42.x.x, non routable depuis une machine externe
        comme la machine de contrôle). Si None, tente un accès réseau
        direct (ne fonctionne que si ce script tourne depuis une machine
        déjà sur le réseau du cluster).

        max_sample_interval : si l'écart entre deux lectures dépasse cette
        valeur (ex: Kourier injoignable pendant plusieurs cycles de poll),
        le delta est invalidé plutôt que moyenné sur toute la période
        écoulée -- un delta calculé sur 30s alors que le poll est censé
        être à 1s donnerait un débit moyen trompeur, pas le débit récent.
        """
        if timeout <= 0:
            raise ValueError("timeout doit être > 0")
        if max_sample_interval <= 0:
            raise ValueError("max_sample_interval doit être > 0")

        self.namespace = namespace
        self.pod_prefix = pod_prefix
        self.metrics_port = metrics_port
        self.timeout = timeout
        self.ssh_proxy = ssh_proxy
        self.max_sample_interval = max_sample_interval
        self._last_count: int | None = None
        self._last_time: float | None = None
        self._last_pod_name: str | None = None

    def get_rate(self, now: float) -> float | None:
        pod_name, pod_ip = self._discover_pod()
        if pod_ip is None:
            return None

        count = self._fetch_counter(pod_ip)
        if count is None:
            return None

        reset = (pod_name != self._last_pod_name) or \
                (self._last_count is not None and count < self._last_count)

        if self._last_count is None or reset:
            self._last_count = count
            self._last_time = now
            self._last_pod_name = pod_name
            return None  # pas de delta calculable ce coup-ci

        dt = now - self._last_time
        if dt <= 0 or dt > self.max_sample_interval:
            # écart trop long (source injoignable un moment) -- invalide le
            # delta plutôt que de moyenner sur toute la période écoulée
            self._last_count = count
            self._last_time = now
            self._last_pod_name = pod_name
            return None

        rate = (count - self._last_count) / dt

        self._last_count = count
        self._last_time = now
        self._last_pod_name = pod_name
        return rate

    def _discover_pod(self) -> tuple[str | None, str | None]:
        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", self.namespace,
                 "--field-selector=status.phase=Running",
                 "-o", ("custom-columns="
                        "NAME:.metadata.name,"
                        "IP:.status.podIP,"
                        "READY:.status.containerStatuses[0].ready"),
                 "--no-headers"],
                capture_output=True, text=True, check=True, timeout=self.timeout,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None, None
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if (len(parts) == 3 and parts[0].startswith(self.pod_prefix)
                    and parts[1] != "<none>" and parts[2].lower() == "true"):
                return parts[0], parts[1]
        return None, None

    def _fetch_counter(self, pod_ip: str) -> int | None:
        url = f"http://{pod_ip}:{self.metrics_port}/stats/prometheus"

        if self.ssh_proxy:
            try:
                result = subprocess.run(
                    ["ssh", self.ssh_proxy, f"curl -s --max-time {self.timeout} {url}"],
                    capture_output=True, text=True, timeout=self.timeout + 2,
                )
            except subprocess.TimeoutExpired:
                return None
            if result.returncode != 0:
                return None
            text = result.stdout
        else:
            try:
                with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                    text = resp.read().decode()
            except (urllib.error.URLError, OSError):
                return None

        match = self.METRIC_PATTERN.search(text)
        if not match:
            return None
        return int(match.group(1))


def compute_count_window_rate(timestamps: list[float], sample_count: int) -> float | None:
    """timestamps : liste de float (time.time()), triée par ordre
    chronologique croissant (comme écrite par le benchmark au fil de l'eau).

    Calcule le débit sur les `sample_count` dernières requêtes :
        rate = (sample_count - 1) / (timestamps[-1] - timestamps[-sample_count])

    Retourne None si moins de `sample_count` requêtes sont disponibles
    (délai de chauffe incompressible) ou si les timestamps sont identiques
    (division par zéro évitée).
    """
    if sample_count < 2:
        raise ValueError("sample_count doit être >= 2")
    if len(timestamps) < sample_count:
        return None
    window = timestamps[-sample_count:]
    duration = window[-1] - window[0]
    if duration <= 0:
        return None
    return (sample_count - 1) / duration
