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
    "encrypt",
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

# Phases de charge (Poisson)
PHASES = [
    {"nom": "low",    "lambda": 1,  "duree": 120},  # 1 req/s pendant 2 min
    {"nom": "medium", "lambda": 5,  "duree": 180},  # 5 req/s pendant 3 min
    {"nom": "burst",  "lambda": 15, "duree": 30},   # 15 req/s pendant 30s
]

SEUIL_COLD_MS   = 2000   # latence > 2s = cold start
INVOCATION_FILE = "invocation_results.csv"
LATENCY_FILE    = "latency_percentiles.csv"
WORKLOAD_FILE   = "workload.json"

# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCTION DU WORKLOAD (Poisson)
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

    # Sauvegarder le workload sans les payloads (pour reproductibilité)
    save = [{"t": r["t"], "phase": r["phase"],
             "function": r["function"], "size": r["size"]}
            for r in workload]
    with open(WORKLOAD_FILE, "w") as f:
        json.dump(save, f, indent=2)

    # Résumé
    df_w = pd.DataFrame(save)
    print("\nWorkload généré :")
    print(df_w.groupby("phase").size().to_string())
    print(f"Total : {len(workload)} requêtes")
    print(f"Durée : {workload[-1]['t']:.0f} secondes (~{workload[-1]['t']/60:.1f} min)\n")

    return workload

# ─────────────────────────────────────────────────────────────────────────────
# INVOCATION ASYNCHRONE
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
            await resp.text()
            elapsed  = (time.time() - start) * 1000
            type_req = "cold" if elapsed > SEUIL_COLD_MS else "warm"

            results[index] = {
                "index":      index,
                "phase":      req_info["phase"],
                "function":   fn,
                "size":       size,
                "latency_ms": round(elapsed, 1),
                "type":       type_req,
                "status":     resp.status,
            }
            print(f"[{index:04d}] {fn:22s} {size:6s} {req_info['phase']:6s} "
                  f"→ {resp.status} {elapsed:8.1f}ms  [{type_req}]")

    except Exception as e:
        results[index] = {
            "index":      index,
            "phase":      req_info["phase"],
            "function":   fn,
            "size":       size,
            "latency_ms": None,
            "type":       "error",
            "status":     "ERROR",
        }
        print(f"[{index:04d}] {fn:22s} {size:6s} → ERROR: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# REPLAY DU WORKLOAD (timing Poisson)
# ─────────────────────────────────────────────────────────────────────────────
async def run_workload(requests_list):
    results = [None] * len(requests_list)

    async with aiohttp.ClientSession() as session:
        t0    = time.time()
        tasks = []

        for i, req_info in enumerate(requests_list):
            # Attendre le moment exact défini par Poisson
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
# SAUVEGARDE — résultats bruts
# ─────────────────────────────────────────────────────────────────────────────
valid_results = [r for r in results if r is not None]
with open(INVOCATION_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "index", "phase", "function", "size",
        "latency_ms", "type", "status"])
    writer.writeheader()
    writer.writerows(valid_results)
print(f"Résultats bruts → {INVOCATION_FILE}")

# ─────────────────────────────────────────────────────────────────────────────
# STATISTIQUES
# ─────────────────────────────────────────────────────────────────────────────
df = pd.DataFrame(valid_results)
df = df[df["status"] != "ERROR"]
df["latency_ms"] = df["latency_ms"].astype(float)

print("\n── Percentiles par phase / type / fonction ──────────────────────────")
print(f"{'Phase':<8} {'Type':<5} {'Function':<22} {'p50':>8} {'p95':>8} {'p99':>8} {'n':>5}")
print("-" * 65)

rows = []
for phase in ["low", "medium", "burst"]:
    for type_req in ["cold", "warm"]:
        for fn in FUNCTIONS:
            sub = df[
                (df["phase"]    == phase)    &
                (df["type"]     == type_req) &
                (df["function"] == fn)
            ]["latency_ms"]
            if len(sub) == 0:
                continue
            p50 = np.percentile(sub, 50)
            p95 = np.percentile(sub, 95)
            p99 = np.percentile(sub, 99)
            print(f"{phase:<8} {type_req:<5} {fn:<22} "
                  f"{p50:>8.1f} {p95:>8.1f} {p99:>8.1f} {len(sub):>5}")
            rows.append({
                "phase": phase, "type": type_req, "function": fn,
                "p50_ms": round(p50,1), "p95_ms": round(p95,1),
                "p99_ms": round(p99,1), "n": len(sub)
            })

with open(LATENCY_FILE, "w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["phase","type","function","p50_ms","p95_ms","p99_ms","n"])
    writer.writeheader()
    writer.writerows(rows)
print(f"\nPercentiles → {LATENCY_FILE}")

# Résumé global cold vs warm
print("\n── Résumé global ────────────────────────────────────────────────────")
for type_req in ["cold", "warm"]:
    sub = df[df["type"] == type_req]["latency_ms"]
    if len(sub) == 0:
        continue
    print(f"{type_req.upper():5} : p50={np.percentile(sub,50):.0f}ms  "
          f"p95={np.percentile(sub,95):.0f}ms  "
          f"p99={np.percentile(sub,99):.0f}ms  "
          f"n={len(sub)}")
