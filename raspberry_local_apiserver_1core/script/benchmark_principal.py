import asyncio
import aiohttp
import time
import csv
import json
import random
import numpy as np
import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
GATEWAY_URL = "http://131.254.100.73:31075"
NAMESPACE   = "default"
SAMPLES_DIR = Path("./samples")

FUNCTIONS = [
    "graphgen",
    "fastfouriertransform",
    "fetchdata",
    "genmatrix",
    "grayscale",
    "linpack",
    "matrixmul",
    "mobilenet",
    "pagerank",
    "resnet",
]

# 👉 INTERVAL FIXE (modifie ici)
REQUEST_INTERVAL = 1   # secondes (0.1 = 100ms = 10 req/s)

# 👉 DURÉE TEST
TEST_DURATION = 2000  # secondes

SEUIL_COLD_MS   = 2000
INVOCATION_FILE = "invocation_results_fixed.csv"
LATENCY_FILE    = "latency_percentiles_fixed.csv"

# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCTION WORKLOAD FIXED RATE
# ─────────────────────────────────────────────────────────────────────────────
def build_request_list():
    random.seed(42)

    workload = []
    t = 0.0
    index = 0

    while t < TEST_DURATION:
        fn   = random.choice(FUNCTIONS)
        size = random.choice(["small", "medium", "large"])

        input_path = SAMPLES_DIR / fn / "samples" / size / "input" / "input.json"
        try:
            with open(input_path) as f:
                payload = json.load(f)
        except FileNotFoundError:
            print(f"[WARN] {input_path} introuvable — payload vide")
            payload = {}

        workload.append({
            "t":        round(t, 3),
            "function": fn,
            "size":     size,
            "payload":  payload,
        })

        t += REQUEST_INTERVAL
        index += 1

    print(f"\nWorkload FIXED généré : {len(workload)} requêtes")
    print(f"Durée : {TEST_DURATION}s | Intervalle : {REQUEST_INTERVAL}s "
          f"(~{1/REQUEST_INTERVAL:.1f} req/s)\n")

    return workload

# ─────────────────────────────────────────────────────────────────────────────
# INVOCATION
# ─────────────────────────────────────────────────────────────────────────────
async def invoke(session, index, req_info, results):
    fn      = req_info["function"]
    size    = req_info["size"]
    payload = req_info["payload"]
    host    = f"{fn}.{NAMESPACE}.example.com"

    start = time.time()
    try:
        async with session.post(
            GATEWAY_URL,
            headers={"Host": host, "Content-Type": "application/json"},
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            text = await resp.text()
            elapsed  = (time.time() - start) * 1000
            type_req = "cold" if elapsed > SEUIL_COLD_MS else "warm"

            exec_time = None
            try:
                payload_resp = json.loads(text)
                exec_time = payload_resp.get("execution_time_sec", None)
            except:
                pass

            results[index] = {
                "index": index,
                "function": fn,
                "size": size,
                "latency_ms": round(elapsed, 1),
                "execution_time_sec": exec_time,
                "type": type_req,
                "status": resp.status,
            }

            print(f"[{index:04d}] {fn:22s} {size:6s} "
                  f"→ {resp.status} {elapsed:8.1f}ms [{type_req}] (exec={exec_time}s)")

    except Exception as e:
        results[index] = {
            "index": index,
            "function": fn,
            "size": size,
            "latency_ms": None,
            "execution_time_sec": None,
            "type": "error",
            "status": "ERROR",
        }
        print(f"[{index:04d}] {fn:22s} {size:6s} → ERROR: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# REPLAY FIXED RATE
# ─────────────────────────────────────────────────────────────────────────────
async def run_workload(requests_list):
    results = [None] * len(requests_list)

    async with aiohttp.ClientSession() as session:
        t0 = time.time()
        tasks = []

        for i, req_info in enumerate(requests_list):
            cible = t0 + req_info["t"]
            delay = cible - time.time()

            if delay > 0:
                await asyncio.sleep(delay)

            task = asyncio.create_task(
                invoke(session, i, req_info, results)
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

    return results

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 65)
print("Construction workload FIXED RATE...")
print("=" * 65)

requests_list = build_request_list()

print("=" * 65)
print(f"Lancement benchmark FIXED — {len(requests_list)} requêtes")
print("=" * 65)

t_start = time.time()
results = asyncio.run(run_workload(requests_list))
total_time = time.time() - t_start

print(f"\nTerminé en {total_time:.1f}s ({len(requests_list)/total_time:.1f} req/s)\n")

# ─────────────────────────────────────────────────────────────────────────────
# SAVE CSV
# ─────────────────────────────────────────────────────────────────────────────
valid_results = [r for r in results if r is not None]

with open(INVOCATION_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "index", "function", "size",
        "latency_ms", "execution_time_sec", "type", "status"
    ])
    writer.writeheader()
    writer.writerows(valid_results)

print(f"Résultats → {INVOCATION_FILE}")

# ─────────────────────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────────────────────
df = pd.DataFrame(valid_results)
df = df[df["status"] != "ERROR"]
df["latency_ms"] = df["latency_ms"].astype(float)

print("\n── Percentiles globaux ──────────────────────────")

for fn in FUNCTIONS:
    sub = df[df["function"] == fn]["latency_ms"]
    if len(sub) == 0:
        continue

    print(f"{fn:<22} "
          f"p50={np.percentile(sub,50):.1f} "
          f"p95={np.percentile(sub,95):.1f} "
          f"p99={np.percentile(sub,99):.1f} "
          f"n={len(sub)}")
