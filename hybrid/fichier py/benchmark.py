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
GATEWAY_URL = "http://131.254.100.72:32340"
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

PHASES = [
    {"nom": "low",    "lambda": 1,  "duree": 120},
    {"nom": "medium", "lambda": 5,  "duree": 180},
    {"nom": "burst",  "lambda": 15, "duree": 30},
]

SEUIL_COLD_MS   = 2000
INVOCATION_FILE = "invocation_results.csv"
LATENCY_FILE    = "latency_percentiles.csv"
WORKLOAD_FILE   = "workload.json"

# ─────────────────────────────────────────────────────────────────────────────
# WORKLOAD
# ─────────────────────────────────────────────────────────────────────────────
def build_request_list():
    np.random.seed(42)
    random.seed(42)
    workload = []
    t = 0.0

    for phase in PHASES:
        fin_phase = t + phase["duree"]
        while True:
            t += np.random.exponential(1.0 / phase["lambda"])
            if t >= fin_phase:
                break

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
                "phase":    phase["nom"],
                "function": fn,
                "size":     size,
                "payload":  payload,
            })

        t = fin_phase

    save = [{"t": r["t"], "phase": r["phase"],
             "function": r["function"], "size": r["size"]}
            for r in workload]

    with open(WORKLOAD_FILE, "w") as f:
        json.dump(save, f, indent=2)

    df_w = pd.DataFrame(save)
    print("\nWorkload généré :")
    print(df_w.groupby("phase").size().to_string())
    print(f"Total : {len(workload)} requêtes")
    print(f"Durée : {workload[-1]['t']:.0f} secondes (~{workload[-1]['t']/60:.1f} min)\n")

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
                "phase": req_info["phase"],
                "function": fn,
                "size": size,
                "latency_ms": round(elapsed, 1),
                "execution_time_sec": exec_time,
                "type": type_req,
                "status": resp.status,
            }

            print(f"[{index:04d}] {fn:22s} {size:6s} {req_info['phase']:6s} "
                  f"→ {resp.status} {elapsed:8.1f}ms [{type_req}] (exec={exec_time}s)")

    except Exception as e:
        results[index] = {
            "index": index,
            "phase": req_info["phase"],
            "function": fn,
            "size": size,
            "latency_ms": None,
            "execution_time_sec": None,
            "type": "error",
            "status": "ERROR",
        }
        print(f"[{index:04d}] {fn:22s} {size:6s} → ERROR: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# REPLAY
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
print("Construction du workload Poisson...")
print("=" * 65)
requests_list = build_request_list()

print("=" * 65)
print(f"Lancement du benchmark — {len(requests_list)} requêtes")
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
        "index", "phase", "function", "size",
        "latency_ms", "execution_time_sec", "type", "status"
    ])
    writer.writeheader()
    writer.writerows(valid_results)

print(f"Résultats bruts → {INVOCATION_FILE}")

# ─────────────────────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────────────────────
df = pd.DataFrame(valid_results)
df = df[df["status"] != "ERROR"]
df["latency_ms"] = df["latency_ms"].astype(float)

print("\n── Percentiles ──────────────────────────")

for phase in ["low", "medium", "burst"]:
    for type_req in ["cold", "warm"]:
        for fn in FUNCTIONS:
            sub = df[
                (df["phase"] == phase) &
                (df["type"] == type_req) &
                (df["function"] == fn)
            ]["latency_ms"]

            if len(sub) == 0:
                continue

            print(f"{phase:<8} {type_req:<5} {fn:<22} "
                  f"{np.percentile(sub,50):>8.1f} "
                  f"{np.percentile(sub,95):>8.1f} "
                  f"{np.percentile(sub,99):>8.1f}")
