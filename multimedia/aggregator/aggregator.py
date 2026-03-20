import io
import json
import time
import logging
import sys


def aggregate_json_list(json_list):
    result_body = {}
    for obj in json_list:
        if not isinstance(obj, dict):
            continue
        for key, value in obj.items():
            result_body[key] = value
    return result_body


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        input_list = json.loads(data.getvalue())

        if not isinstance(input_list, list):
            return json.dumps({"status": "error", "error": "Input must be a list of JSON objects"})

        aggregated_result = aggregate_json_list(input_list)

        return json.dumps({
            "status": "success",
            "result": aggregated_result,
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