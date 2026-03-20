import io
import sys
import json
import time
import random
import string
import logging

def generate_random_lines(num_lines, num_chars):
    """Generate a list of random alphanumeric strings."""
    return [
        ''.join(random.choices(string.ascii_letters + string.digits, k=num_chars))
        for _ in range(num_lines)
    ]

def handler(ctx=None, data: io.BytesIO = None):
    """
    FaaS-compatible JSON handler for generating random text.
    Input JSON:
    {
        "numIters": 1,
        "numLines": 50,
        "numChars": 100
    }
    Output JSON:
    {
        "status": "success",
        "result": {
            "rndText": ["randomstring1", "randomstring2", ...],
            "numIters": 1,
            "numLines": 50,
            "numChars": 100
        },
        "execution_time_sec": 0.02
    }
    """
    start_time = time.time()
    try:
        if not data:
            return json.dumps({
                "status": "error",
                "error": "Empty request body",
                "execution_time_sec": round(time.time() - start_time, 6)
            })

        input_json = json.loads(data.getvalue())

        num_iters = int(input_json.get("numIters", 1))
        num_lines = int(input_json.get("numLines", 100))
        num_chars = int(input_json.get("numChars", 100))

        rnd_text = generate_random_lines(num_lines, num_chars)

        return json.dumps({
            "status": "success",
            "result": {
                "rndText": rnd_text,
                "numIters": num_iters,
                "numLines": num_lines,
                "numChars": num_chars
            },
            "execution_time_sec": round(time.time() - start_time, 6)
        })

    except Exception as e:
        logging.error(f"Exception in random text handler: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "execution_time_sec": round(time.time() - start_time, 6)
        })

if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))