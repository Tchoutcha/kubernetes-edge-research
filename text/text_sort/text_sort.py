import io
import sys
import json
import time
import logging

def sorter(lines):
    return [sorted(line) for line in lines]

def handler(ctx=None, data: io.BytesIO = None):
    """
    FaaS-compatible JSON handler for sorting text lines.
    Input JSON:
    {
        "rndText": [["c","b","a"], ["z","y","x"]],
        "numIters": <some_number>
    }
    Output JSON:
    {
        "status": "success",
        "result": {
            "sortedText": [["a","b","c"], ["x","y","z"]],
            "numIters": <some_number>
        },
        "execution_time_sec": <seconds>
    }
    """
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())

        if "rndText" not in body or "numIters" not in body:
            return json.dumps({"status": "error", "error": "Missing 'rndText' or 'numIters' field"})

        lines = body["rndText"]
        num_iters = body["numIters"]

        sorted_lines = sorter(lines)

        return json.dumps({
            "status": "success",
            "result": {
                "sortedText": sorted_lines,
                "numIters": num_iters
            },
            "execution_time_sec": round(time.time() - start_time, 6)
        })

    except Exception as e:
        logging.error(f"Exception in sorter handler: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "execution_time_sec": round(time.time() - start_time, 6)
        })

if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))