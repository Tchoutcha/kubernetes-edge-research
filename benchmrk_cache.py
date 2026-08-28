#!/usr/bin/env python3
"""
Benchmark cache chaud vs cache froid
======================================
Principe : appeler la même fonction de multiplication matricielle
10 fois avec un délai fixe entre chaque appel.

Si le cache est encore chaud → le temps d'exécution reste bas
Si le cache s'est vidé entre deux appels → le temps remonte

Délais testés : 2ms, 10ms, 50ms, 100ms, 200ms, 1000ms
Tailles de matrices : 16x16 (~2KB), 128x128 (~128KB), 512x512 (~2MB)

Résultats sauvegardés dans : cache_results/<machine>/
"""

import time
import json
import platform
import os
import sys

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# =============================================================================
# Configuration
# =============================================================================

DELAYS_MS   = [2, 10, 50, 100, 200, 1000]   # délais en millisecondes
SIZES       = [16, 128, 512]                  # tailles de matrices
REPETITIONS = 10                              # appels par délai

MACHINE = platform.node()
RESULT_DIR = f"./cache_results/{MACHINE}"
os.makedirs(RESULT_DIR, exist_ok=True)

# =============================================================================
# Multiplication matricielle
# =============================================================================

def matmul(A, B):
    if HAS_NUMPY:
        return np.dot(A, B)
    n = len(A)
    C = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for k in range(n):
            a_ik = A[i][k]
            for j in range(n):
                C[i][j] += a_ik * B[k][j]
    return C

def make_matrix(n):
    if HAS_NUMPY:
        return np.full((n, n), 1.5, dtype=np.float64)
    return [[1.5] * n for _ in range(n)]

# =============================================================================
# Benchmark principal
# =============================================================================

def run_series(size, delay_ms, repetitions):
    """
    Lance la multiplication size x size, repetitions fois,
    avec un délai de delay_ms millisecondes entre chaque appel.
    Retourne la liste des temps d'exécution.
    """
    A = make_matrix(size)
    B = make_matrix(size)

    delay_s = delay_ms / 1000.0
    times = []

    for i in range(repetitions):
        # Délai AVANT l'appel (sauf le premier) pour laisser le cache refroidir
        if i > 0:
            time.sleep(delay_s)

        t0 = time.perf_counter()
        matmul(A, B)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)  # en ms

    return times

def stats(times):
    avg = sum(times) / len(times)
    mn  = min(times)
    mx  = max(times)
    var = sum((t - avg) ** 2 for t in times) / len(times)
    std = var ** 0.5
    # Tendance : est-ce que le temps augmente avec les appels ?
    # On compare la moyenne de la 1ère moitié vs 2ème moitié
    mid = len(times) // 2
    trend_first = sum(times[:mid]) / mid
    trend_last  = sum(times[mid:]) / (len(times) - mid)
    trend = trend_last - trend_first  # positif = ça ralentit, négatif = ça s'accélère
    return {
        "avg_ms": round(avg, 6),
        "min_ms": round(mn,  6),
        "max_ms": round(mx,  6),
        "std_ms": round(std, 6),
        "trend_ms": round(trend, 6),  # + = cache refroidit, - = cache chauffe
        "all_ms": [round(t, 6) for t in times],
    }

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":

    # En mode Python pur, 512x512 est trop lent → on réduit
    if not HAS_NUMPY:
        print("[!] numpy non disponible — mode Python pur (matrices réduites)")
        SIZES = [16, 64]
        REPETITIONS = 10

    print("=" * 65)
    print(f"  Benchmark cache chaud/froid — {MACHINE}")
    print(f"  CPU     : {platform.processor() or platform.machine()}")
    print(f"  numpy   : {'oui v' + np.__version__ if HAS_NUMPY else 'non'}")
    print(f"  Délais  : {DELAYS_MS} ms")
    print(f"  Tailles : {SIZES}")
    print(f"  Répétitions par délai : {REPETITIONS}")
    print("=" * 65)

    all_results = []

    for size in SIZES:
        size_kb = round((size * size * 8) / 1024, 1)  # float64 = 8 octets
        print(f"\n  ── Matrice {size}x{size}  ({size_kb} KB) ──────────────────────")

        size_results = []

        for delay_ms in DELAYS_MS:
            print(f"    Délai {delay_ms:>5}ms  ", end="", flush=True)

            times = run_series(size, delay_ms, REPETITIONS)
            s = stats(times)

            # Indicateur visuel de tendance
            if s["trend_ms"] > 0.01:
                trend_icon = "↑ cache refroidit"
            elif s["trend_ms"] < -0.01:
                trend_icon = "↓ cache se chauffe"
            else:
                trend_icon = "→ stable"

            print(f"avg={s['avg_ms']:>8.4f}ms  std={s['std_ms']:>7.4f}ms  {trend_icon}")

            size_results.append({
                "delay_ms":   delay_ms,
                "size":       size,
                "size_kb":    size_kb,
                **s,
            })

        all_results.append({
            "size":    size,
            "size_kb": size_kb,
            "series":  size_results,
        })

    # -------------------------------------------------------------------------
    # Sauvegarde JSON
    # -------------------------------------------------------------------------
    output = {
        "machine":     MACHINE,
        "cpu":         platform.processor() or platform.machine(),
        "python":      sys.version.split()[0],
        "numpy":       np.__version__ if HAS_NUMPY else None,
        "delays_ms":   DELAYS_MS,
        "repetitions": REPETITIONS,
        "results":     all_results,
    }

    out_file = f"{RESULT_DIR}/cache_results_{MACHINE}.json"
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)

    # -------------------------------------------------------------------------
    # Résumé final
    # -------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("  RÉSUMÉ — tendance du cache par taille de matrice")
    print("=" * 65)

    for sr in all_results:
        print(f"\n  Matrice {sr['size']}x{sr['size']} ({sr['size_kb']} KB)")
        print(f"  {'Délai':>8}  {'Avg (ms)':>10}  {'Trend':>10}  {'Interprétation'}")
        print(f"  {'-'*60}")
        for s in sr["series"]:
            if s["trend_ms"] > 0.05:
                interp = "⚠ cache froid détecté"
            elif s["trend_ms"] < -0.05:
                interp = "✓ cache chauffe bien"
            else:
                interp = "  stable"
            print(f"  {s['delay_ms']:>6}ms  {s['avg_ms']:>10.4f}  {s['trend_ms']:>+10.4f}  {interp}")

    print(f"\n  [✓] Résultats sauvegardés : {out_file}")
    print("\n  Pour comparer Raspberry vs serveur :")
    print("  python3 compare_cache.py cache_results_raspberry.json cache_results_serveur.json")
