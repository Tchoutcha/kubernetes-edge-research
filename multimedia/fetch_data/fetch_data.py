import io
import json
import base64
import logging
import time
import sys
import requests


def download_file(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            encoded_image = base64.b64encode(response.content).decode('utf-8')
            return encoded_image
        else:
            logging.info(f"Failed to download image. Status code: {response.status_code}")
            return None
    except Exception as e:
        logging.info(f"An error occurred: {e}")
        return None


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())
        url = body.get("url")

        if not url:
            return json.dumps({"status": "error", "error": "Missing 'url' field"})

        encoded = download_file(url)

        return json.dumps({
            "status": "success",
            "result": {
                "url": url,
                "encoded": encoded
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