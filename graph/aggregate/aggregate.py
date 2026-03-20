import io
import json
import logging
import sys
import time


def handler(data: io.BytesIO = None):
    """
    Processes a list of function results and returns a simplified JSON.
    Input JSON example:
    {
        "objects": [
            {"function": "func1", "result": {...}},
            {"function": "func2", "result": {...}}
        ]
    }
    Output JSON example:
    {
        "status": "success",
        "result": {
            "func1": {...},
            "func2": {...}
        },
        "execution_time_sec": 0.002
    }
    """
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        input_data = json.loads(data.getvalue())
        result_dict = {}
        start_total = time.time()

        for obj in input_data:
            func_name = obj.get("function")
            if not func_name:
                continue
            func_result = obj.get("result")
            result_dict[func_name] = func_result

        total_time = time.time() - start_total

        return json.dumps({
            "status": "success",
            "result": result_dict,
            "execution_time_sec": round(total_time, 6)
        })

    except Exception as e:
        logging.error(str(e))
        return json.dumps({
            "status": "error",
            "error": "Processing error",
            "details": str(e)
        })


if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))