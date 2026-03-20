import io
import sys
import json
import time
import logging

def sorter(lines):
    """Sort each string in the list alphabetically by characters."""
    return [''.join(sorted(line)) for line in lines]

def handler(ctx=None, data: io.BytesIO = None):
    """
    FaaS-compatible JSON handler for sorting the 'rndText' strings.
    Input JSON:
    {
        "_body": {
            "rndText": ["5a1tph4d...", ...],
            "numIters": 100
        }
    }
    Output JSON:
    {
        "status": "success",
        "result": {
            "sortedText": ["1145ad..."],
            "numIters": 100
        },
        "execution_time_sec": 0.02
    }
    """
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        input_json = json.loads(data.getvalue())
        body = input_json.get("_body")

        if not body or "rndText" not in body or "numIters" not in body:
            return json.dumps({"status": "error", "error": "Missing '_body', 'rndText', or 'numIters' field"})

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