#!/bin/bash

# Source structure: <app>/<function>/samples/<payload>/input/input.json
# Destination:      data/<app>/<function>/samples/<payload>/input/input.json

APPS=("graph" "math" "multimedia" "text")
DATA_DIR="./data"
FOUND=0
MISSING=()

echo "Collecting all sample payloads into ${DATA_DIR}..."
mkdir -p "${DATA_DIR}"

for APP in "${APPS[@]}"; do
    if [[ ! -d "./${APP}" ]]; then
        echo "⚠️  App directory ./${APP} not found. Skipping."
        continue
    fi

    # Loop over each function inside the app
    for FUNC_PATH in "./${APP}"/*/; do
        FUNC=$(basename "$FUNC_PATH")
        SAMPLES_DIR="${FUNC_PATH}samples"

        if [[ ! -d "$SAMPLES_DIR" ]]; then
            continue
        fi


        DEST_DIR="${DATA_DIR}/${APP}/${FUNC}/"
        mkdir -p "${DEST_DIR}"
        cp -r "$SAMPLES_DIR" "${DEST_DIR}/samples"
        echo "✅ ${APP}/${FUNC}/samples"
        ((FOUND++))

    done
done

# Summary
echo ""
echo "============================================"
echo " SUMMARY"
echo "============================================"
echo "Payloads collected : ${FOUND}"
echo "Missing payloads   : ${#MISSING[@]}"

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo ""
    echo "⚠️  Missing:"
    for M in "${MISSING[@]}"; do
        echo "   - $M"
    done
fi

echo ""
echo "Final data structure:"
find "${DATA_DIR}" -name "input.json" | sort

echo ""
echo "Transfer to Grid5000:"
echo "   scp -r ./data your_username@access.grid5000.fr:~/data"