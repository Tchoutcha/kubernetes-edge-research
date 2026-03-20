import io
import json
import time
import logging
import sys
import numpy as np
import random


def generate_random_matrix(body):
    seed = int(body.get('seed', 0))
    ub = int(body.get('upper_bound', 10))
    iters = int(body.get('iters', 1))

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
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        result = generate_random_matrix(body)

        return json.dumps({
            "status": "success",
            "result": result,
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