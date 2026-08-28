import asyncio
import aiohttp
import time
import csv
import json
import numpy as np
import pandas as pd
import argparse
from pathlib import Path
import sys

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
GATEWAY_URL     = "http://131.254.100.72:30333"
NAMESPACE       = "default"
SAMPLES_DIR     = Path("./samples")
MAX_CONCURRENCY = 100
INVOCATION_FILE = "invocation_decomposed.csv"

# 🔥 COLD THRESHOLD (system-based definition)
COLD_THRESHOLD_MS = 1000

# ─────────────────────────────────────────────
# ARGUMENTS
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--workload", type=str, required=True)
parser.add_argument("--verbose", action="store_true")
args = parser.parse_args()

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
in_flight = 0
max_in_flight = 0
lock = asyncio.Lock()
SEM = asyncio.Semaphore(MAX_CONCURRENCY)

payload_cache = {}

# ─────────────────────────────────────────────
# PAYLOAD
# ─────────────────────────────────────────────
def get_payload(fn, size):
    key = (fn, size)
    if key not in payload_cache:
        path = SAMPLES_DIR / fn / "samples" / size / "input" / "input.json"
        try:
            with open(path) as f:
                payload_cache[key] = json.load(f)
        except FileNotFoundError:
            payload_cache[key] = {}
    return payload_cache[key]

# ─────────────────────────────────────────────
# LOAD WORKLOAD
# ─────────────────────────────────────────────
def load_workload(path):
    df = pd.read_csv(path).sort_values("scheduled_time").reset_index(drop=True)

    workload = []
    for _, r in df.iterrows():
        workload.append({
            "t": float(r["scheduled_time"]),
            "function": str(r["function"]),
            "size": str(r["payload_size"]),
            "request_id": int(r["request_id"]),
        })

    print(f"Loaded {len(workload)} requests")
    return workload

# ─────────────────────────────────────────────
# INVOKE
# ─────────────────────────────────────────────
async def invoke(session, idx, req, results):
    global in_flight, max_in_flight

    fn   = req["function"]
    size = req["size"]
    payload = get_payload(fn, size)
    host = f"{fn}.{NAMESPACE}.example.com"

    async with SEM:
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            cur = in_flight

        t_send = time.perf_counter()

        try:
            async with session.post(
                GATEWAY_URL,
                headers={
                    "Host": host,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:

                chunks = []
                t_first = None

                async for c in resp.content.iter_any():
                    if t_first is None:
                        t_first = time.perf_counter()
                    chunks.append(c)

                t_last = time.perf_counter()
                text = b"".join(chunks).decode()

                if t_first is None:
                    t_first = t_last

                # ─────────────────────────────
                # METRICS
                # ─────────────────────────────
                latency_ms = (t_last - t_send) * 1000
                ttfb_ms    = (t_first - t_send) * 1000

                exec_ms = None
                system_ms = None

                try:
                    p = json.loads(text)
                    exec_sec = p.get("execution_time_sec")

                    if exec_sec is not None:
                        exec_ms = exec_sec * 1000
                        system_ms = max(0.0, ttfb_ms - exec_ms)

                except:
                    pass

                # ─────────────────────────────
                # 🔥 COLD DETECTION (SYSTEM ONLY)
                # ─────────────────────────────
                cold = False
                if system_ms is not None:
                    cold = system_ms > COLD_THRESHOLD_MS

                # fallback type
                req_type = "error"
                if resp.status == 200:
                    req_type = "cold" if cold else "warm"

                results[idx] = {
                    "request_id": req["request_id"],
                    "function": fn,
                    "size": size,
                    "type": req_type,
                    "status": resp.status,
                    "latency_ms": round(latency_ms, 2),
                    "ttfb_ms": round(ttfb_ms, 2),
                    "execution_time_ms": round(exec_ms, 2) if exec_ms else None,
                    "system_overhead_ms": round(system_ms, 2) if system_ms else None,
                    "in_flight": cur,
                }

                # ─────────────────────────────
                # LIVE PRINT
                # ─────────────────────────────
                if args.verbose:
                    print(
                        f"[{idx:05d}] {fn:15s} {size:6s} {req_type:6s} "
                        f"| total={latency_ms:8.1f}ms "
                        f"| system={system_ms if system_ms else 0:.1f}ms "
                        f"| exec={exec_ms if exec_ms else 'N/A'} "
                        f"| conc={cur}"
                    )
                    sys.stdout.flush()

        finally:
            async with lock:
                in_flight -= 1

# ─────────────────────────────────────────────
# RUN WORKLOAD
# ─────────────────────────────────────────────
async def run_workload(workload):
    results = [None] * len(workload)

    async with aiohttp.ClientSession() as session:
        t0 = time.perf_counter()

        tasks = []

        for i, req in enumerate(workload):
            target = t0 + req["t"]

            delay = target - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)

            tasks.append(asyncio.create_task(
                invoke(session, i, req, results)
            ))

        await asyncio.gather(*tasks)

    return results

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
print("=" * 60)
print("Loading workload...")

workload = load_workload(args.workload)

for r in workload:
    get_payload(r["function"], r["size"])

print(f"Requests: {len(workload)}")
print("=" * 60)

results = asyncio.run(run_workload(workload))

print(f"\nMax concurrency observed: {max_in_flight}")

# ─────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────
df = pd.DataFrame(results)
df.to_csv(INVOCATION_FILE, index=False)

print(f"Saved: {INVOCATION_FILE}")
