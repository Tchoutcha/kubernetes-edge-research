import io
import json
import time
import logging
import sys
import numpy as np


def generate(body):
    seed = int(body['seed'])
    iters = int(body['iters'])
    np.random.seed(seed)
    param = np.random.randint(10000)
    return {
        'integer': int(param),
        'iters': iters
    }


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        result = generate(body)

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