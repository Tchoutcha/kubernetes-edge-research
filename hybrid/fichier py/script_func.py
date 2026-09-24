import asyncio
import aiohttp
import time
import csv
import json
import random
import numpy as np
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
GATEWAY_URL  = "http://131.254.100.72:32340"
NAMESPACE    = "default"
TOTAL        = 500        # nombre total de requêtes
INTERVAL     = 1       # 10ms entre requêtes (burst contrôlé)

# Tes 10 fonctions — adapte les noms
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

# Dossier racine contenant les samples
# Structure attendue :
#   samples/<function>/small/input.json
#   samples/<function>/medium/input.json
#   samples/<function>/large/input.json
SAMPLES_DIR = Path("./samples")

# Répartition par fonction : 2×small, 2×medium, 1×large
WORKLOAD_PATTERN = ["small", "small", "medium", "medium", "large"]
# → 5 requêtes par fonction × 10 fonctions = 50 req/cycle
# → 500 / 50 = 10 cycles

INVOCATION_FILE = "invocation_results.csv"
LATENCY_FILE    = "latency_percentiles.csv"

# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCTION DE LA LISTE DES REQUÊTES
# ─────────────────────────────────────────────────────────────────────────────
def build_request_list():
    """
    Construit la liste des 500 requêtes :
    10 cycles × (10 fonctions × 5 tailles) = 500
    Ordre aléatoire dans chaque cycle pour éviter les biais.
    """
    requests_list = []
    cycles = TOTAL // (len(FUNCTIONS) * len(WORKLOAD_PATTERN))

    for cycle in range(cycles):
        cycle_requests = []
        for fn in FUNCTIONS:
            for size in WORKLOAD_PATTERN:
                input_path = SAMPLES_DIR / fn / "samples" / size / "input" / "input.json"

                # Charge le payload JSON si disponible
                try:
                    with open(input_path) as f:
                        payload = json.load(f)
                except FileNotFoundError:
                    print(f"[WARN] {input_path} introuvable — payload vide")
                    payload = {}

                cycle_requests.append({
                    "function": fn,
                    "size":     size,
                    "payload":  payload,
                    "cycle":    cycle,
                })

        # Mélange l'ordre dans le cycle pour éviter les patterns
        random.shuffle(cycle_requests)
        requests_list.extend(cycle_requests)

    return requests_list

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
            body    = await resp.text()
            elapsed = (time.time() - start) * 1000   # ms

            results[index] = {
                "index":    index,
                "function": fn,
                "size":     size,
                "cycle":    req_info["cycle"],
                "latency_ms": elapsed,
                "status":   resp.status,
            }
            print(f"[{index:03d}] {fn:20s} {size:6s} "
                  f"→ {resp.status} {elapsed:7.1f}ms")

    except Exception as e:
        results[index] = {
            "index":      index,
            "function":   fn,
            "size":       size,
            "cycle":      req_info["cycle"],
            "latency_ms": None,
            "status":     "ERROR",
        }
        print(f"[{index:03d}] {fn:20s} {size:6s} → ERROR: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# BURST CONTRÔLÉ
# ─────────────────────────────────────────────────────────────────────────────
async def run_burst(requests_list):
    results = [None] * len(requests_list)

    async with aiohttp.ClientSession() as session:
        t0    = time.time()
        tasks = []

        for i, req_info in enumerate(requests_list):
            # Respect de l'intervalle entre requêtes
            scheduled = t0 + i * INTERVAL
            delay = scheduled - time.time()
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
print(f"Construction de {TOTAL} requêtes...")
requests_list = build_request_list()
print(f"  {len(requests_list)} requêtes prêtes — "
      f"{len(FUNCTIONS)} fonctions × {len(WORKLOAD_PATTERN)} tailles × "
      f"{TOTAL // (len(FUNCTIONS)*len(WORKLOAD_PATTERN))} cycles\n")

t_start = time.time()
results = asyncio.run(run_burst(requests_list))
total_time = time.time() - t_start

print(f"\n{TOTAL} requêtes en {total_time:.2f}s "
      f"({TOTAL/total_time:.1f} req/s)\n")

# ─────────────────────────────────────────────────────────────────────────────
# SAUVEGARDE — résultats bruts
# ─────────────────────────────────────────────────────────────────────────────
with open(INVOCATION_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "index", "function", "size", "cycle",
        "latency_ms", "status"])
    writer.writeheader()
    writer.writerows([r for r in results if r is not None])

print(f"Résultats bruts → {INVOCATION_FILE}")

# ─────────────────────────────────────────────────────────────────────────────
# STATISTIQUES PAR FONCTION ET PAR TAILLE
# ─────────────────────────────────────────────────────────────────────────────
import pandas as pd

df = pd.DataFrame([r for r in results if r is not None])
df = df[df["status"] != "ERROR"]
df["latency_ms"] = df["latency_ms"].astype(float)

print("\n── Percentiles par fonction ─────────────────────────────────────────")
print(f"{'Function':<22} {'Size':<8} {'p50':>8} {'p95':>8} {'p99':>8} {'n':>5}")
print("-" * 60)

rows = []
for fn in FUNCTIONS:
    for size in ["small", "medium", "large"]:
        sub = df[(df["function"] == fn) & (df["size"] == size)]["latency_ms"]
        if len(sub) == 0:
            continue
        p50 = np.percentile(sub, 50)
        p95 = np.percentile(sub, 95)
        p99 = np.percentile(sub, 99)
        print(f"  {fn:<20} {size:<8} {p50:>8.1f} {p95:>8.1f} {p99:>8.1f} {len(sub):>5}")
        rows.append({
            "function": fn, "size": size,
            "p50_ms": p50, "p95_ms": p95, "p99_ms": p99,
            "n": len(sub),
        })

with open(LATENCY_FILE, "w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["function", "size", "p50_ms", "p95_ms", "p99_ms", "n"])
    writer.writeheader()
    writer.writerows(rows)

print(f"\nPercentiles → {LATENCY_FILE}")
