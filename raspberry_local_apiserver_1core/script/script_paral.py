import asyncio
import aiohttp
import time
import csv
import numpy as np

# -----------------------------
# CONFIGURATION
# -----------------------------
SERVICE_HOST = "helloworld.default.example.com"
SERVICE_URL = "http://131.254.100.72:32340"

TOTAL_REQUESTS = 500
INTERVAL = 0.1 # Intervalle entre requêtes en secondes (~10ms)

LATENCY_FILE = "latency_percentiles.csv"
INVOCATION_FILE = "invocation_times.csv"

# -----------------------------
# Fonction d'invocation asynchrone
# -----------------------------
async def invoke(session, index, results):
    start_time = time.time()
    try:
        async with session.get(SERVICE_URL, headers={"Host": SERVICE_HOST}, timeout=30) as resp:
            elapsed = time.time() - start_time
            results[index] = {
                "latency_s": elapsed,
                "status": resp.status
            }
            print(f"[Req {index}] Status: {resp.status}, latency={elapsed:.3f}s")
    except Exception as e:
        results[index] = {
            "latency_s": None,
            "status": "ERROR"
        }
        print(f"[Req {index}] ERROR: {e}")

# -----------------------------
# Burst contrôlé
# -----------------------------
async def run_controlled_burst():
    results = [None] * TOTAL_REQUESTS

    async with aiohttp.ClientSession() as session:
        start_time = time.time()
        tasks = []

        for i in range(TOTAL_REQUESTS):
            scheduled_time = start_time + i * INTERVAL
            now = time.time()
            sleep_time = scheduled_time - now
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

            task = asyncio.create_task(
                invoke(session, i, results)
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

    return results

# -----------------------------
# Exécution
# -----------------------------
start = time.time()
results = asyncio.run(run_controlled_burst())
total_time = time.time() - start
print(f"\nToutes les {TOTAL_REQUESTS} requêtes envoyées en {total_time:.3f}s")

# -----------------------------
# Sauvegarder invocations
# -----------------------------
with open(INVOCATION_FILE, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["invocation_index", "latency_s", "status"])
    for idx, val in enumerate(results):
        if val is None:
            writer.writerow([idx + 1, "ERROR", "ERROR"])
        else:
            writer.writerow([
                idx + 1,
                val["latency_s"],
                val["status"]
            ])

# -----------------------------
# Calcul des percentiles
# -----------------------------
latencies = [r["latency_s"] for r in results if r is not None]

if latencies:
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)

    with open(LATENCY_FILE, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["p50_s", "p95_s", "p99_s"])
        writer.writerow([p50, p95, p99])

    print("\n--- Latency Percentiles ---")
    print(f"p50: {p50:.3f}s")
    print(f"p95: {p95:.3f}s")
    print(f"p99: {p99:.3f}s")
else:
    print("Aucune invocation réussie.")
