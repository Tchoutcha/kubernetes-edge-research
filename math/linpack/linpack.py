import io
import json
import time
import logging
import sys
import numpy as np
from numpy import linalg


def handle(matrix_A, matrix_B, n, iters):
    mflops = None
    for i in range(iters):
        ops = (2.0 * n) * n * n / 3.0 + (2.0 * n) * n
        start = time.time()
        x = linalg.solve(matrix_A, matrix_B)
        latency = time.time() - start
        mflops = ops * 1e-6 / latency
    return mflops


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())

        matrix_A = json.loads(body["matrixA"])
        matrix_B = json.loads(body["matrixB"])
        size = int(body["size"])
        iters = int(body["iters"])

        mflops = handle(matrix_A, matrix_B, size, iters)

        return json.dumps({
            "status": "success",
            "result": {"linpack_mflops": mflops},
            "execution_time_sec": round(time.time() - start_time, 6)
        })
    except Exception as e:
        logging.error(str(e))
        return json.dumps({
            "status": "error",
            "error": str(e),
            "execution_time_sec": round(time.time() - start_time, 6)
        })


if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))