import time
import requests
import subprocess
import csv
from statistics import median

SERVICE_URL = "http://131.254.100.72:32340"
HEADERS     = {"Host": "helloworld.default.example.com"}
session     = requests.Session()

NAMESPACE = "default"
SERVICE   = "helloworld"


# ─────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────

def pods_running():
    r = subprocess.run([
        "kubectl", "get", "pods", "-n", NAMESPACE,
        "-l", f"serving.knative.dev/service={SERVICE}",
        "--no-headers"
    ], capture_output=True, text=True)

    return sum(
        1 for l in r.stdout.splitlines()
        if "Running" in l and "Terminating" not in l
    )


def wait_scale_to_zero(timeout=120):
    print("Waiting scale-to-zero...", end="", flush=True)

    for t in range(timeout):
        if pods_running() == 0:
            print(f" OK ({t}s)")
            return True
        print(".", end="", flush=True)
        time.sleep(1)

    print(" TIMEOUT")
    return False


def wait_ready(timeout=60):
    """Wait until pod is fully READY (not just existing)"""
    for _ in range(timeout * 2):
        r = subprocess.run([
            "kubectl", "get", "pod", "-n", NAMESPACE,
            "-l", f"serving.knative.dev/service={SERVICE}",
            "-o", "jsonpath={.items[0].status.containerStatuses[0].ready}"
        ], capture_output=True, text=True)

        if "true" in r.stdout.lower():
            return True

        time.sleep(0.5)

    return False


# ─────────────────────────────────────────────
# EXPERIMENT
# ─────────────────────────────────────────────

results = []

for i in range(500):

    print(f"\n=== Iteration {i} ===")

    # 1) scale-to-zero
    if not wait_scale_to_zero():
        print(f"[{i}] SKIP (scale-to-zero timeout)")
        continue

    # 2) COLD REQUEST
    try:
        t0 = time.perf_counter()
        session.get(SERVICE_URL, headers=HEADERS, timeout=60).raise_for_status()
        cold_latency = (time.perf_counter() - t0) * 1000
    except Exception as e:
        print(f"[{i}] SKIP cold error: {e}")
        continue

    # 3) wait fully ready (important for warm validity)
    time.sleep(2)
    if not wait_ready():
        print(f"[{i}] SKIP (pod not ready)")
        continue

    # 4) WARM samples (robust via median)
    warm_samples = []
    try:
        for _ in range(5):
            t0 = time.perf_counter()
            session.get(SERVICE_URL, headers=HEADERS, timeout=10).raise_for_status()
            warm_samples.append((time.perf_counter() - t0) * 1000)
    except Exception as e:
        print(f"[{i}] SKIP warm error: {e}")
        continue

    warm_latency = median(warm_samples)
    overhead     = cold_latency - warm_latency

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

    result = {
        "iteration": i,
        "timestamp": timestamp,
        "cold_ms": round(cold_latency, 2),
        "warm_ms": round(warm_latency, 2),
        "overhead_ms": round(overhead, 2),
    }

    results.append(result)

    print(
        f"[{i}] cold={cold_latency:.0f}ms | "
        f"warm={warm_latency:.0f}ms | "
        f"overhead={overhead:.0f}ms | "
        f"samples={[round(x) for x in warm_samples]}"
    )

# ─────────────────────────────────────────────
# SAVE CSV
# ─────────────────────────────────────────────

fieldnames = ["iteration", "timestamp", "cold_ms", "warm_ms", "overhead_ms"]

with open("cold_warm_results.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)

print(f"\n✓ Done → {len(results)} samples saved in cold_warm_results.csv")
