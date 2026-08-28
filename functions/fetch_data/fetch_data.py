import io
import json
import base64
import logging
import time
import sys
import requests

_is_cold = True


def download_file(url):
    """
    Télécharge un fichier et retourne base64
    """
    try:
        response = requests.get(url)

        if response.status_code == 200:
            return base64.b64encode(
                response.content
            ).decode("utf-8")

        else:
            logging.info(f"HTTP error: {response.status_code}")
            return None

    except Exception as e:
        logging.info(f"Download error: {e}")
        return None


def handler(data: io.BytesIO = None):

    global _is_cold

    cold = _is_cold
    _is_cold = False

    total_start = time.time()

    # ─────────────────────────────────────
    # SCHEMA UNIFIÉ
    # ─────────────────────────────────────
    timings = {
        "binary_read_sec": 0.0,
        "json_parsing_sec": 0.0,
        "parameter_extraction_sec": 0.0,
        "compute_sec": 0.0,
        "io_sec": 0.0,
        "total_time_sec": 0.0
    }

    try:

        if not data:
            return json.dumps({
                "status": "error",
                "error": "Empty request body",
                "cold_start": cold,
                "timings": timings
            })

        # 1. lecture binaire
        t0 = time.time()
        raw_data = data.getvalue()
        t1 = time.time()
        timings["binary_read_sec"] = t1 - t0

        # 2. parsing JSON
        body = json.loads(raw_data)
        t2 = time.time()
        timings["json_parsing_sec"] = t2 - t1

        # 3. extraction paramètres
        url = body.get("url")
        t3 = time.time()
        timings["parameter_extraction_sec"] = t3 - t2

        if not url:
            return json.dumps({
                "status": "error",
                "error": "Missing 'url' field",
                "cold_start": cold,
                "timings": timings
            })

        # 4. IO (download + base64)
        t4 = time.time()
        encoded = download_file(url)
        t5 = time.time()

        timings["io_sec"] = t5 - t4

        # 5. total
        t6 = time.time()
        timings["total_time_sec"] = t6 - total_start

        return json.dumps({
            "status": "success",

            "timings": timings,
            "execution_time_sec": time.time() - total_start,

            "result": {
                "url": url,
                "encoded": encoded
            },

            "cold_start": cold
        })

    except Exception as e:

        logging.error(str(e))

        return json.dumps({
            "status": "error",
            "error": str(e),

            "cold_start": cold,

            "timings": timings,

            "execution_time_sec": time.time() - total_start
        })


if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))
