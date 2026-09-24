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
GATEWAY_URL      = "http://131.254.100.73:31075"
NAMESPACE        = "default"
SAMPLES_DIR      = Path("./samples")
REQUEST_INTERVAL = 0.1
TEST_DURATION    = 180
SEUIL_COLD_MS    = 2000
MAX_CONCURRENT   = 100
INVOCATION_FILE  = "invocation_decomposed.csv"

FUNCTIONS = [
    "fastfouriertransform", "fetchdata", "genmatrix", "grayscale",
    "linpack", "matrixmul", "mobilenet", "pagerank", "resnet", "graphgen",
]

# ─────────────────────────────────────────────────────────────────────────────
# ÉTAT GLOBAL — protégé par lock asyncio
# ─────────────────────────────────────────────────────────────────────────────
in_flight     = 0
max_in_flight = 0
lock          = asyncio.Lock()   # ✅ fix race condition

# ─────────────────────────────────────────────────────────────────────────────
# PRÉCHARGEMENT PAYLOADS
# ─────────────────────────────────────────────────────────────────────────────
payload_cache = {}

def get_payload(fn, size):
    key = (fn, size)
    if key not in payload_cache:
        input_path = SAMPLES_DIR / fn / "samples" / size / "input" / "input.json"
        try:
            with open(input_path) as f:
                payload_cache[key] = json.load(f)
        except FileNotFoundError:
            print(f"[WARN] {input_path} introuvable — payload vide")
            payload_cache[key] = {}
    return payload_cache[key]

# ─────────────────────────────────────────────────────────────────────────────
# WORKLOAD
# ─────────────────────────────────────────────────────────────────────────────
def build_request_list():
    random.seed(42)
    workload = []
    t = 0.0
    while t < TEST_DURATION:
        fn   = random.choice(FUNCTIONS)
        size = random.choice(["small", "medium", "large"])
        workload.append({"t": round(t, 3), "function": fn, "size": size})
        t += REQUEST_INTERVAL
    print(f"Workload : {len(workload)} requêtes | {1/REQUEST_INTERVAL:.0f} req/s\n")
    return workload

# ─────────────────────────────────────────────────────────────────────────────
# SEMAPHORE
# ─────────────────────────────────────────────────────────────────────────────
SEM = asyncio.Semaphore(MAX_CONCURRENT)

# ─────────────────────────────────────────────────────────────────────────────
# INVOCATION
# ─────────────────────────────────────────────────────────────────────────────
async def invoke(session, index, req_info, results):
    global in_flight, max_in_flight

    fn      = req_info["function"]
    size    = req_info["size"]
    payload = get_payload(fn, size)
    host    = f"{fn}.{NAMESPACE}.example.com"

    async with SEM:

        # ✅ incrémente in_flight de façon atomique + capture valeur exacte
        async with lock:
            in_flight += 1
            max_in_flight    = max(max_in_flight, in_flight)
            current_in_flight = in_flight   # valeur exacte au moment du send

        t_send = time.perf_counter()  # ✅ haute résolution, insensible NTP

        try:
            async with session.post(
                GATEWAY_URL,
                headers={"Host": host, "Content-Type": "application/json"},
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:

                # ── Lecture chunk par chunk ────────────────────────────────
                chunks       = []
                t_first_byte = None

                async for chunk in resp.content.iter_any():
                    if t_first_byte is None:
                        t_first_byte = time.perf_counter()  # ✅
                    chunks.append(chunk)

                t_last_byte = time.perf_counter()  # ✅
                text = b"".join(chunks).decode()

                if t_first_byte is None:
                    t_first_byte = t_last_byte  # fallback si body vide

                # ── Tout en ms ────────────────────────────────────────────
                latency_ms         = (t_last_byte  - t_send)       * 1000
                time_to_first_byte = (t_first_byte - t_send)       * 1000
                output_transfer_ms = (t_last_byte  - t_first_byte) * 1000

                # ── Détection erreur HTTP ✅ ───────────────────────────────
                if resp.status != 200:
                    results[index] = {
                        "index": index, "function": fn, "size": size,
                        "type": "error", "status": resp.status,
                        "latency_ms": round(latency_ms, 2),
                        "time_to_first_byte_ms": round(time_to_first_byte, 2),
                        "output_transfer_ms": round(output_transfer_ms, 2),
                        "execution_time_ms": None, "system_overhead_ms": None,
                        "in_flight_at_send": current_in_flight,
                    }
                    print(f"[{index:04d}] {fn:22s} {size:6s} HTTP {resp.status} "
                          f"| total={latency_ms:8.1f}ms")
                    return

                # ── Parsing réponse ────────────────────────────────────────
                exec_time_ms       = None
                system_overhead_ms = None
                type_req           = "cold" if latency_ms > SEUIL_COLD_MS else "warm"

                try:
                    payload_resp = json.loads(text)

                    exec_sec = payload_resp.get("execution_time_sec", None)
                    if exec_sec is not None:
                        exec_time_ms = exec_sec * 1000

                    if "cold_start" in payload_resp:
                        type_req = "cold" if payload_resp["cold_start"] else "warm"

                    if exec_time_ms is not None:
                        # ✅ max(0, ...) évite les valeurs négatives
                        system_overhead_ms = max(0.0, time_to_first_byte - exec_time_ms)

                except Exception:
                    pass

                results[index] = {
                    "index":                 index,
                    "function":              fn,
                    "size":                  size,
                    "type":                  type_req,
                    "status":                resp.status,
                    "latency_ms":            round(latency_ms, 2),
                    "time_to_first_byte_ms": round(time_to_first_byte, 2),
                    "output_transfer_ms":    round(output_transfer_ms, 2),
                    "execution_time_ms":     round(exec_time_ms, 2)       if exec_time_ms       is not None else None,
                    "system_overhead_ms":    round(system_overhead_ms, 2) if system_overhead_ms is not None else None,
                    "in_flight_at_send":     current_in_flight,
                }

                exec_str = f"{exec_time_ms:.1f}ms" if exec_time_ms is not None else "N/A"
                sys_str  = f"{system_overhead_ms:.1f}ms" if system_overhead_ms is not None else "N/A"

                print(f"[{index:04d}] {fn:22s} {size:6s} {type_req:4s} "
                      f"| total={latency_ms:8.1f}ms "
                      f"| TTFB={time_to_first_byte:8.1f}ms "
                      f"| exec={exec_str:>10} "
                      f"| sys={sys_str:>10} "
                      f"| out={output_transfer_ms:6.2f}ms "
                      f"| conc={current_in_flight}")

        except Exception as e:
            results[index] = {
                "index": index, "function": fn, "size": size,
                "type": "error", "status": "ERROR",
                "latency_ms": None, "time_to_first_byte_ms": None,
                "output_transfer_ms": None, "execution_time_ms": None,
                "system_overhead_ms": None, "in_flight_at_send": current_in_flight,
            }
            print(f"[{index:04d}] {fn:22s} {size:6s} ERROR: {e}")

        finally:
            # ✅ décrémente atomique dans finally
            async with lock:
                in_flight -= 1

# ─────────────────────────────────────────────────────────────────────────────
# REPLAY — rate control précis
# ─────────────────────────────────────────────────────────────────────────────
async def run_workload(requests_list):
    results = [None] * len(requests_list)

    async with aiohttp.ClientSession() as session:
        t0    = time.perf_counter()  # ✅
        tasks = []

        for i, req_info in enumerate(requests_list):
            # Rate control basé sur temps absolu — minimise la dérive
            target = t0 + req_info["t"]
            delay  = target - time.perf_counter()  # ✅
            if delay > 0:
                await asyncio.sleep(delay)
            tasks.append(asyncio.create_task(
                invoke(session, i, req_info, results)
            ))

        await asyncio.gather(*tasks)

    return results

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 70)
print("Préchargement des payloads...")
for fn in FUNCTIONS:
    for size in ["small", "medium", "large"]:
        get_payload(fn, size)
print(f"Cache : {len(payload_cache)} payloads chargés")
print("=" * 70)

requests_list = build_request_list()
print("=" * 70)

t_start    = time.perf_counter()  # ✅
results    = asyncio.run(run_workload(requests_list))
total_time = time.perf_counter() - t_start

throughput = len(results) / total_time
print(f"\nTerminé en {total_time:.1f}s | throughput réel = {throughput:.1f} req/s")
print(f"Concurrence max observée (offered load) = {max_in_flight} req simultanées")
print(f"Note: in_flight = offered load côté client, pas effective concurrency cluster\n")

# ─────────────────────────────────────────────────────────────────────────────
# SAVE CSV
# ─────────────────────────────────────────────────────────────────────────────
valid = [r for r in results if r is not None]

fieldnames = [
    "index", "function", "size", "type", "status",
    "latency_ms", "time_to_first_byte_ms", "output_transfer_ms",
    "execution_time_ms", "system_overhead_ms", "in_flight_at_send",
]

with open(INVOCATION_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(valid)

print(f"✓ Saved: {INVOCATION_FILE}")

# ─────────────────────────────────────────────────────────────────────────────
# STATS — uniquement status=200 ✅
# ─────────────────────────────────────────────────────────────────────────────
df = pd.DataFrame(valid)

# ✅ exclure erreurs HTTP et exceptions
n_total  = len(df)
df       = df[df["status"] == 200]
n_errors = n_total - len(df)
print(f"\nRequêtes totales : {n_total} | OK : {len(df)} | Erreurs : {n_errors}")

METRICS = [
    ("latency_ms",            "End-to-end        "),
    ("time_to_first_byte_ms", "Time to 1st byte  "),
    ("execution_time_ms",     "Execution time     "),
    ("system_overhead_ms",    "System overhead    "),
    ("output_transfer_ms",    "Output transfer ⚠️ "),
]

for req_type in ["cold", "warm"]:
    sub = df[df["type"] == req_type]
    if len(sub) == 0:
        continue

    print(f"\n{'='*70}")
    print(f"  {req_type.upper()} — global (n={len(sub)})")
    print(f"{'='*70}")
    print(f"  {'Métrique':<25} {'p50':>10} {'p90':>10} {'p95':>10} {'p99':>10}  (ms)")
    print(f"  {'-'*65}")
    for col, label in METRICS:
        s = pd.to_numeric(sub[col], errors="coerce").dropna()
        if len(s) == 0:
            continue
        print(f"  {label} "
              f"{np.percentile(s,50):>10.1f} "
              f"{np.percentile(s,90):>10.1f} "
              f"{np.percentile(s,95):>10.1f} "
              f"{np.percentile(s,99):>10.1f}")

    # ── Stats par fonction ─────────────────────────────────────────────
    print(f"\n── {req_type.upper()} — par fonction ──")
    print(f"  {'Function':<25} {'n':>6} {'p50':>10} {'p95':>10} {'p99':>10}  (ms)")
    print(f"  {'-'*65}")
    for fn in sorted(df["function"].unique()):
        fn_sub = pd.to_numeric(sub[sub["function"] == fn]["latency_ms"],
                               errors="coerce").dropna()
        if len(fn_sub) == 0:
            continue
        print(f"  {fn:<25} {len(fn_sub):>6} "
              f"{np.percentile(fn_sub,50):>10.1f} "
              f"{np.percentile(fn_sub,95):>10.1f} "
              f"{np.percentile(fn_sub,99):>10.1f}")

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSE SATURATION — latence vs concurrence ✅
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n── Courbe de saturation — latency_ms médian vs in_flight ──")
print(f"  {'in_flight':>10} {'n':>8} {'p50_lat':>12} {'p95_lat':>12}  (ms)")
print(f"  {'-'*50}")

sat = df[df["type"] == "warm"].copy()
sat["in_flight_bucket"] = pd.cut(
    sat["in_flight_at_send"],
    bins=[0,1,2,3,5,10,20,50,100],
    labels=["1","2","3","4-5","6-10","11-20","21-50","51-100"]
)
for bucket, grp in sat.groupby("in_flight_bucket", observed=True):
    lat = pd.to_numeric(grp["latency_ms"], errors="coerce").dropna()
    if len(lat) == 0:
        continue
    print(f"  {str(bucket):>10} {len(lat):>8} "
          f"{np.percentile(lat,50):>12.1f} "
          f"{np.percentile(lat,95):>12.1f}")
