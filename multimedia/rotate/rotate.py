import io
import json
import time
import base64
from PIL import Image
import logging
import sys

def rotate(encoded_image: str):
    image_data = base64.b64decode(encoded_image.encode("utf-8"))
    image_io = io.BytesIO(image_data)
    image = Image.open(image_io)
    rotated_image = image.rotate(-90, expand=True)
    rotated_image_io = io.BytesIO()
    rotated_image.save(rotated_image_io, format="PNG")
    rotated_bytes = rotated_image_io.getvalue()
    return base64.b64encode(rotated_bytes).decode("utf-8")

def handler(ctx=None, data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})
        body = json.loads(data.getvalue())
        if "encoded" not in body:
            return json.dumps({"status": "error", "error": "Missing 'encoded' field"})
        encoded_image = body["encoded"]
        rotated_image = rotate(encoded_image)
        return json.dumps({
            "status": "success",
            "result": {"encoded": rotated_image},
            "execution_time_sec":  round(time.time() - start_time, 6)
        })
    except Exception as e:
        logging.error(str(e))
        return json.dumps({
            "status": "error",
            "error": str(e),
            "execution_time_sec":  round(time.time() - start_time, 6)
        })
    
if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))