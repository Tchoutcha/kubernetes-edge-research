#!/bin/bash
<<comment
FUNCTION_DIRS=(
    "graph_aggregate" "graph_graph_bft" "graph_graph_gen" "graph_graph_mst" "graph_pagerank"
    "math_aggregator" "math_cosine" "math_factors" "math_fast_fourier_transform" "math_gen_int"
    "math_gen_list" "math_gen_matrix_a" "math_gen_matrix_b" "math_linpack" "math_matrix_multiplication"
    "math_sine" "math_source"
    "multimedia_aggregator" "multimedia_alexnet" "multimedia_fetch_data" "multimedia_flip"
    "multimedia_grayscale" "multimedia_mobilenet" "multimedia_resize" "multimedia_resnet" "multimedia_rotate"
    "text_aggregate_lines" "text_encrypt" "text_merge_aggregate" "text_single_string"
    "text_text_data_gen" "text_text_sort" "text_textsort1" "text_trigger"
)
comment

FUNCTION_DIRS=(
    "graph_graph_bft"
    "graph_graph_mst"
    "graph_pagerank"
)

DOCKERHUB_USERNAME="arjiba"
REPO="profiling"

# Login
echo "Logging in to Docker Hub..."
docker login -u ${DOCKERHUB_USERNAME}
if [[ $? -ne 0 ]]; then
    echo "❌ Docker login failed. Exiting."
    exit 1
fi

PUSH_FAILURES=()

for FUNC in "${FUNCTION_DIRS[@]}"; do
    LOCAL_IMAGE="${FUNC}:latest"
    REMOTE_IMAGE="${DOCKERHUB_USERNAME}/${REPO}:${FUNC}"

    echo "=============================="
    echo "Tagging and pushing: ${FUNC}"
    echo "=============================="

    # Check image exists locally
    if ! docker image inspect "${LOCAL_IMAGE}" > /dev/null 2>&1; then
        echo "❌ Local image ${LOCAL_IMAGE} not found. Skipping."
        PUSH_FAILURES+=("$FUNC")
        continue
    fi

    # Tag
    docker tag "${LOCAL_IMAGE}" "${REMOTE_IMAGE}"
    echo "✅ Tagged: ${LOCAL_IMAGE} → ${REMOTE_IMAGE}"

    # Push
    docker push "${REMOTE_IMAGE}"
    if [[ $? -ne 0 ]]; then
        echo "❌ Push failed for ${FUNC}"
        PUSH_FAILURES+=("$FUNC")
        continue
    fi
    echo "✅ Pushed: ${REMOTE_IMAGE}"

done

# Summary
echo ""
echo "============================================"
echo " SUMMARY"
echo "============================================"
echo "Total functions : ${#FUNCTION_DIRS[@]}"
echo "Push failures   : ${#PUSH_FAILURES[@]}"

if [[ ${#PUSH_FAILURES[@]} -gt 0 ]]; then
    echo ""
    echo "❌ Push failures:"
    for F in "${PUSH_FAILURES[@]}"; do
        echo "   - $F"
    done
else
    echo "✅ All ${#FUNCTION_DIRS[@]} images pushed successfully"
fi

echo ""
echo "Verify: https://hub.docker.com/r/${DOCKERHUB_USERNAME}/${REPO}/tags"