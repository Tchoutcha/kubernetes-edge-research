import io
import json
import time
import logging
import sys
import numpy as np

_is_cold = True


def handle(matrix_A, matrix_B, iters):
    """
    Multiplication matricielle répétée
    """
    result = None

    for _ in range(iters):
        result = np.matmul(matrix_A, matrix_B)

    return result


def handler(data: io.BytesIO = None):

    global _is_cold

    cold = _is_cold
    _is_cold = False

    total_start = time.time()

    # ─────────────────────────────────────
    # SCHEMA UNIFIÉ GLOBAL
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

        # 3. extraction paramètres
        matrix_A = json.loads(body["matrixA"])
        matrix_B = json.loads(body["matrixB"])
        iters = int(body["iters"])
        t3 = time.time()

        timings["parameter_extraction_sec"] = t3 - t2

        # 4. compute
        result = handle(matrix_A, matrix_B, iters)
        t4 = time.time()

        timings["compute_sec"] = t4 - t3

        # 5. total
        t5 = time.time()
        timings["total_time_sec"] = t5 - total_start

        return json.dumps({
            "status": "success",

            "timings": timings,
            "execution_time_sec": time.time() - total_start,

            "result": {
                "matrix_multiplication_result": result.tolist()
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
