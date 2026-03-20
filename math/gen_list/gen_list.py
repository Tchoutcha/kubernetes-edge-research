import io
import json
import time
import logging
import sys
import numpy as np


def generate_random_list(body):
    seed = int(body.get('seed', 0))
    iters = int(body.get('iters', 1))
    np.random.seed(seed)
    param = np.random.rand(10000).tolist()
    return {"list": param, "iters": iters}


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        result = generate_random_list(body)

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