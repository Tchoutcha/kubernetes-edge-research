#!/bin/bash

FUNCTION_DIRS=("aggregate" "graph_bft" "graph_gen" "graph_mst" "pagerank")

SERVER_PY_TEMPLATE='import io
import os
import importlib.util
from fastapi import FastAPI, Request, Response
import uvicorn

FUNC_FILE = "PLACEHOLDER.py"
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
        content='"'"'{"status":"success","execution_time_sec":0}'"'"',
        media_type="application/json"
    )

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
'

DOCKERFILE_TEMPLATE='FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "server.py"]
'

for FUNC in "${FUNCTION_DIRS[@]}"; do
    echo "=============================="
    echo "Processing: $FUNC"
    echo "=============================="

    if [[ ! -d "$FUNC" ]]; then
        echo "Directory $FUNC not found. Skipping."
        continue
    fi

    # Write server.py with the correct function file name
    echo "${SERVER_PY_TEMPLATE/PLACEHOLDER/$FUNC}" > "$FUNC/server.py"
    echo "  ✅ server.py created with FUNC_FILE=${FUNC}.py"

    # Write Dockerfile
    echo "$DOCKERFILE_TEMPLATE" > "$FUNC/Dockerfile"
    echo "  ✅ Dockerfile updated"

    # Add fastapi and uvicorn to requirements.txt if not already there
    if [[ ! -f "$FUNC/requirements.txt" ]]; then
        touch "$FUNC/requirements.txt"
    fi

    grep -q "fastapi" "$FUNC/requirements.txt" || echo "fastapi" >> "$FUNC/requirements.txt"
    grep -q "uvicorn" "$FUNC/requirements.txt" || echo "uvicorn" >> "$FUNC/requirements.txt"
    echo "  ✅ requirements.txt updated"

    echo "  Done: $FUNC"
done

echo ""
echo "All functions updated. Ready to build."