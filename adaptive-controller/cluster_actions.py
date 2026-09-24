#!/usr/bin/env python3
"""
cluster_actions.py -- Cluster Actions : COMMENT une bascule de mode est
appliquée physiquement sur le cluster K3s/Knative réel.

C'est un DÉTAIL D'IMPLÉMENTATION, pas une décision scientifique (cf.
policy.py). Aucune connaissance du "pourquoi" ou du "quand" basculer ici --
uniquement le "comment", étant donné un Mode déjà décidé.

Toute la configuration spécifique au cluster (noms de nœuds, alias SSH,
namespaces, préfixes de pods) est externalisée dans un fichier YAML
(cluster.yaml, cf. config.example.yaml) plutôt que codée en dur -- pour
qu'un reviewer avec un cluster différent puisse réutiliser ce code en
changeant uniquement sa config.
"""

import subprocess
import time
import yaml
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from policy import Mode


@dataclass
class ClusterConfig:
    master_node: str = "auto"
    master_label_selector: str = "node-role.kubernetes.io/control-plane"
    ssh_aliases: dict = field(default_factory=dict)
    scheduler_namespace: str = "kube-system"
    scheduler_prefix: str = "my-scheduler"
    scheduler_proc: str = "/usr/local/bin/kube-scheduler"
    dedicated_core: str = "1"
    knative_namespace: str = "knative-serving"
    activator_prefix: str = "activator"
    autoscaler_prefix: str = "autoscaler"
    kourier_namespace: str = "kourier-system"
    kourier_prefix: str = "3scale-kourier-gateway"

    @classmethod
    def from_config_dict(cls, data: dict) -> "ClusterConfig":
        """Construit à partir des sections `cluster:` et `components:` d'un
        YAML déjà parsé (nesting explicite plutôt que filtrage générique,
        car la structure YAML est imbriquée différemment du dataclass)."""
        cluster = data.get("cluster", {}) or {}
        components = data.get("components", {}) or {}
        activator = components.get("activator", {}) or {}
        autoscaler = components.get("autoscaler", {}) or {}
        kourier = components.get("kourier", {}) or {}

        return cls(
            master_node=cluster.get("master_node", "auto"),
            master_label_selector=cluster.get(
                "master_label_selector", "node-role.kubernetes.io/control-plane"),
            ssh_aliases=cluster.get("ssh_aliases", {}) or {},
            scheduler_namespace=cluster.get("scheduler_namespace", "kube-system"),
            scheduler_prefix=cluster.get("scheduler_prefix", "my-scheduler"),
            scheduler_proc=cluster.get("scheduler_process",
                                        "/usr/local/bin/kube-scheduler"),
            dedicated_core=str(cluster.get("dedicated_core", "1")),
            knative_namespace=activator.get("namespace", "knative-serving"),
            activator_prefix=activator.get("prefix", "activator"),
            autoscaler_prefix=autoscaler.get("prefix", "autoscaler"),
            kourier_namespace=kourier.get("namespace", "kourier-system"),
            kourier_prefix=kourier.get("prefix", "3scale-kourier-gateway"),
        )

    @classmethod
    def from_yaml(cls, path: str) -> "ClusterConfig":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls.from_config_dict(data)

    def ssh_target(self, k8s_node_name: str) -> str:
        """Traduit un nom de nœud K8s (ex: pc8) vers son alias SSH (ex:
        worker14), nécessaire quand les noms K8s ne sont pas des hostnames
        résolvables directement. Si absent de la table, tente le nom brut
        plutôt que de planter."""
        alias = self.ssh_aliases.get(k8s_node_name)
        if alias is None:
            print(f"  WARNING: pas d'alias SSH connu pour '{k8s_node_name}', "
                  f"tentative avec le nom brut")
            return k8s_node_name
        return alias


def resolve_master_node(cfg: ClusterConfig) -> str:
    """Résout cfg.master_node : si explicite dans la config, retourne tel
    quel ; si "auto", découvre le nœud control-plane via
    cfg.master_label_selector (kubectl get nodes -l ...)."""
    if cfg.master_node != "auto":
        return cfg.master_node

    try:
        result = subprocess.run(
            ["kubectl", "get", "nodes", "-l", cfg.master_label_selector,
             "-o", "jsonpath={.items[0].metadata.name}"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(
            f"Auto-détection du master a échoué (label "
            f"'{cfg.master_label_selector}'): {e}. Renseigne "
            f"cluster.master_node explicitement dans config.yaml.")

    node = result.stdout.strip()
    if not node:
        raise RuntimeError(
            f"Aucun nœud trouvé avec le label '{cfg.master_label_selector}'. "
            f"Renseigne cluster.master_node explicitement dans config.yaml.")
    return node


def detect_current_mode(master_node: str) -> Mode:
    """Auto-détection du mode actuellement appliqué, en inspectant les
    taints du nœud master : NoExecute présent -> apiserver, sinon ->
    local1core. Utilisé quand controller.initial_mode == 'auto'."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "node", master_node,
             "-o", 'jsonpath={.spec.taints[*].key}|{.spec.taints[*].effect}'],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        print("  WARNING: impossible de lire les taints du master, "
              "hypothèse par défaut : local1core")
        return Mode.LOCAL1CORE

    output = result.stdout.strip()
    if "CriticalAddonsOnly" in output and "NoExecute" in output:
        return Mode.APISERVER
    return Mode.LOCAL1CORE


def run(cmd, dry_run=False, allow_fail=False):
    print(f"  $ {' '.join(cmd)}")
    if dry_run:
        return
    result = subprocess.run(cmd, capture_output=allow_fail, text=True)
    if result.returncode != 0:
        if allow_fail:
            print(f"  (ignoré : {result.stderr.strip()})")
        else:
            raise subprocess.CalledProcessError(result.returncode, cmd)


def get_pod_node_map(namespace: str) -> dict:
    """{nom_pod: nom_noeud} pour un namespace. Lecture seule, toujours
    exécutée même en dry-run (n'altère rien)."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace,
             "-o", "custom-columns=NAME:.metadata.name,NODE:.spec.nodeName",
             "--no-headers"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"  WARNING: impossible de lister les pods de {namespace}: {e}")
        return {}
    mapping = {}
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) == 2:
            mapping[parts[0]] = parts[1]
    return mapping


def find_pod_by_prefix(namespace: str, prefix: str):
    mapping = get_pod_node_map(namespace)
    for name, node in mapping.items():
        if name.startswith(prefix):
            return name, node
    return None, None


def delete_pods_by_prefix(namespace: str, prefix: str, dry_run: bool):
    """Supprime tous les pods dont le nom commence par `prefix`, peu importe
    leur nœud actuel -- leur controller (Deployment) les recrée ailleurs.

    --wait=false : ne bloque pas jusqu'à la terminaison réelle du pod
    (grace period de arrêt) -- inutile ici puisque le taint empêche déjà
    toute recréation sur le master, et la continuité de service est assurée
    par le réplica déjà en place ailleurs (make-before-break pour
    activator/kourier) ou n'est pas requise (scheduler/autoscaler, hors du
    chemin direct des requêtes en cours). Gain mesuré : ~1.2-1.3s -> ~0.05s
    par pod supprimé.
    """
    mapping = get_pod_node_map(namespace)
    matches = [name for name in mapping if name.startswith(prefix)]
    if not matches:
        print(f"  (aucun pod '{prefix}*' trouvé dans {namespace}, rien à supprimer)")
        return
    for name in matches:
        run(["kubectl", "delete", "pod", "-n", namespace, name,
             "--ignore-not-found", "--wait=false"], dry_run)


def get_deployment_replicas(namespace: str, deployment: str):
    """Nombre de réplicas actuel d'un Deployment, ou None si introuvable."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "deployment", deployment, "-n", namespace,
             "-o", "jsonpath={.spec.replicas}"],
            capture_output=True, text=True, check=True,
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None


def wait_for_new_pod_off_node(namespace: str, prefix: str, exclude_pod: str,
                                excluded_node: str, timeout_s: float = 60.0,
                                poll_s: float = 2.0):
    """Attend qu'un pod `prefix*` autre que `exclude_pod` soit Running,
    Ready, et placé hors de `excluded_node`. Retourne True si trouvé avant
    timeout, False sinon (l'appelant décide comment réagir à un timeout)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        mapping = get_pod_node_map(namespace)
        for name, node in mapping.items():
            if name.startswith(prefix) and name != exclude_pod and node != excluded_node:
                # vérifier Ready, pas seulement présent
                try:
                    result = subprocess.run(
                        ["kubectl", "get", "pod", name, "-n", namespace,
                         "-o", "jsonpath={.status.containerStatuses[0].ready}"],
                        capture_output=True, text=True, check=True,
                    )
                    if result.stdout.strip() == "true":
                        return True
                except subprocess.CalledProcessError:
                    pass
        time.sleep(poll_s)
    return False


def evacuate_gracefully(namespace: str, prefix: str, pod_name: str,
                          master_node: str, dry_run: bool):
    """Make-before-break : scale le Deployment `prefix` de +1 réplica,
    attend qu'un nouveau pod soit Ready ailleurs, PUIS seulement retourne.
    Le pod d'origine (`pod_name`, déjà confirmé sur `master_node` par
    l'appelant) sera évincé par le taint appliqué juste après -- sans
    jamais passer par un état où aucun réplica n'est disponible.

    Suppose que l'appelant a déjà vérifié que `pod_name` est bien sur
    `master_node` (pas de nouvelle requête cluster pour re-vérifier --
    évite une lecture redondante déjà faite par l'appelant).

    Retourne le nombre de réplicas d'origine (pour que l'appelant puisse
    redescendre l'échelle après coup), ou None si le Deployment est
    introuvable (bascule directe sans évacuation gracieuse).
    """
    print(f"  -> {pod_name} est sur le master, évacuation gracieuse (make-before-break)")
    original_replicas = get_deployment_replicas(namespace, prefix)
    if original_replicas is None:
        print(f"  WARNING: Deployment '{prefix}' introuvable dans {namespace}, "
              f"bascule directe sans évacuation gracieuse")
        return None

    target_replicas = original_replicas + 1
    run(["kubectl", "scale", "deployment", prefix, "-n", namespace,
         f"--replicas={target_replicas}"], dry_run)

    if dry_run:
        return original_replicas

    ok = wait_for_new_pod_off_node(namespace, prefix, exclude_pod=pod_name,
                                    excluded_node=master_node)
    if not ok:
        print(f"  WARNING: timeout en attendant le nouveau réplica de "
              f"'{prefix}' hors du master -- le taint qui suit risque de "
              f"couper le service le temps qu'un réplica soit disponible")

    return original_replicas


def apply_local1core(cfg: ClusterConfig, dry_run: bool = False):
    """1. untaint + uncordon le master (les workloads peuvent y tourner)
       2. découvre dynamiquement le nœud où tourne le scheduler custom
       3. SSH sur ce nœud, pin le process (core dédié + priorité RT max)
    """
    run(["kubectl", "taint", "node", cfg.master_node, "CriticalAddonsOnly-"],
        dry_run, allow_fail=True)
    run(["kubectl", "uncordon", cfg.master_node], dry_run, allow_fail=True)

    pod_name, sched_node = find_pod_by_prefix(cfg.scheduler_namespace,
                                               cfg.scheduler_prefix)
    if sched_node is None:
        print(f"  WARNING: pod '{cfg.scheduler_prefix}*' introuvable dans "
              f"{cfg.scheduler_namespace}, pinning ignoré")
        return

    print(f"  -> {pod_name} trouvé sur le nœud {sched_node}")

    pin_cmd = (
        f"pid=$(pgrep -o -f {cfg.scheduler_proc}) && "
        f"sudo taskset -cp {cfg.dedicated_core} $pid && "
        f"sudo renice -20 -p $pid && "
        f"sudo chrt -f -p 99 $pid"
    )
    target = cfg.ssh_target(sched_node)
    run(["ssh", target, pin_cmd], dry_run)


def apply_apiserver(cfg: ClusterConfig, dry_run: bool = False):
    """1. vérifie où sont activator, kourier-gateway, autoscaler ET le
          scheduler custom -- une seule lecture chacun, réutilisée pour
          la décision ET l'action qui suit
       2. cordon le master SEULEMENT si au moins un composant à évacuation
          gracieuse (activator/kourier/autoscaler) y est effectivement
          présent (sinon aucune protection n'est nécessaire, skip cordon/
          uncordon économise 2 aller-retours API server)
       3. évacuation gracieuse (make-before-break) des composants
          concernés -- scale +1 replica ailleurs, attend qu'il soit Ready,
          AVANT tout taint. Concerne activator, kourier-gateway ET
          autoscaler : tous trois font partie du chemin de service ou de
          la boucle de contrôle Knative, une coupure brève dégraderait le
          service ou retarderait des décisions de scaling en cours.
       4. taint le master en NoExecute (toujours)
       5. uncordon SEULEMENT si on avait cordonné à l'étape 2
       6. supprime le scheduler custom -- SEULEMENT s'il est effectivement
          sur le master (sinon rien à faire, économise un cycle de
          recréation inutile), et SANS évacuation gracieuse : contrairement
          aux trois autres, on ignore si son élection de leader d'origine
          est intacte après modification -- faire tourner deux réplicas en
          parallèle risquerait un double-scheduling, donc suppression
          simple (--wait=false) plutôt que make-before-break
       7. redescend les composants évacués à leur effectif de réplicas
          d'origine (nettoyage post-évacuation)
    """
    graceful_candidates = [(cfg.knative_namespace, cfg.activator_prefix),
                            (cfg.kourier_namespace, cfg.kourier_prefix),
                            (cfg.knative_namespace, cfg.autoscaler_prefix)]

    to_evacuate = []  # (namespace, prefix, pod_name)
    for namespace, prefix in graceful_candidates:
        pod_name, node = find_pod_by_prefix(namespace, prefix)
        if node == cfg.master_node:
            to_evacuate.append((namespace, prefix, pod_name))
        else:
            print(f"  ({prefix}* déjà hors du master, pas d'évacuation nécessaire)")

    cordoned = bool(to_evacuate)
    if cordoned:
        run(["kubectl", "cordon", cfg.master_node], dry_run)

    pending_scale_down = []
    for namespace, prefix, pod_name in to_evacuate:
        original = evacuate_gracefully(namespace, prefix, pod_name,
                                        cfg.master_node, dry_run)
        if original is not None:
            pending_scale_down.append((namespace, prefix, original))

    run(["kubectl", "taint", "node", cfg.master_node,
         "CriticalAddonsOnly=true:NoExecute", "--overwrite"], dry_run)

    if cordoned:
        run(["kubectl", "uncordon", cfg.master_node], dry_run, allow_fail=True)

    scheduler_pod, scheduler_node = find_pod_by_prefix(
        cfg.scheduler_namespace, cfg.scheduler_prefix)
    if scheduler_node == cfg.master_node:
        delete_pods_by_prefix(cfg.scheduler_namespace, cfg.scheduler_prefix, dry_run)
    else:
        print(f"  ({cfg.scheduler_prefix}* déjà hors du master, "
              f"pas de suppression nécessaire)")

    for namespace, prefix, original in pending_scale_down:
        run(["kubectl", "scale", "deployment", prefix, "-n", namespace,
             f"--replicas={original}"], dry_run)


def apply_mode(cfg: ClusterConfig, mode: Mode, dry_run: bool = False):
    """Point d'entrée unique utilisé par controller.py -- routage vers la
    bonne fonction selon le Mode décidé par policy.py."""
    if mode == Mode.APISERVER:
        apply_apiserver(cfg, dry_run)
    else:
        apply_local1core(cfg, dry_run)
