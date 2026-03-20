import io
import json
import time
import base64
import sys
import logging
import os
import numpy as np
import onnxruntime as ort
from PIL import Image
from io import BytesIO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "dependencies", "model", "resnet50v2.onnx")
LABELS_PATH = os.path.join(BASE_DIR, "dependencies", "data", "imagenet_classes.txt")


def decode_base64(data: str):
    img = np.asarray(Image.open(BytesIO(base64.b64decode(data))))[:, :, [2, 1, 0]]
    img = img.transpose((2, 0, 1))
    img = img.reshape(1, 3, 224, 224)
    return img


def preprocess(img_data: np.ndarray) -> np.ndarray:
    mean_vec = np.array([0.485, 0.456, 0.406])
    stddev_vec = np.array([0.229, 0.224, 0.225])
    norm_img_data = np.zeros(img_data.shape).astype("float32")
    for i in range(img_data.shape[0]):
        norm_img_data[i, :, :] = (img_data[i, :, :] / 255 - mean_vec[i]) / stddev_vec[i]
    return norm_img_data


def load_labels(path: str):
    labels = []
    with open(path, "r") as f:
        for line in f:
            labels.append(line.strip())
    return labels


def map_outputs(outputs):
    labels = load_labels(LABELS_PATH)
    return labels[np.argmax(outputs[0])]


def run_model(img: np.ndarray):
    ort_sess = ort.InferenceSession(MODEL_PATH)
    input_name = ort_sess.get_inputs()[0].name
    outputs = ort_sess.run(None, {input_name: img})
    return outputs


def handler(data: io.BytesIO = None):
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())

        if "encoded" not in body:
            return json.dumps({"status": "error", "error": "Missing 'encoded' field"})

        img = decode_base64(body["encoded"])
        img = preprocess(img)
        outputs = run_model(img)
        predicted_class = map_outputs(outputs)

        return json.dumps({
            "status": "success",
            "result": {"resnet": predicted_class},
            "execution_time_sec": round(time.time() - start_time, 6)
        })
    except Exception as e:
        logging.error(f"Exception in handler: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "execution_time_sec": round(time.time() - start_time, 6)
        })


if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))