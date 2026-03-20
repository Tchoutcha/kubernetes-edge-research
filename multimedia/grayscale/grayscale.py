import io
import json
import time
import base64
import sys
import logging
from PIL import Image


def rgb_to_grayscale(encoded_image: str) -> str:
    try:
        image_data = base64.b64decode(encoded_image.encode("utf-8"))
        img = Image.open(io.BytesIO(image_data))
        img_grayscale = img.convert("L")
        buf = io.BytesIO()
        img_grayscale.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        raise Exception(f"Grayscale conversion error: {str(e)}")


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())

        if "encoded" not in body:
            return json.dumps({"status": "error", "error": "Missing 'encoded' field"})

        grayscale_image = rgb_to_grayscale(body["encoded"])

        return json.dumps({
            "status": "success",
            "result": {"encoded": grayscale_image},
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