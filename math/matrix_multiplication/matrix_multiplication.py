import io
import json
import time
import logging
import sys
import numpy as np


def handle(matrix_A, matrix_B, iters):
    for i in range(iters):
        result = np.matmul(matrix_A, matrix_B)
    return result


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())

        matrix_A = json.loads(body["matrixA"])
        matrix_B = json.loads(body["matrixB"])
        iters = int(body["iters"])

        result = handle(matrix_A, matrix_B, iters)

        return json.dumps({
            "status": "success",
            "result": {
                "matrix_multiplication_result": result.tolist()
            },
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