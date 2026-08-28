import io
import json
import time
import logging
import sys
import numpy as np
import random

_is_cold = True


def generate_random_matrix(body):
    seed = int(body.get("seed", 0))
    ub = int(body.get("upper_bound", 10))
    iters = int(body.get("iters", 1))

    np.random.seed(seed)
    random_no = random.randint(0, 10000)
    np.random.seed(seed + random_no)

    matrix = np.random.rand(ub, ub)

    return {
        "matrixA": matrix.tolist(),
        "size": ub,
        "iters": iters
    }


def handler(data: io.BytesIO = None):

    global _is_cold

    cold = _is_cold
    _is_cold = False

    total_start = time.time()

    # ─────────────────────────────────────
    # SCHEMA UNIFIÉ
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
                "cold_start": cold,
                "timings": timings
            })

        # 1. lecture binaire
        t0 = time.time()
        raw_data = data.getvalue()
        t1 = time.time()
        timings["binary_read_sec"] = t1 - t0

        # 2. parsing JSON
        body = json.loads(raw_data)
        t2 = time.time()
        timings["json_parsing_sec"] = t2 - t1

        # 3. génération matrice
        result = generate_random_matrix(body)
        t3 = time.time()

        timings["compute_sec"] = t3 - t2

        # 4. total
        t4 = time.time()
        timings["total_time_sec"] = t4 - total_start

        return json.dumps({
            "status": "success",

            "timings": timings,
            "execution_time_sec": time.time() - total_start,

            "result": result,

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
