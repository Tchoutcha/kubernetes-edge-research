# APC: Adaptive Control-Plane Configuration

This repository contains the implementation of **APC**, an adaptive control-plane isolation controller presented in our paper (submitted fordouble-blind review).

APC dynamically switches a K3s/Knative cluster between two control-plane isolation levels based on the live request rate observed at the server side.The controller adapts to workload changes without requiring prior knowledge
of the workload.

## Mapping to the Paper

| Paper element                                 | Location in this repository                                     |
| --------------------------------------------- | --------------------------------------------------------------- |
| Table 1 (isolation configurations)            | `cluster_actions.py` (`apply_local1core`, `apply_apiserver`)    |
| Eqs. 1--4 (decision model)                    | `policy.py` (`HysteresisPolicy.decide`)                         |
| Algorithm 1                                   | `controller.py` (`run_iterations`)                              |
| Reconfiguration mechanism (make-before-break) | `cluster_actions.py` (`evacuate_gracefully`, `apply_apiserver`) |
| Request-rate signal (Kourier)                 | `metrics_provider.py` (`KourierMetricsProvider`)                |

## Architecture

The controller is organized into three independently testable layers:

```text
Metrics Provider  ->  Request Rate  ->  Decision Policy  ->  Mode  ->  Cluster Actions
(metrics_provider.py)                  (policy.py)                 (cluster_actions.py)
```


| File                  | Role                                                                                                     | Requires a live cluster?                                             |
| --------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `policy.py`           | Thresholds, hysteresis, asymmetric confirmation, and cooldown                                            | No                                                                   |
| `metrics_provider.py` | Request-rate signal (Kourier, or client-side fallback)                                                   | Only for live use; rate computation is unit-tested without a cluster |
| `cluster_actions.py`  | `kubectl` taint/cordon, dynamic node discovery, SSH-based pinning, and make-before-break reconfiguration | Yes                                                                  |
| `controller.py`       | Configuration resolution, CLI, orchestration loop, and structured logging                                | Yes, except with `--dry-run` or `--check-config`                     |

This separation allows the decision policy (`policy.py`), which is the main object of evaluation in the paper (Algorithm 1, Eqs. 1--4), to be
verified independently of the cluster and of the specific metrics source used.

## Installation

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml   # then adapt to your cluster
```


## Requirements

* Python 3.10+
* `kubectl` configured (`KUBECONFIG`) to control the target cluster
* Passwordless SSH access to every node in the cluster. The custom scheduler
  and Knative components have no fixed node placement and may be scheduled
  on any worker.

## Configuration

All cluster-specific and deployment-specific configuration is defined in
`config.yaml` (see `config.example.yaml` for the complete schema and inline
documentation). The `policy.py`, `cluster_actions.py`, and `controller.py`
modules remain generic.

The policy thresholds used to produce the results reported in the paper are:

```yaml
policy:
  low_threshold_rps: 20
  high_threshold_rps: 50
  required_high_samples: 3    # confirmations to escalate (fast)
  required_low_samples: 60    # confirmations to de-escalate (conservative)
  cooldown_seconds: 60
```

See the paper's Design section for the rationale behind the asymmetry between
`required_high_samples` and `required_low_samples`.

## Usage

### Normal usage

By default, the controller loads `config.yaml` and starts the control loop:

```bash
python3 controller.py
```

The controller resolves its configuration, automatically detects the cluster
state it needs, and runs indefinitely as an adaptive control loop.

**Configuration resolution**, in the following order (first match wins):

1. `--config` explicitly provided
2. `ACPC_CONFIG` environment variable
3. `./config.yaml`
4. `/etc/adaptive-controller/config.yaml`
5. Safe built-in defaults (if no configuration file is found; this is always
   announced and never silent)

**Automatically detected**, with no additional configuration:

* The control-plane node, via `cluster.master_label_selector`, which defaults to the standard `node-role.kubernetes.io/control-plane` label
  
* The currently active mode at startup, by inspecting node taints
* 
* The node currently hosting each managed component (scheduler, activator,autoscaler, and ingress gateway) at every reconfiguration, since these
  components have no fixed placement

**Remains configurable** (see `config.example.yaml`): thresholds, confirmation counts, cooldown, dedicated CPU core, pod name prefixes (if your deployment
differs), SSH alias table, and behavior when the metrics source is unavailable.

### Other commands

```bash
python3 controller.py --config path/to/config.yaml   # explicit config
python3 controller.py --dry-run                      # print actions without executing
python3 controller.py --once                          # single decision iteration, then exit
python3 controller.py --check-config                 # resolve config + auto-detection, print, exit
python3 controller.py --switch-to apiserver           # manual one-shot switch [testing only]
```

`--check-config` is the recommended first step on a new cluster: it resolves the full configuration and performs all available auto-detection **without
executing any cluster-changing action**, allowing the configuration to be verified before running the controller for real.

## How the Request Rate Is Measured (`metrics.provider: kourier`, Default)

The controller reads the cumulative Envoy counter

`envoy_http_downstream_rq_total{envoy_http_conn_manager_prefix="ingress_http"}`

exposed by the Kourier ingress gateway pod, and derives the request rate from the delta between successive reads.

This is a **server-side** measurement: it reflects the load received at the ingress gateway rather than the requests generated by the client. This avoids
relying solely on injected load, which may differ from the load actually received or processed by the system under saturation.

No Prometheus deployment is required: Kourier's Envoy proxy already exposes its counters through `/stats/prometheus`.

A second provider (`metrics.provider: client`), based on a sliding window of client-side request timestamps, is available as a fallback. See the
documentation in `metrics_provider.py` for details.


## Logs

Every event (start, transition, stop) is written to `logging.path` in either CSV or JSONL format, as specified by `logging.format`. Each entry contains
both an epoch timestamp and an ISO 8601 timestamp, making the logs directly usable with pandas to correlate controller events with independently
collected latency and energy measurements.

## Testing the Decision Logic Without a Cluster

The decision policy (`policy.py`) has no dependency on a live cluster and can be tested independently:

```bash
python3 -m unittest test_policy.py -v
```

This part of the artifact can therefore be verified without access to the physical testbed used in the paper.

## Known Limitations

* The default thresholds (`low_threshold_rps: 20`, `high_threshold_rps: 50`) were calibrated empirically on our testbed (K3s/Knative on Raspberry Pi 5)
  and should be re-tuned for different hardware.
  
* Deleting the Kourier pod during a transition to `apiserver` resets its request counter. `metrics_provider.py` detects this reset and avoids
  computing an incorrect negative-delta rate, but one measurement point is lost at each such transition.
  
* Master auto-detection via label assumes a single control-plane node. On a multi-master cluster, set `cluster.master_node` explicitly.
  
* `metrics.provider: client` measures offered (injected) load rather than load actually received at the ingress gateway. It is provided as a
  fallback and was not used for the results reported in the paper.

## License

License to be finalized upon acceptance.



