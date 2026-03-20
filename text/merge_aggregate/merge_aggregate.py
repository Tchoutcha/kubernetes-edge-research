import io
import sys
import json
import logging
import time

def merge(lists):
    n_pointers = len(lists)
    pointers = [0] * n_pointers
    result = []
    while True:
        min_val = None
        min_val_idx = None
        for i in range(n_pointers):
            if pointers[i] < len(lists[i]):
                if min_val is None or lists[i][pointers[i]] < min_val:
                    min_val = lists[i][pointers[i]]
                    min_val_idx = i
        if min_val_idx is None:
            break
        result.append(min_val)
        pointers[min_val_idx] += 1
    return result

def handler(ctx=None, data: io.BytesIO = None):
    """
    FaaS-compatible handler for merging and sorting lists.
    Input JSON format:
    {
        "text": [[...], [...], ...],
        "iters": <number_of_iterations>
    }
    Output JSON format:
    {
        "status": "success",
        "result": {
            "text": [...],
            "iters": <iters>
        },
        "execution_time_sec": <seconds>
    }
    """
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        lines = body["text"]
        iters = body.get("iters")

        sorted_lines = merge(lines)

        return json.dumps({
            "status": "success",
            "result": {
                "text": sorted_lines,
                "iters": iters
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