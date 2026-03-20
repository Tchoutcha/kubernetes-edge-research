import io
import sys
import json
import time
import random
import logging

def generate_random_lines(n, size):
    characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    lines = [''.join(random.choice(characters) for _ in range(size)) for _ in range(n)]
    return lines

def handler(ctx=None, data: io.BytesIO = None):
    """
    FaaS-compatible handler to generate random strings.
    Input JSON format:
    {
        "numLines": 5,
        "numChars": 10,
        "numIters": 1
    }
    Output JSON format:
    {
        "status": "success",
        "rndText": ["Ab3d...", "..."],
        "numIters": 1,
        "execution_time_sec": 0.001
    }
    """
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        n = body.get("numLines", 1)
        size = body.get("numChars", 8)
        num_iters = body.get("numIters", 1)

        rnd_text = generate_random_lines(n, size)

        return json.dumps({
            "status": "success",
            "rndText": rnd_text,
            "numIters": num_iters,
            "execution_time_sec": round(time.time() - start_time, 6)
        })

    except Exception as e:
        logging.error(f"Exception in handler: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "execution_time_sec": round(time.time() - start_time, 6)
        })

if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))