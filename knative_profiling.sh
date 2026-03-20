#!/bin/bash

# ============================================
# KNATIVE PROFILING SCRIPT — ALL FUNCTIONS
# Run one group at a time: graph, math, multimedia, text
# One CSV per group
# ============================================

# --- GLOBAL CONFIGURATION ---
DOCKERHUB_USERNAME="arjiba"
REPO="profiling"
DOCKERHUB_SECRET="dockerhub-secret"
NAMESPACE="default"
DATA_DIR="./Profiling/"
RESULTS_DIR="./Profiling/results"
WARM_ITERATIONS=10
MEMORY_LIMITS=("128Mi" "256Mi" "512Mi")
CPU_LIMITS=("500m" "1000m" "1500m" "2000m")
PAYLOADS=("small" "medium" "large")

# --- NETWORKING ---
DOMAIN=$(kubectl get configmap config-domain -n knative-serving -o jsonpath='{.data}' | jq -r 'keys[0]')
KOURIER_IP=$(kubectl get svc kourier -n kourier-system -o jsonpath='{.spec.clusterIP}')

# --- FUNCTION GROUPS ---
declare -A GROUPS
GROUPS["graph"]="aggregate graph_bft graph_gen graph_mst pagerank"
GROUPS["math"]="aggregator cosine factors fast_fourier_transform gen_int gen_list gen_matrix_a gen_matrix_b linpack matrix_multiplication sine source"
GROUPS["multimedia"]="aggregator alexnet fetch_data flip grayscale mobilenet resize resnet rotate"
GROUPS["text"]="aggregate_lines encrypt merge_aggregate single_string text_data_gen text_sort textsort1 trigger"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

mkdir -p "${RESULTS_DIR}"

# ============================================
# HELPER — wait for pod to be running
# ============================================
wait_for_pod() {
    local SERVICE=$1
    echo "Waiting for pod ${SERVICE} to be running..."
    for i in $(seq 1 60); do
        POD_STATUS=$(kubectl get pods -n ${NAMESPACE} \
            -l serving.knative.dev/service=${SERVICE} \
            --field-selector=status.phase=Running \
            -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        if [[ -n "$POD_STATUS" ]]; then
            echo -e "${GREEN}✅ Pod running: $POD_STATUS${NC}"
            sleep 2
            return 0
        fi
        sleep 2
    done
    echo -e "${RED}❌ Pod never became ready for ${SERVICE}${NC}"
    return 1
}

# ============================================
# HELPER — get pod metrics
# ============================================
get_pod_metrics() {
    local SERVICE=$1
    POD_NAME=$(kubectl get pods -n ${NAMESPACE} \
        -l serving.knative.dev/service=${SERVICE} \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [[ -z "$POD_NAME" ]]; then
        echo "0 0"
        return
    fi
    METRICS=$(kubectl top pod "$POD_NAME" -n ${NAMESPACE} --no-headers 2>/dev/null)
    CPU=$(echo "$METRICS" | awk '{print $2}' | sed 's/m//')
    MEM=$(echo "$METRICS" | awk '{print $3}' | sed 's/Mi//')
    CPU=${CPU:-0}
    MEM=${MEM:-0}
    echo "$CPU $MEM"
}

# ============================================
# HELPER — scale to zero
# ============================================
scale_to_zero() {
    local SERVICE=$1
    echo "Scaling ${SERVICE} to zero..."
    LATEST_REVISION=$(kubectl get revision -n ${NAMESPACE} \
        -l serving.knative.dev/service=${SERVICE} \
        --sort-by=.metadata.creationTimestamp \
        -o jsonpath='{.items[-1].metadata.name}' 2>/dev/null)

    if [[ -n "$LATEST_REVISION" ]]; then
        kubectl annotate revision -n ${NAMESPACE} \
            "${LATEST_REVISION}" \
            autoscaling.knative.dev/minScale=0 --overwrite 2>/dev/null
    fi

    for i in $(seq 1 30); do
        POD_COUNT=$(kubectl get pods -n ${NAMESPACE} \
            -l serving.knative.dev/service=${SERVICE} \
            --field-selector=status.phase=Running \
            --no-headers 2>/dev/null | wc -l)
        if [[ "$POD_COUNT" -eq 0 ]]; then
            echo -e "${GREEN}✅ Scaled to zero${NC}"
            return 0
        fi
        sleep 3
    done
    echo -e "${YELLOW}⚠️  Could not confirm scale to zero, continuing anyway${NC}"
}

# ============================================
# HELPER — patch resources
# ============================================
patch_resources() {
    local SERVICE=$1
    local IMAGE=$2
    local CPU=$3
    local MEM=$4
    echo "Patching ${SERVICE}: CPU=${CPU} MEM=${MEM}..."
    kubectl patch ksvc ${SERVICE} -n ${NAMESPACE} --type merge -p \
    "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"autoscaling.knative.dev/minScale\":\"0\",\"autoscaling.knative.dev/maxScale\":\"1\"}},\"spec\":{\"containers\":[{\"name\":\"user-container\",\"image\":\"${IMAGE}\",\"securityContext\":{\"allowPrivilegeEscalation\":false,\"runAsNonRoot\":false,\"capabilities\":{\"drop\":[\"ALL\"]},\"seccompProfile\":{\"type\":\"RuntimeDefault\"}},\"resources\":{\"requests\":{\"memory\":\"${MEM}\",\"cpu\":\"${CPU}\"},\"limits\":{\"memory\":\"${MEM}\",\"cpu\":\"${CPU}\"}}}]}}}}" 2>/dev/null

    kubectl wait --for=condition=Ready ksvc/${SERVICE} -n ${NAMESPACE} --timeout=120s
}

# ============================================
# HELPER — deploy function if not exists
# ============================================
deploy_function() {
    local SERVICE=$1
    local IMAGE=$2

    if kubectl get ksvc ${SERVICE} -n ${NAMESPACE} > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  ${SERVICE} already exists, skipping deploy${NC}"
        return 0
    fi

    echo "Deploying ${SERVICE} from ${IMAGE}..."
    kubectl apply -f - <<EOF
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ${SERVICE}
  namespace: ${NAMESPACE}
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"
        autoscaling.knative.dev/maxScale: "1"
    spec:
      imagePullSecrets:
        - name: ${DOCKERHUB_SECRET}
      containers:
        - image: ${IMAGE}
          imagePullPolicy: Always
          ports:
            - containerPort: 8080
          securityContext:
            allowPrivilegeEscalation: false
            runAsNonRoot: false
            capabilities:
              drop:
                - ALL
            seccompProfile:
              type: RuntimeDefault
          resources:
            requests:
              memory: "128Mi"
              cpu: "500m"
            limits:
              memory: "128Mi"
              cpu: "500m"
EOF
    kubectl wait --for=condition=Ready ksvc/${SERVICE} -n ${NAMESPACE} --timeout=120s
    echo -e "${GREEN}✅ ${SERVICE} deployed${NC}"
}

# ============================================
# HELPER — profile one function
# ============================================
profile_function() {
    local GROUP=$1
    local FUNC=$2
    local SERVICE="${GROUP}-${FUNC}"
    local IMAGE="${DOCKERHUB_USERNAME}/${REPO}:${GROUP}_${FUNC}"
    local FUNC_DATA_DIR="${DATA_DIR}/${GROUP}/${FUNC}/samples"
    local OUTPUT_CSV=$3

    echo ""
    echo -e "${MAGENTA}============================================${NC}"
    echo -e "${MAGENTA} FUNCTION: ${SERVICE}${NC}"
    echo -e "${MAGENTA}============================================${NC}"

    # Deploy if needed
    deploy_function "${SERVICE}" "${IMAGE}"
    if [[ $? -ne 0 ]]; then
        echo -e "${RED}❌ Failed to deploy ${SERVICE}. Skipping.${NC}"
        return 1
    fi

    # Loop over CPU and memory configurations
    for CPU_LIMIT in "${CPU_LIMITS[@]}"; do
        for MEMORY in "${MEMORY_LIMITS[@]}"; do

            echo ""
            echo -e "${CYAN}--- CPU: ${CPU_LIMIT} | MEMORY: ${MEMORY} ---${NC}"

            # Patch resources
            patch_resources "${SERVICE}" "${IMAGE}" "${CPU_LIMIT}" "${MEMORY}"

            # ==================================
            # COLD START — small payload only
            # ==================================
            COLD_PAYLOAD_FILE="${FUNC_DATA_DIR}/small/input/input.json"

            if [[ ! -f "$COLD_PAYLOAD_FILE" ]]; then
                echo -e "${RED}❌ Cold payload not found: $COLD_PAYLOAD_FILE. Skipping.${NC}"
                continue
            fi

            scale_to_zero "${SERVICE}"
            sleep 5

            echo "Cold start..."
            START=$(date +%s%3N)
            OUTPUT=$(curl -s -X POST \
                -H "Host: ${SERVICE}.${NAMESPACE}.${DOMAIN}" \
                -H "Content-Type: application/json" \
                -d @"${COLD_PAYLOAD_FILE}" \
                http://${KOURIER_IP})
            END=$(date +%s%3N)

            COLD_TOTAL_MS=$(echo "scale=3; ($END - $START)" | bc)
            EXEC_TIME_COLD=$(echo "$OUTPUT" | jq -r 'select(.status=="success") | .execution_time_sec // "0"' 2>/dev/null)
            EXEC_TIME_COLD=${EXEC_TIME_COLD:-0}
            COLD_EXEC_MS=$(echo "scale=3; $EXEC_TIME_COLD * 1000" | bc)
            COLD_START_MS=$(echo "scale=3; $COLD_TOTAL_MS - $COLD_EXEC_MS" | bc)

            echo -e "  Cold total : ${COLD_TOTAL_MS}ms"
            echo -e "  Cold start : ${COLD_START_MS}ms"
            echo -e "  Cold exec  : ${COLD_EXEC_MS}ms"

            # ==================================
            # WARM START — all payloads
            # ==================================

            # Start background metrics sampler
            CPU_LOG=$(mktemp)
            MEM_LOG=$(mktemp)
            (
                while true; do
                    read -r CPU_VAL MEM_VAL <<< $(get_pod_metrics "${SERVICE}")
                    [[ "$CPU_VAL" -gt 0 ]] && echo "$CPU_VAL" >> "$CPU_LOG"
                    [[ "$MEM_VAL" -gt 0 ]] && echo "$MEM_VAL" >> "$MEM_LOG"
                    sleep 2
                done
            ) &
            SAMPLER_PID=$!

            for PAYLOAD in "${PAYLOADS[@]}"; do
                PAYLOAD_FILE="${FUNC_DATA_DIR}/${PAYLOAD}/input/input.json"

                if [[ ! -f "$PAYLOAD_FILE" ]]; then
                    echo -e "${YELLOW}⚠️  Payload not found: $PAYLOAD_FILE. Skipping.${NC}"
                    continue
                fi

                PAYLOAD_SIZE_MB=$(stat -c%s "$PAYLOAD_FILE" | awk '{printf "%.6f", $1/1024/1024}')
                echo ""
                echo "Warm payload: ${PAYLOAD} (${PAYLOAD_SIZE_MB}MB)"

                TOTAL_WARM_SUM=0
                EXEC_WARM_SUM=0
                OUTPUT_SIZE_SUM=0

                for ((i=1; i<=WARM_ITERATIONS; i++)); do
                    START=$(date +%s%3N)
                    OUTPUT=$(curl -s -X POST \
                        -H "Host: ${SERVICE}.${NAMESPACE}.${DOMAIN}" \
                        -H "Content-Type: application/json" \
                        -d @"${PAYLOAD_FILE}" \
                        http://${KOURIER_IP})
                    END=$(date +%s%3N)

                    ITER_TOTAL_MS=$(echo "scale=3; ($END - $START)" | bc)
                    ITER_EXEC=$(echo "$OUTPUT" | jq -r 'select(.status=="success") | .execution_time_sec // "0"' 2>/dev/null)
                    ITER_EXEC=${ITER_EXEC:-0}
                    ITER_EXEC_MS=$(echo "scale=3; $ITER_EXEC * 1000" | bc)
                    ITER_OUTPUT_SIZE=$(echo "$OUTPUT" | wc -c | awk '{printf "%.6f", $1/1024/1024}')

                    TOTAL_WARM_SUM=$(echo "scale=3; $TOTAL_WARM_SUM + $ITER_TOTAL_MS" | bc)
                    EXEC_WARM_SUM=$(echo "scale=3; $EXEC_WARM_SUM + $ITER_EXEC_MS" | bc)
                    OUTPUT_SIZE_SUM=$(echo "scale=6; $OUTPUT_SIZE_SUM + $ITER_OUTPUT_SIZE" | bc)

                    echo "  Iter ${i}: total=${ITER_TOTAL_MS}ms exec=${ITER_EXEC_MS}ms"
                done

                # Stop sampler and compute averages
                kill $SAMPLER_PID 2>/dev/null
                wait $SAMPLER_PID 2>/dev/null

                AVG_TOTAL_MS=$(echo "scale=3; $TOTAL_WARM_SUM / $WARM_ITERATIONS" | bc)
                AVG_EXEC_MS=$(echo "scale=3; $EXEC_WARM_SUM / $WARM_ITERATIONS" | bc)
                AVG_START_MS=$(echo "scale=3; $AVG_TOTAL_MS - $AVG_EXEC_MS" | bc)
                AVG_OUTPUT_SIZE=$(echo "scale=6; $OUTPUT_SIZE_SUM / $WARM_ITERATIONS" | bc)
                AVG_CPU=$(awk '{sum+=$1; count++} END {if(count>0) printf "%.3f", sum/count; else print "0"}' "$CPU_LOG" 2>/dev/null)
                AVG_MEM=$(awk '{sum+=$1; count++} END {if(count>0) printf "%.3f", sum/count; else print "0"}' "$MEM_LOG" 2>/dev/null)
                AVG_CPU=${AVG_CPU:-0}
                AVG_MEM=${AVG_MEM:-0}

                echo -e "  ${GREEN}Avg total  : ${AVG_TOTAL_MS}ms${NC}"
                echo -e "  ${GREEN}Avg exec   : ${AVG_EXEC_MS}ms${NC}"
                echo -e "  ${GREEN}Avg start  : ${AVG_START_MS}ms${NC}"
                echo -e "  ${GREEN}Avg CPU    : ${AVG_CPU}m${NC}"
                echo -e "  ${GREEN}Avg memory : ${AVG_MEM}Mi${NC}"

                # Write to CSV
                echo "${GROUP},${FUNC},${CPU_LIMIT},${MEMORY},${PAYLOAD},${PAYLOAD_SIZE_MB},${AVG_OUTPUT_SIZE},${COLD_TOTAL_MS},${COLD_START_MS},${COLD_EXEC_MS},${AVG_TOTAL_MS},${AVG_EXEC_MS},${AVG_START_MS},${AVG_CPU},${AVG_MEM},${WARM_ITERATIONS}" >> "$OUTPUT_CSV"

                # Restart sampler for next payload
                > "$CPU_LOG"
                > "$MEM_LOG"
                (
                    while true; do
                        read -r CPU_VAL MEM_VAL <<< $(get_pod_metrics "${SERVICE}")
                        [[ "$CPU_VAL" -gt 0 ]] && echo "$CPU_VAL" >> "$CPU_LOG"
                        [[ "$MEM_VAL" -gt 0 ]] && echo "$MEM_VAL" >> "$MEM_LOG"
                        sleep 2
                    done
                ) &
                SAMPLER_PID=$!

            done

            # Final cleanup of sampler
            kill $SAMPLER_PID 2>/dev/null
            wait $SAMPLER_PID 2>/dev/null
            rm -f "$CPU_LOG" "$MEM_LOG"

        done
    done
}

# ============================================
# MAIN — run all groups automatically
# ============================================

for GROUP in "graph" "math" "multimedia" "text"; do
    echo ""
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN} GROUP: ${GROUP}${NC}"
    echo -e "${CYAN}============================================${NC}"

    # Create CSV for this group
    OUTPUT_CSV="${RESULTS_DIR}/${GROUP}_profiling_$(date +%Y%m%d_%H%M%S).csv"
    echo "group,function,cpu_limit,memory_limit,payload,payload_size_mb,output_size_mb,cold_total_ms,cold_start_ms,cold_exec_ms,warm_avg_total_ms,warm_avg_exec_ms,warm_avg_start_ms,warm_avg_cpu_m,warm_avg_memory_mi,warm_iterations" > "$OUTPUT_CSV"
    echo -e "${GREEN}Results will be saved to: ${OUTPUT_CSV}${NC}"

    # Loop over functions in this group
    FUNC_LIST="${GROUPS[$GROUP]}"
    for FUNC in $FUNC_LIST; do
        profile_function "${GROUP}" "${FUNC}" "${OUTPUT_CSV}"
    done

    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN} GROUP ${GROUP} COMPLETE${NC}"
    echo -e "${GREEN} Results: ${OUTPUT_CSV}${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "Preview:"
    column -t -s ',' "$OUTPUT_CSV"
done

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN} ALL PROFILING COMPLETE${NC}"
echo -e "${CYAN} Results saved in: ${RESULTS_DIR}${NC}"
echo -e "${CYAN}============================================${NC}"