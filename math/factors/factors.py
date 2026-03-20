import io
import json
import math
import time
import logging
import sys


def compute_factors(num: int, req: int):
    factors = []
    for _ in range(req):
        factors = []
        for i in range(1, math.isqrt(num) + 1):
            if num % i == 0:
                factors.append(i)
                if i != num // i:
                    factors.append(num // i)
        factors.sort()
    return factors


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        num = int(body.get("integer", 1))
        req = int(body.get("iters", 1))

        factors = compute_factors(num, req)

        return json.dumps({
            "status": "success",
            "result": {f"Factors of {num}": factors},
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