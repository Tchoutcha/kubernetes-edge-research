import io
import sys
import json
import time
import logging

def handler(ctx=None, data: io.BytesIO = None):
    """
    FaaS-compatible handler to concatenate and sort strings.
    Input JSON format:
    {
        "text": ["hello", "world"],
        "numIters": 1
    }
    Output JSON format:
    {
        "status": "success",
        "text": "dehllloorw",
        "numIters": 1,
        "execution_time_sec": 0.002
    }
    """
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        strings = body.get("text", [])
        num_iters = body.get("numIters", 1)

        if not all(isinstance(s, str) for s in strings):
            return json.dumps({"status": "error", "error": "Input 'text' must be a list of strings"})

        sorted_chars = ''.join(strings)
        sorted_chars = ''.join(sorted(sorted_chars))

        return json.dumps({
            "status": "success",
            "text": sorted_chars,
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