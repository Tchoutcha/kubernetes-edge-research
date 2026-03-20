#!/bin/bash
# ============================================
# Generate multimedia workflow YAML files
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

    echo "Generating multimedia_workflow_${SIZE}.yaml..."

    # Collect data sizes from output.json of each function
    local SIZE_FETCH_DATA SIZE_GRAYSCALE SIZE_FLIP
    local SIZE_ROTATE SIZE_RESIZE
    local SIZE_ALEXNET SIZE_RESNET SIZE_MOBILENET

    SIZE_FETCH_DATA=$(get_output_size_mb  "fetch_data"  "$SIZE")
    SIZE_GRAYSCALE=$(get_output_size_mb   "grayscale"   "$SIZE")
    SIZE_FLIP=$(get_output_size_mb        "flip"        "$SIZE")
    SIZE_ROTATE=$(get_output_size_mb      "rotate"      "$SIZE")
    SIZE_RESIZE=$(get_output_size_mb      "resize"      "$SIZE")
    SIZE_ALEXNET=$(get_output_size_mb     "alexnet"     "$SIZE")
    SIZE_RESNET=$(get_output_size_mb      "resnet"      "$SIZE")
    SIZE_MOBILENET=$(get_output_size_mb   "mobilenet"   "$SIZE")

    echo "  fetch_data  output → ${SIZE_FETCH_DATA} MB"
    echo "  grayscale   output → ${SIZE_GRAYSCALE} MB"
    echo "  flip        output → ${SIZE_FLIP} MB"
    echo "  rotate      output → ${SIZE_ROTATE} MB"
    echo "  resize      output → ${SIZE_RESIZE} MB"
    echo "  alexnet     output → ${SIZE_ALEXNET} MB"
    echo "  resnet      output → ${SIZE_RESNET} MB"
    echo "  mobilenet   output → ${SIZE_MOBILENET} MB"

    cat > "${OUTPUT_DIR}/multimedia_workflow_${SIZE}.yaml" << EOF
workflow_name: multimedia_workflow_${SIZE}
functions:
  - name: fetch_data
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:multimedia_fetch_data

  - name: grayscale
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:multimedia_grayscale

  - name: flip
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:multimedia_flip

  - name: rotate
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:multimedia_rotate

  - name: resize
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:multimedia_resize

  - name: alexnet
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:multimedia_alexnet

  - name: resnet
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:multimedia_resnet

  - name: mobilenet
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:multimedia_mobilenet

  - name: aggregator
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:multimedia_aggregator

dependencies:
  - from: fetch_data
    to: grayscale
    data_size: ${SIZE_FETCH_DATA}

  - from: grayscale
    to: flip
    data_size: ${SIZE_GRAYSCALE}

  - from: flip
    to: rotate
    data_size: ${SIZE_FLIP}

  - from: rotate
    to: resize
    data_size: ${SIZE_ROTATE}

  - from: resize
    to: alexnet
    data_size: ${SIZE_RESIZE}

  - from: resize
    to: resnet
    data_size: ${SIZE_RESIZE}

  - from: resize
    to: mobilenet
    data_size: ${SIZE_RESIZE}

  - from: alexnet
    to: aggregator
    data_size: ${SIZE_ALEXNET}

  - from: resnet
    to: aggregator
    data_size: ${SIZE_RESNET}

  - from: mobilenet
    to: aggregator
    data_size: ${SIZE_MOBILENET}
EOF

    echo "  ✅ ${OUTPUT_DIR}/multimedia_workflow_${SIZE}.yaml created"
}

# ============================================
# Generate all three sizes
# ============================================
generate_workflow "small"
generate_workflow "medium"
generate_workflow "large"

echo ""
echo "✅ All multimedia workflows generated in ${OUTPUT_DIR}/"
ls -lh "${OUTPUT_DIR}"