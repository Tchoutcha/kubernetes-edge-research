#!/usr/bin/env python3
"""

## Usage

### Normal usage

With no arguments, the controller loads the configuration, automatically
detects what it can, and runs indefinitely as an adaptive daemon:

```bash
python3 controller.py
```

### Configuration resolution

Configuration is resolved in the following order (first match wins):

1. `--config` explicitly provided
2. `ACPC_CONFIG` environment variable
3. `./config.yaml`
4. `/etc/adaptive-controller/config.yaml`
5. Safe built-in defaults (if no configuration file is found)

See `config.example.yaml` for the complete configuration schema and
`ALGORITHM.md` for an overview of the decision policy.

### Options

| Option             | Description                                                                                                             |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `--config PATH`    | Explicit path to the configuration file                                                                                 |
| `--dry-run`        | Print actions without executing them. Forces dry-run mode even if `config.yaml` sets it to `false`                      |
| `--once`           | Run a single measurement/decision iteration and exit instead of running indefinitely                                    |
| `--check-config`   | Resolve the configuration and perform auto-detection, print the result, and exit without executing any cluster action   |
| `--switch-to MODE` | Perform a one-shot manual switch (`local1core` or `apiserver`). Secondary testing utility; not part of normal operation |

"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from policy import Mode, PolicyConfig
from cluster_actions import (
    ClusterConfig, apply_mode, resolve_master_node, detect_current_mode,
)
from metrics_provider import KourierMetricsProvider, ClientSideRateProvider


DEFAULT_CONFIG_LOCATIONS = ["./config.yaml", "/etc/adaptive-controller/config.yaml"]

SAFE_DEFAULTS = {
    "controller": {"poll_interval_seconds": 1, "initial_mode": "auto", "dry_run": False},
    "policy": {"low_threshold_rps": 20, "high_threshold_rps": 50,
               "required_high_samples": 3, "required_low_samples": 100,
               "cooldown_seconds": 60},
    "metrics": {"provider": "kourier", "namespace": "kourier-system",
                "pod_prefix": "3scale-kourier-gateway", "port": 9000,
                "timeout_seconds": 3},
    "cluster": {}, "components": {},
    "logging": {"format": "csv", "path": "transitions.csv"},
}


def resolve_config_path(explicit_path):
    """Cascade de résolution : --config > $ACPC_CONFIG > ./config.yaml >
    /etc/adaptive-controller/config.yaml > None (défauts sûrs)."""
    if explicit_path:
        if not Path(explicit_path).exists():
            sys.exit(f"--config '{explicit_path}' introuvable")
        return explicit_path

    env_path = os.environ.get("ACPC_CONFIG")
    if env_path:
        if not Path(env_path).exists():
            sys.exit(f"ACPC_CONFIG='{env_path}' introuvable")
        return env_path

    for candidate in DEFAULT_CONFIG_LOCATIONS:
        if Path(candidate).exists():
            return candidate

    return None  # aucun fichier trouvé -> défauts sûrs


def load_raw_config(path):
    if path is None:
        print("Aucun config.yaml trouvé -- utilisation des valeurs par "
              "défaut sûres (voir SAFE_DEFAULTS dans controller.py). "
              "Recommandé : copier config.example.yaml -> config.yaml.")
        return SAFE_DEFAULTS
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    print(f"Config chargée depuis : {path}")
    return data


def build_policy_config(data: dict, cli_overrides: dict) -> PolicyConfig:
    section = data.get("policy", {}) or {}
    merged = {**SAFE_DEFAULTS["policy"], **section}
    for k, v in cli_overrides.items():
        if v is not None:
            merged[k] = v
    return PolicyConfig(
        high_threshold=merged["high_threshold_rps"],
        low_threshold=merged["low_threshold_rps"],
        cooldown_s=merged["cooldown_seconds"],
        required_high_samples=merged["required_high_samples"],
        required_low_samples=merged["required_low_samples"],
    )


class TransitionLogger:
    """Log structuré (CSV ou JSONL selon logging.format) : une ligne/objet
    par évènement, exploitable directement en pandas pour croiser avec les
    mesures énergie/latence (Antela)."""

    FIELDS = ["epoch", "iso_time", "event", "from_mode", "to_mode", "rate"]

    def __init__(self, path: str, fmt: str = "csv"):
        self.fmt = fmt
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        is_new = not Path(path).exists()
        self._file = open(path, "a", newline="" if fmt == "csv" else None)
        if fmt == "csv":
            self._writer = csv.DictWriter(self._file, fieldnames=self.FIELDS)
            if is_new:
                self._writer.writeheader()
                self._file.flush()

    def log(self, event: str, from_mode="", to_mode="", rate=""):
        from_mode_s = from_mode if isinstance(from_mode, str) else from_mode.value
        to_mode_s = to_mode if isinstance(to_mode, str) else to_mode.value
        row = {
            "epoch": f"{time.time():.6f}",
            "iso_time": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "from_mode": from_mode_s,
            "to_mode": to_mode_s,
            "rate": rate,
        }
        if self.fmt == "jsonl":
            self._file.write(json.dumps(row) + "\n")
        else:
            self._writer.writerow(row)
        self._file.flush()
        print(f"[{row['iso_time']}] {event} from={from_mode_s} "
              f"to={to_mode_s} rate={rate}")

    def close(self):
        self._file.close()


def build_metrics_provider(data: dict, cfg: ClusterConfig, dry_run: bool):
    section = data.get("metrics", {}) or {}
    provider_name = section.get("provider", "kourier")

    if provider_name == "kourier":
        # Trois états distincts pour metrics.ssh_proxy, à ne pas confondre :
        #   - clé absente, ou valeur "auto"  -> auto-résolution (alias SSH
        #     du master), utile depuis une machine EXTERNE au cluster
        #   - valeur explicite "null"/omise avec `~` en YAML -> ACCÈS DIRECT,
        #     aucun relais SSH -- pertinent quand le contrôleur tourne
        #     DEPUIS un nœud du cluster (réseau overlay déjà joignable)
        #   - une chaîne -- alias SSH explicite, utilisé tel quel
        # `section.get("ssh_proxy")` seul ne peut PAS distinguer "clé
        # absente" de "valeur null explicite" (les deux valent None en
        # Python) -- d'où le test `"ssh_proxy" in section` explicite.
        key_present = "ssh_proxy" in section
        ssh_proxy_config = section.get("ssh_proxy")

        if not key_present or ssh_proxy_config == "auto":
            ssh_proxy = cfg.ssh_target(cfg.master_node)
            print(f"  metrics.ssh_proxy non renseigné/'auto' -> auto : "
                  f"'{ssh_proxy}' (alias du master)")
        elif ssh_proxy_config is None:
            ssh_proxy = None
            print("  metrics.ssh_proxy: null -> accès réseau direct "
                  "(aucun relais SSH)")
        else:
            ssh_proxy = ssh_proxy_config

        return KourierMetricsProvider(
            namespace=section.get("namespace", cfg.kourier_namespace),
            pod_prefix=section.get("pod_prefix", cfg.kourier_prefix),
            metrics_port=section.get("port", 9000),
            timeout=section.get("timeout_seconds", 3),
            ssh_proxy=ssh_proxy,
            max_sample_interval=section.get("max_sample_interval_seconds", 5.0),
        )
    elif provider_name == "client":
        return ClientSideRateProvider(
            log_path=section.get("request_log", "request_log.txt"),
            sample_count=section.get("sample_count", 20),
        )
    else:
        sys.exit(f"metrics.provider inconnu : '{provider_name}'")


def next_poll_interval(rate: float | None, pending_count: int,
                        base_interval: float, max_interval: float,
                        requests_per_poll: float) -> float:
    """Calcule le prochain intervalle de polling, proportionnel au débit
    RÉELLEMENT OBSERVÉ -- pas un calendrier de backoff fixe qu'il faudrait
    régler à la main pour chaque régime de charge.

    - pending_count > 0 -> retour immédiat au rythme de base
    - rate is None -> rythme de base (chauffe)
    - rate <= 0 -> rythme le plus lent (max_interval)
    - rate > 0 -> interval proportionnel, borné entre base_interval et max_interval
    """
    if pending_count > 0:
        return base_interval
    if rate is None:
        return base_interval
    if rate <= 0:
        return max_interval
    desired = requests_per_poll / rate
    return max(base_interval, min(desired, max_interval))


def run_iterations(policy_cfg: PolicyConfig, cluster_cfg: ClusterConfig,
                    provider, logger, current_mode: Mode,
                    poll_interval: float, dry_run: bool, once: bool,
                    poll_interval_max: float = None,
                    poll_requests_per_poll: float = 3.0):
    policy = policy_cfg.build_policy()
    poll_interval_max = poll_interval_max or poll_interval
    current_interval = poll_interval

    logger.log("CONTROLLER_START", to_mode=current_mode)

    # Applique explicitement le mode initial avant d'entrer dans la boucle
    # -- sans ça, un état déjà cohérent côté taint ne garantit rien sur le
    # pinning du scheduler, qui ne persiste pas tout seul (process OS).
    logger.log("INITIAL_APPLY_START", to_mode=current_mode)
    apply_mode(cluster_cfg, current_mode, dry_run)
    logger.log("INITIAL_APPLY_END", to_mode=current_mode)

    try:
        while True:
            # monotonic, pas time.time() : le cooldown et le delta de débit
            # dépendent uniquement du temps écoulé, jamais de l'heure
            # système -- un ajustement NTP ou un changement d'heure ne doit
            # jamais fausser ces calculs. Seul le logger garde time.time()
            # (timestamps lisibles/comparables entre machines).
            now = time.monotonic()
            rate = provider.get_rate(now)

            from_mode = current_mode
            want = policy.decide(current_mode, rate, now)
            if want is not None:
                rate_s = f"{rate:.2f}" if rate is not None else ""
                logger.log("TRANSITION_START", from_mode=from_mode,
                            to_mode=want, rate=rate_s)
                apply_mode(cluster_cfg, want, dry_run)
                policy.record_switch(now)
                current_mode = want
                logger.log("TRANSITION_END", from_mode=from_mode,
                            to_mode=current_mode, rate=rate_s)

            current_interval = next_poll_interval(
                rate, policy.pending_count, poll_interval,
                poll_interval_max, poll_requests_per_poll)

            if once:
                break
            time.sleep(current_interval)
    except KeyboardInterrupt:
        logger.log("CONTROLLER_STOP", to_mode=current_mode)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None,
                     help="chemin explicite vers config.yaml (sinon cascade "
                          "$ACPC_CONFIG / ./config.yaml / /etc/... )")
    ap.add_argument("--dry-run", action="store_true",
                     help="affiche les actions sans les exécuter")
    ap.add_argument("--once", action="store_true",
                     help="une seule itération mesure/décision puis quitte")
    ap.add_argument("--check-config", action="store_true",
                     help="résout config + auto-détection, affiche, quitte "
                          "sans rien exécuter sur le cluster")
    ap.add_argument("--switch-to", choices=["local1core", "apiserver"],
                     default=None,
                     help="[secondaire, tests] bascule manuelle ponctuelle, "
                          "puis quitte -- n'est pas l'usage normal")

    # overrides ponctuels, optionnels -- la source de vérité reste config.yaml
    ap.add_argument("--high-threshold", type=float, default=None)
    ap.add_argument("--low-threshold", type=float, default=None)
    ap.add_argument("--cooldown", type=float, default=None)
    ap.add_argument("--required-high-samples", type=int, default=None)
    ap.add_argument("--required-low-samples", type=int, default=None)

    args = ap.parse_args()

    config_path = resolve_config_path(args.config)
    data = load_raw_config(config_path)

    cluster_cfg = ClusterConfig.from_config_dict(data)
    try:
        cluster_cfg.master_node = resolve_master_node(cluster_cfg)
    except RuntimeError as e:
        sys.exit(str(e))
    print(f"Master node résolu : {cluster_cfg.master_node}")

    cli_overrides = {
        "high_threshold_rps": args.high_threshold,
        "low_threshold_rps": args.low_threshold,
        "cooldown_seconds": args.cooldown,
        "required_high_samples": args.required_high_samples,
        "required_low_samples": args.required_low_samples,
    }
    policy_cfg = build_policy_config(data, cli_overrides)

    controller_section = data.get("controller", {}) or {}
    poll_interval = controller_section.get("poll_interval_seconds", 1.0)
    poll_interval_max = controller_section.get("poll_interval_max_seconds", 30.0)
    poll_requests_per_poll = controller_section.get("poll_requests_per_poll", 3.0)
    dry_run = args.dry_run or controller_section.get("dry_run", False)

    logging_section = data.get("logging", {}) or {}
    log_fmt = logging_section.get("format", "csv")
    log_path = logging_section.get("path",
                                    "transitions.csv" if log_fmt == "csv" else "transitions.jsonl")

    if args.check_config:
        print("\n--- Résolution de config ---")
        print(f"cluster_cfg  : {cluster_cfg}")
        print(f"policy_cfg   : {policy_cfg}")
        print(f"poll_interval: {poll_interval}s, dry_run={dry_run}")
        print(f"logging      : format={log_fmt}, path={log_path}")
        try:
            detected = detect_current_mode(cluster_cfg.master_node)
            print(f"Mode actuellement détecté sur le cluster : {detected.value}")
        except Exception as e:
            print(f"Auto-détection du mode courant impossible : {e}")
        return

    logger = TransitionLogger(log_path, fmt=log_fmt)

    try:
        if args.switch_to:
            mode = Mode(args.switch_to)
            logger.log("MANUAL_SWITCH_START", to_mode=mode)
            apply_mode(cluster_cfg, mode, dry_run)
            logger.log("MANUAL_SWITCH_END", to_mode=mode)
            return

        initial_mode_setting = controller_section.get("initial_mode", "auto")
        if initial_mode_setting == "auto":
            current_mode = detect_current_mode(cluster_cfg.master_node)
            print(f"initial_mode: auto -> détecté {current_mode.value}")
        else:
            current_mode = Mode(initial_mode_setting)

        provider = build_metrics_provider(data, cluster_cfg, dry_run)

        run_iterations(policy_cfg, cluster_cfg, provider, logger,
                        current_mode, poll_interval, dry_run, args.once,
                        poll_interval_max=poll_interval_max,
                        poll_requests_per_poll=poll_requests_per_poll)
    finally:
        logger.close()


if __name__ == "__main__":
    main()
