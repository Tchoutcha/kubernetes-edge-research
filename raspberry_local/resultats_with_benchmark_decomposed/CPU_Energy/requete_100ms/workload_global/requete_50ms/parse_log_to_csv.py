import re
import csv
import sys

# Usage: python parse_log_to_csv.py log.txt output.csv

infile  = sys.argv[1] if len(sys.argv) > 1 else "log.txt"
outfile = sys.argv[2] if len(sys.argv) > 2 else "invocation_decomposed.csv"

pattern_ok = re.compile(
    r'\[(\d+)\]\s+(\S+)\s+(\S+)\s+(\S+)\s+\|'
    r'\s+total=\s*([\d.]+)ms\s+\|'
    r'\s+TTFB=\s*([\d.]+)ms\s+\|'
    r'\s+exec=\s*([\d.]+)ms\s+\|'
    r'\s+sys=\s*([\d.]+)ms\s+\|'
    r'\s+out=\s*([\d.]+)ms\s+\|'
    r'\s+conc=(\d+)'
)

pattern_err = re.compile(
    r'\[(\d+)\]\s+(\S+)\s+(\S+)\s+(HTTP \d+)\s+\|\s+total=\s*([\d.]+)ms'
)

fieldnames = [
    'index', 'function', 'size', 'type', 'status',
    'latency_ms', 'time_to_first_byte_ms', 'output_transfer_ms',
    'execution_time_ms', 'system_overhead_ms', 'in_flight_at_send',
]

rows = []
with open(infile, encoding='utf-8', errors='ignore') as f:
    for line in f:
        line = line.strip()
        m = pattern_ok.search(line)
        if m:
            idx, fn, size, typ, total, ttfb, exc, sys_, out, conc = m.groups()
            rows.append({
                'index':                 int(idx),
                'function':              fn,
                'size':                  size,
                'type':                  typ,
                'status':                200,
                'latency_ms':            float(total),
                'time_to_first_byte_ms': float(ttfb),
                'output_transfer_ms':    float(out),
                'execution_time_ms':     float(exc),
                'system_overhead_ms':    float(sys_),
                'in_flight_at_send':     int(conc),
            })
            continue
        m2 = pattern_err.search(line)
        if m2:
            idx, fn, size, status, total = m2.groups()
            rows.append({
                'index':                 int(idx),
                'function':              fn,
                'size':                  size,
                'type':                  'error',
                'status':                status,
                'latency_ms':            float(total),
                'time_to_first_byte_ms': None,
                'output_transfer_ms':    None,
                'execution_time_ms':     None,
                'system_overhead_ms':    None,
                'in_flight_at_send':     None,
            })

# Trier par index
rows.sort(key=lambda r: r['index'])

with open(outfile, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f"✓ {len(rows)} lignes écrites → {outfile}")
