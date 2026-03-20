#!/bin/bash

# ============================================
# Generate graph workflow YAML files
# for small, medium, and large payload sizes
# Data sizes are read from actual output.json files
# ============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/workflows"
mkdir -p "$OUTPUT_DIR"

# ============================================
# Helper — get file size in MB from output.json
# ============================================
get_output_size_mb() {
    local func=$1
    local size=$2
    local output_file="${SCRIPT_DIR}/${func}/samples/${size}/output/output.json"

    if [[ -f "$output_file" ]]; then
        local bytes
        bytes=$(stat -c%s "$output_file")
        python3 -c "print(round(${bytes}/1024/1024, 6))"
    else
        echo "0.001"  # fallback
    fi
}

# ============================================
# Generate workflow YAML for a given size
# ============================================
generate_workflow() {
    local SIZE=$1   # small | medium | large

    echo "Generating graph_workflow_${SIZE}.yaml..."

    # Collect data sizes from output.json of each function
    local SIZE_GRAPH_GEN
    local SIZE_GRAPH_BFT
    local SIZE_PAGERANK
    local SIZE_GRAPH_MST

    SIZE_GRAPH_GEN=$(get_output_size_mb "graph_gen"  "$SIZE")
    SIZE_GRAPH_BFT=$(get_output_size_mb "graph_bft"  "$SIZE")
    SIZE_PAGERANK=$(get_output_size_mb  "pagerank"   "$SIZE")
    SIZE_GRAPH_MST=$(get_output_size_mb "graph_mst"  "$SIZE")

    echo "  graph_gen  output → ${SIZE_GRAPH_GEN} MB"
    echo "  graph_bft  output → ${SIZE_GRAPH_BFT} MB"
    echo "  pagerank   output → ${SIZE_PAGERANK} MB"
    echo "  graph_mst  output → ${SIZE_GRAPH_MST} MB"

    cat > "${OUTPUT_DIR}/graph_workflow_${SIZE}.yaml" << EOF
workflow_name: graph_workflow_${SIZE}

functions:
  - name: graph_gen
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:graph_graph_gen

  - name: graph_bft
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:graph_graph_bft

  - name: pagerank
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:graph_pagerank

  - name: graph_mst
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:graph_graph_mst

  - name: aggregate
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:graph_aggregate

dependencies:
  - from: graph_gen
    to: graph_bft
    data_size: ${SIZE_GRAPH_GEN}

  - from: graph_gen
    to: pagerank
    data_size: ${SIZE_GRAPH_GEN}

  - from: graph_gen
    to: graph_mst
    data_size: ${SIZE_GRAPH_GEN}

  - from: graph_bft
    to: aggregate
    data_size: ${SIZE_GRAPH_BFT}

  - from: pagerank
    to: aggregate
    data_size: ${SIZE_PAGERANK}

  - from: graph_mst
    to: aggregate
    data_size: ${SIZE_GRAPH_MST}
EOF

    echo "${OUTPUT_DIR}/graph_workflow_${SIZE}.yaml created"
}

# ============================================
# Generate all three sizes
# ============================================
generate_workflow "small"
generate_workflow "medium"
generate_workflow "large"

echo ""
echo "All workflows generated in ${OUTPUT_DIR}/"
ls -lh "${OUTPUT_DIR}"/