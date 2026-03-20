import io
import sys
import json
import time
import logging

def handler(ctx=None, data: io.BytesIO = None):
    """
    FaaS-compatible handler for processing a list of text objects.
    Input JSON format:
    [
            {"sortedText": ["text1", "text2"], "numIters": 3},
            {"sortedText": ["text3"], "numIters": 5}
    ]
    Output JSON format:
    {
        "status": "success",
        "text": [["text1", "text2"], ["text3"]],
        "numIters": <last_numIters_value>,
        "execution_time_sec": <seconds>
    }
    """
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        all_texts = []
        last_num_iters = 0

        for obj in body:
            strings = obj.get("sortedText", [])
            last_num_iters = obj.get("numIters", last_num_iters)
            st = [text for text in strings]
            all_texts.append(st)

        return json.dumps({
            "status": "success",
            "text": all_texts,
            "numIters": last_num_iters,
            "execution_time_sec":  round(time.time() - start_time, 6)
        })

    except Exception as e:
        logging.error(f"Exception in handler: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "execution_time_sec":  round(time.time() - start_time, 6)
        })

if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))