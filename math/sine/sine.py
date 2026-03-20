import io
import json
import time
import logging
import sys
from math import sin, pi


def compute_sine(body):
    iterations = int(body.get('iters', 1))
    angle = int(body.get('integer', 0))
    result = None
    for _ in range(iterations):
        for x in range(angle):
            result = sin(x * pi / 180)
    return result


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        result = compute_sine(body)

        return json.dumps({
            "status": "success",
            "result": {f"Sine of {body.get('integer', 0)} degrees": result},
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