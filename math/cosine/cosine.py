import io
import json
import time
import sys
import logging
from math import cos, pi


def compute_cosine(iterations: int, angle: int):
    result = None
    for _ in range(iterations):
        for x in range(angle):
            result = cos(x * pi / 180)
    return result


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        iterations = int(body.get("iters", 1))
        angle = int(body.get("integer", 0))

        result = compute_cosine(iterations, angle)

        return json.dumps({
            "status": "success",
            "result": {f"Cosine of {angle} degrees": result},
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