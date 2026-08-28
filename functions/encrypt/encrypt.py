import io
import sys
import json
import time
import base64
import logging
from pyaes import AESModeOfOperationCTR

KEY = b"\xa1\xf6%\x8c\x87}_\xcd\x89dHE8\xbf\xc9,"

def encryption_handler(message: str, num_of_iterations: int) -> bytes:
    ciphertext = b""
    for _ in range(num_of_iterations):
        aes = AESModeOfOperationCTR(KEY)
        ciphertext = aes.encrypt(message)
    return ciphertext

def handler(ctx=None, data: io.BytesIO = None):
    """
    FaaS-compatible JSON handler for AES encryption.
    Input JSON:
    {
        "text": "<string_to_encrypt>",
        "numIters": <number_of_iterations>
    }
    Output JSON:
    {
        "status": "success",
        "result": {"encrypted_string": "<ciphertext_base64>"},
        "execution_time_sec": <seconds>
    }
    """
    start_time = time.time()
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())

        if "text" not in body or "numIters" not in body:
            return json.dumps({"status": "error", "error": "Missing 'text' or 'numIters' field"})

        text = body["text"]
        num_of_iterations = int(body["numIters"])

        ciphertext = encryption_handler(text, num_of_iterations)
        encrypted_b64 = base64.b64encode(ciphertext).decode("utf-8")

        return json.dumps({
            "status": "success",
            "result": {"encrypted_string": encrypted_b64},
            "execution_time_sec": round(time.time() - start_time, 6)
        })

    except Exception as e:
        logging.error(f"Exception in encryption handler: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "execution_time_sec": round(time.time() - start_time, 6)
        })

if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))