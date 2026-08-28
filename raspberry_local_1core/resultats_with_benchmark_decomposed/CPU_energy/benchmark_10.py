import asyncio
import aiohttp
import time
import csv
import json
import numpy as np
import pandas as pd
import argparse
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
GATEWAY_URL     = "http://131.254.100.72:30333"
NAMESPACE       = "default"
SAMPLES_DIR     = Path("./samples")
MAX_CONCURRENCY = 100
INVOCATION_FILE = "invocation_decomposed.csv"

COLD_THRESHOLD_MS = 1000

# ─────────────────────────────────────────────────────────────
# ARGUMENTS
# ─────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--workload", type=str, required=True)
parser.add_argument("--verbose", action="store_true")
args = parser.parse_args()

# ─────────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────────
in_flight = 0
max_in_flight = 0
lock = asyncio.Lock()
SEM = asyncio.Semaphore(MAX_CONCURRENCY)

payload_cache = {}

# ─────────────────────────────────────────────────────────────
# PAYLOAD
# ─────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────
# LOAD WORKLOAD
# ─────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────
# INVOKE
# ─────────────────────────────────────────────────────────────
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
            current = in_flight

        t_send = time.perf_counter()

        try:
            async with session.post(
                GATEWAY_URL,
                headers={"Host": host, "Content-Type": "application/json"},
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
                text = b"".join(chunks).decode(errors="ignore")

                if t_first is None:
                    t_first = t_last

                latency_ms = (t_last - t_send) * 1000
                ttfb_ms    = (t_first - t_send) * 1000
                out_ms     = (t_last - t_first) * 1000

                # ─────────────────────────────────────
                # SERVER RESPONSE PARSING
                # ─────────────────────────────────────
                exec_ms = None
                system_ms = None
                cold_flag = None

                io_ms = None
                binary_read_ms = None
                json_parsing_ms = None
                param_ms = None
                compute_ms = None
                total_server_ms = None

                try:
                    payload_resp = json.loads(text)

                    exec_sec = payload_resp.get("execution_time_sec")
                    timings = payload_resp.get("timings", {})
                    cold_flag = payload_resp.get("cold_start")

                    if exec_sec is not None:
                        exec_ms = exec_sec * 1000
                        system_ms = max(0.0, ttfb_ms - exec_ms)

                    # FULL TIMINGS
                    io_ms = timings.get("io_sec", 0) * 1000
                    binary_read_ms = timings.get("binary_read_sec", 0) * 1000
                    json_parsing_ms = timings.get("json_parsing_sec", 0) * 1000
                    param_ms = timings.get("parameter_extraction_sec", 0) * 1000
                    compute_ms = timings.get("compute_sec", 0) * 1000
                    total_server_ms = timings.get("total_time_sec", 0) * 1000

                except Exception:
                    pass

                # ─────────────────────────────────────
                # COLD DETECTION
                # ─────────────────────────────────────
                cold_start = False
                if system_ms is not None:
                    cold_start = system_ms > COLD_THRESHOLD_MS

                req_type = "error"
                if resp.status == 200:
                    req_type = "cold" if cold_start else "warm"

                results[idx] = {
                    "index": idx,
                    "request_id": req["request_id"],
                    "function": fn,
                    "size": size,
                    "type": req_type,
                    "status": resp.status,

                    # CLIENT METRICS
                    "latency_ms": round(latency_ms, 2),
                    "ttfb_ms": round(ttfb_ms, 2),
                    "output_transfer_ms": round(out_ms, 2),

                    # SERVER METRICS
                    "execution_time_ms": round(exec_ms, 2) if exec_ms else None,
                    "system_overhead_ms": round(system_ms, 2) if system_ms else None,
                    "cold_start_server": cold_flag,

                    # FULL TIMINGS
                    "io_ms": round(io_ms, 2) if io_ms else None,
                    "binary_read_ms": round(binary_read_ms, 2) if binary_read_ms else None,
                    "json_parsing_ms": round(json_parsing_ms, 2) if json_parsing_ms else None,
                    "parameter_extraction_ms": round(param_ms, 2) if param_ms else None,
                    "compute_ms": round(compute_ms, 2) if compute_ms else None,
                    "total_server_ms": round(total_server_ms, 2) if total_server_ms else None,

                    "in_flight": current,
                }

                # ─────────────────────────────────────
                # VERBOSE OUTPUT
                # ─────────────────────────────────────
                if args.verbose:
                    print(
                        f"[{idx:05d}] {fn:20s} {size:6s} {req_type:6s} "
                        f"| total={latency_ms:7.1f}ms "
                        f"| ttfb={ttfb_ms:7.1f}ms "
                        f"| exec={exec_ms if exec_ms else 'N/A'} "
                        f"| system={system_ms if system_ms else 0:.1f}ms "
                        f"| io={io_ms if io_ms else 0:.1f}ms "
                        f"| compute={compute_ms if compute_ms else 0:.1f}ms "
                        f"| parse={json_parsing_ms if json_parsing_ms else 0:.1f}ms "
                        f"| conc={current}"
                    )
                    sys.stdout.flush()

        finally:
            async with lock:
                in_flight -= 1

# ─────────────────────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────────────────────
async def schedule_request(session, idx, req, t0, results):
    target = t0 + req["t"]

    while True:
        now = time.perf_counter()
        delay = target - now
        if delay <= 0:
            break
        await asyncio.sleep(min(delay, 0.001))

    await invoke(session, idx, req, results)

# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────
async def run(workload):
    results = [None] * len(workload)

    async with aiohttp.ClientSession() as session:
        t0 = time.perf_counter()

        tasks = [
            asyncio.create_task(schedule_request(session, i, req, t0, results))
            for i, req in enumerate(workload)
        ]

        await asyncio.gather(*tasks)

    return results

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
print("Loading workload...")
workload = load_workload(args.workload)

print("Preloading payloads...")
for r in workload:
    get_payload(r["function"], r["size"])

print("Running benchmark...\n")

t_start = time.perf_counter()
results = asyncio.run(run(workload))
print(f"\nDone in {time.perf_counter() - t_start:.2f}s")

# ─────────────────────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────────────────────
valid = [r for r in results if r]

with open(INVOCATION_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=valid[0].keys())
    writer.writeheader()
    writer.writerows(valid)

print("Saved:", INVOCATION_FILE)
