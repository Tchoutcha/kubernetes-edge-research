import io
import json
import time
import random
import logging
import sys


def generate_seed_iters(body):
    ub = int(body.get('upper_bound', 10))
    seed = int(body.get('seed', random.randrange(10000)))
    iters = int(body.get('iters', 1000))
    return {"seed": seed, "iters": iters, "upper_bound": ub}


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        result = generate_seed_iters(body)

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