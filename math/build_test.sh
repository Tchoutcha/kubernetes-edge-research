#!/bin/bash

FUNCTION_DIRS=("aggregator" "cosine" "factors" "fast_fourier_transform" "gen_int" "gen_list" "gen_matrix_a" "gen_matrix_b" "linpack" "matrix_multiplication" "sine" "source")
APP_NAME="math"
TEST_PORT=8080
STARTUP_WAIT=3  # seconds to wait for container to be ready

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================"
echo " BUILD AND TEST ALL FUNCTIONS"
echo "============================================"

BUILD_FAILURES=()
TEST_FAILURES=()

# ======================================
# STEP 1 — BUILD ALL IMAGES
# ======================================
echo ""
echo "============================================"
echo " STEP 1: BUILDING ALL IMAGES"
echo "============================================"

for FUNC in "${FUNCTION_DIRS[@]}"; do
    IMAGE_NAME="${APP_NAME}_${FUNC}"

    if [[ ! -d "$FUNC" ]]; then
        echo -e "${RED}❌ Directory $FUNC not found. Skipping.${NC}"
        BUILD_FAILURES+=("$FUNC")
        continue
    fi

    echo ""
    echo "Building: $IMAGE_NAME..."
    if docker build -t "${IMAGE_NAME}:latest" "./${FUNC}"; then
        echo -e "${GREEN}✅ ${IMAGE_NAME} built successfully${NC}"
    else
        echo -e "${RED}❌ ${IMAGE_NAME} build failed${NC}"
        BUILD_FAILURES+=("$FUNC")
    fi
done

# ======================================
# STEP 2 — TEST ALL IMAGES
# ======================================
echo ""
echo "============================================"
echo " STEP 2: TESTING ALL IMAGES"
echo "============================================"

for FUNC in "${FUNCTION_DIRS[@]}"; do
    IMAGE_NAME="${APP_NAME}_${FUNC}"

    # Skip if build failed
    if [[ " ${BUILD_FAILURES[@]} " =~ " ${FUNC} " ]]; then
        echo -e "${YELLOW}⚠️  Skipping test for ${FUNC} (build failed)${NC}"
        continue
    fi

    echo ""
    echo "=============================="
    echo "Testing: ${IMAGE_NAME}"
    echo "=============================="

    # Start container
    CONTAINER_ID=$(docker run -d -p ${TEST_PORT}:8080 "${IMAGE_NAME}:latest")
    if [[ -z "$CONTAINER_ID" ]]; then
        echo -e "${RED}❌ Failed to start container for ${FUNC}${NC}"
        TEST_FAILURES+=("$FUNC")
        continue
    fi
    echo "Container started: $CONTAINER_ID"

    # Wait for FastAPI to be ready
    echo "Waiting ${STARTUP_WAIT}s for startup..."
    sleep $STARTUP_WAIT

    # ---- HEALTH CHECK ----
    echo ""
    echo "  [1/3] Health check..."
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${TEST_PORT}/health)
    if [[ "$HEALTH_RESPONSE" == "200" ]]; then
        echo -e "  ${GREEN}✅ /health OK (HTTP 200)${NC}"
    else
        echo -e "  ${RED}❌ /health failed (HTTP ${HEALTH_RESPONSE})${NC}"
        TEST_FAILURES+=("${FUNC}_health")
    fi

    # ---- NOOP CHECK ----
    echo ""
    echo "  [2/3] Noop check..."
    NOOP_RESPONSE=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d '{}' \
        http://localhost:${TEST_PORT}/noop)
    echo "  Response: $NOOP_RESPONSE"
    if echo "$NOOP_RESPONSE" | jq -e '.status == "success"' > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ /noop OK${NC}"
    else
        echo -e "  ${RED}❌ /noop failed${NC}"
        TEST_FAILURES+=("${FUNC}_noop")
    fi

    # ---- INVOKE WITH SMALL PAYLOAD ----
    echo ""
    echo "  [3/3] Invoke with small payload..."
    PAYLOAD_FILE="./${FUNC}/samples/small/input/input.json"

    if [[ -f "$PAYLOAD_FILE" ]]; then
        PAYLOAD_SIZE=$(stat -c%s "$PAYLOAD_FILE")
        echo "  Payload: $PAYLOAD_FILE (${PAYLOAD_SIZE} bytes)"

        START=$(date +%s%3N)
        INVOKE_RESPONSE=$(curl -s -X POST \
            -H "Content-Type: application/json" \
            -d @"$PAYLOAD_FILE" \
            http://localhost:${TEST_PORT}/)
        END=$(date +%s%3N)
        ELAPSED=$((END - START))

        echo "  Response: $INVOKE_RESPONSE"
        echo "  Time: ${ELAPSED}ms"

        if echo "$INVOKE_RESPONSE" | jq -e '.status == "success"' > /dev/null 2>&1; then
            echo -e "  ${GREEN}✅ /invoke OK (${ELAPSED}ms)${NC}"
        else
            echo -e "  ${RED}❌ /invoke failed${NC}"
            TEST_FAILURES+=("${FUNC}_invoke")
        fi
    else
        echo -e "  ${YELLOW}⚠️  No payload found at $PAYLOAD_FILE — skipping invoke test${NC}"
    fi

    # Stop and remove container
    docker stop "$CONTAINER_ID" > /dev/null
    docker rm "$CONTAINER_ID" > /dev/null
    echo ""
    echo -e "${GREEN}✅ ${FUNC} tests done${NC}"

done

# ======================================
# STEP 3 — SUMMARY
# ======================================
echo ""
echo "============================================"
echo " SUMMARY"
echo "============================================"

if [[ ${#BUILD_FAILURES[@]} -eq 0 ]]; then
    echo -e "${GREEN}✅ All images built successfully${NC}"
else
    echo -e "${RED}❌ Build failures: ${BUILD_FAILURES[*]}${NC}"
fi

if [[ ${#TEST_FAILURES[@]} -eq 0 ]]; then
    echo -e "${GREEN}✅ All tests passed${NC}"
else
    echo -e "${RED}❌ Test failures: ${TEST_FAILURES[*]}${NC}"
fi

echo ""
echo "Done. Ready to import into K3s."