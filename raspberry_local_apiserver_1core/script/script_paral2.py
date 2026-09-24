import time
import requests
import subprocess
import csv

SERVICE_URL = "http://131.254.100.72:32340"
HEADERS = {"Host": "helloworld.default.example.com"}

# -------------------------
# Utils
# -------------------------
def pods_running():
    r = subprocess.run([
        "kubectl", "get", "pods", "-n", "default",
        "-l", "serving.knative.dev/service=helloworld",
        "--field-selector=status.phase=Running",
        "--no-headers"
    ], capture_output=True, text=True)

    return len([l for l in r.stdout.split("\n") if l.strip()])


def wait_scale_to_zero(timeout=120):
    for _ in range(timeout):
        if pods_running() == 0:
            return True
        time.sleep(1)
    return False


def measure_request():
    t0 = time.time()
    requests.get(SERVICE_URL, headers=HEADERS, timeout=60)
    return (time.time() - t0) * 1000


# -------------------------
# Benchmark
# -------------------------
results = []

for i in range(500):

    # 1) FORCE cold state
    print(f"\n[{i}] waiting scale-to-zero...")
    if not wait_scale_to_zero():
        print(f"[{i}] SKIP (timeout)")
        continue

    time.sleep(2)  # stabilisation activator

    # 2) COLD START
    cold = measure_request()

    # 3) STABILISATION (IMPORTANT)
    # on "réchauffe" proprement le système
    time.sleep(2)

    # 4) WARM START (steady-state)
    warm = measure_request()

    result = {
        "iteration": i,
        "cold_ms": cold,
        "warm_ms": warm,
        "overhead_ms": cold - warm
    }

    results.append(result)

    print(f"[{i}] cold={cold:.0f}ms | warm={warm:.0f}ms | overhead={cold-warm:.0f}ms")


# -------------------------
# Save
# -------------------------
with open("cold_warm_results.csv", "w", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["iteration", "cold_ms", "warm_ms", "overhead_ms"]
    )
    writer.writeheader()
    writer.writerows(results)

print("\nDone → cold_warm_results.csv")
