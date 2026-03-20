import io
import os
import importlib.util
from fastapi import FastAPI, Request, Response
import uvicorn

FUNC_FILE = "trigger.py"
spec = importlib.util.spec_from_file_location("func", FUNC_FILE)
func = importlib.util.module_from_spec(spec)
spec.loader.exec_module(func)

app = FastAPI()

@app.post("/")
async def invoke(request: Request):
    body = await request.body()
    data = io.BytesIO(body)
    result = func.handler(data=data)
    return Response(content=result, media_type="application/json")

@app.post("/noop")
async def noop():
    return Response(
        content='{"status":"success","execution_time_sec":0}',
        media_type="application/json"
    )

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

