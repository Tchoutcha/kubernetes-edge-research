import io
import json
import time
import base64
import sys
import logging
import cv2
import numpy as np


def decode(image_base64: str):
    decoded_image = base64.b64decode(image_base64.encode("utf-8"))
    jpeg_as_np = np.frombuffer(decoded_image, dtype=np.uint8)
    image = cv2.imdecode(jpeg_as_np, flags=1)
    return image


def resize(img):
    return cv2.resize(img, (224, 224))


def encode(image):
    retval, buffer = cv2.imencode(".jpg", image)
    if not retval:
        raise Exception("Image encoding failed")
    return base64.b64encode(buffer).decode("utf-8")


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())

        if "encoded" not in body:
            return json.dumps({"status": "error", "error": "Missing 'encoded' field"})

        image = decode(body["encoded"])
        resized_image = resize(image)
        encoded_result = encode(resized_image)

        return json.dumps({
            "status": "success",
            "result": {"encoded": encoded_result},
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