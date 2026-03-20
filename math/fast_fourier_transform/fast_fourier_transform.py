import io
import json
import time
import logging
import sys
import numpy as np


def handle(iters, x):
    for i in range(iters):
        y = np.fft.fft(x)
    return y


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        x = body['list']
        iters = int(body.get('iters', 1))

        y = handle(iters, x)

        return json.dumps({
            "status": "success",
            "result": {
                "Resulting array on performing fft": str(y)
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