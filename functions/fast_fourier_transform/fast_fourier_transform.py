import io
import json
import time
import logging
import sys
import numpy as np

# cold start flag
_is_cold = True


def handle(iters, x):
    """
    Effectue plusieurs FFT sur le tableau x.
    """
    for _ in range(iters):
        y = np.fft.fft(x)
    return y


def handler(data: io.BytesIO = None):

    global _is_cold

    cold = _is_cold
    _is_cold = False

    total_start = time.time()

    # ─────────────────────────────────────
    # schéma timings UNIFIÉ
    # ─────────────────────────────────────
    timings = {
        "binary_read_sec": 0.0,
        "json_parsing_sec": 0.0,
        "parameter_extraction_sec": 0.0,
        "compute_sec": 0.0,
        "io_sec": 0.0,
        "total_time_sec": 0.0
    }

    try:

        if not data:
            return json.dumps({
                "status": "error",
                "error": "Empty request body",
                "cold_start": cold
            })

        # 1. lecture binaire
        t0 = time.time()
        raw_data = data.getvalue()
        t1 = time.time()

        timings["binary_read_sec"] = t1 - t0

        # 2. parsing json
        body = json.loads(raw_data)
        t2 = time.time()

        timings["json_parsing_sec"] = t2 - t1

        # 3. extraction paramètres
        x = body["list"]
        iters = int(body.get("iters", 1))
        t3 = time.time()

        timings["parameter_extraction_sec"] = t3 - t2

        # 4. compute FFT
        y = handle(iters, x)
        t4 = time.time()

        timings["compute_sec"] = t4 - t3

        # total
        t5 = time.time()
        timings["total_time_sec"] = t5 - total_start

        return json.dumps({
            "status": "success",
            "execution_time_sec": time.time() - total_start,

            "timings": timings,

            "result": {
                "fft_result": str(y)
            },

            "cold_start": cold
        })

    except Exception as e:

        logging.error(str(e))

        return json.dumps({
            "status": "error",
            "error": str(e),
            "cold_start": cold,
            "timings": timings,
            "execution_time_sec": time.time() - total_start
        })


if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))
