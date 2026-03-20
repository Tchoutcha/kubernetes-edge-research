#!/bin/bash
# ============================================
# Generate math workflow YAML files
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

    echo "Generating math_workflow_${SIZE}.yaml..."

    # Collect data sizes from output.json of each function
    local SIZE_SOURCE SIZE_GEN_LIST SIZE_GEN_INT
    local SIZE_GEN_MATRIX_A SIZE_GEN_MATRIX_B
    local SIZE_FFT SIZE_SINE SIZE_COSINE SIZE_FACTORS
    local SIZE_AGGREGATOR_MID SIZE_AGGREGATOR_MATRIX
    local SIZE_LINPACK SIZE_MATRIX_MUL SIZE_AGGREGATOR_MATRIX2

    SIZE_SOURCE=$(get_output_size_mb             "source"                "$SIZE")
    SIZE_GEN_LIST=$(get_output_size_mb           "gen_list"              "$SIZE")
    SIZE_GEN_INT=$(get_output_size_mb            "gen_int"               "$SIZE")
    SIZE_GEN_MATRIX_A=$(get_output_size_mb       "gen_matrix_a"          "$SIZE")
    SIZE_GEN_MATRIX_B=$(get_output_size_mb       "gen_matrix_b"          "$SIZE")
    SIZE_FFT=$(get_output_size_mb                "fast_fourier_transform" "$SIZE")
    SIZE_SINE=$(get_output_size_mb               "sine"                  "$SIZE")
    SIZE_COSINE=$(get_output_size_mb             "cosine"                "$SIZE")
    SIZE_FACTORS=$(get_output_size_mb            "factors"               "$SIZE")
    SIZE_AGGREGATOR_MID=$(get_output_size_mb     "aggregator"            "$SIZE")
    SIZE_AGGREGATOR_MATRIX=$(get_output_size_mb  "aggregator"            "$SIZE")
    SIZE_LINPACK=$(get_output_size_mb            "linpack"               "$SIZE")
    SIZE_MATRIX_MUL=$(get_output_size_mb         "matrix_multiplication" "$SIZE")
    SIZE_AGGREGATOR_MATRIX2=$(get_output_size_mb "aggregator"            "$SIZE")

    echo "  source                output → ${SIZE_SOURCE} MB"
    echo "  gen_list              output → ${SIZE_GEN_LIST} MB"
    echo "  gen_int               output → ${SIZE_GEN_INT} MB"
    echo "  gen_matrix_a          output → ${SIZE_GEN_MATRIX_A} MB"
    echo "  gen_matrix_b          output → ${SIZE_GEN_MATRIX_B} MB"
    echo "  fast_fourier_transform output → ${SIZE_FFT} MB"
    echo "  sine                  output → ${SIZE_SINE} MB"
    echo "  cosine                output → ${SIZE_COSINE} MB"
    echo "  factors               output → ${SIZE_FACTORS} MB"
    echo "  aggregator_mid        output → ${SIZE_AGGREGATOR_MID} MB"
    echo "  aggregator_matrix     output → ${SIZE_AGGREGATOR_MATRIX} MB"
    echo "  linpack               output → ${SIZE_LINPACK} MB"
    echo "  matrix_multiplication output → ${SIZE_MATRIX_MUL} MB"
    echo "  aggregator_matrix2    output → ${SIZE_AGGREGATOR_MATRIX2} MB"

    cat > "${OUTPUT_DIR}/math_workflow_${SIZE}.yaml" << EOF
workflow_name: math_workflow_${SIZE}
functions:
  - name: source
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_source

  - name: gen_list
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_gen_list

  - name: gen_int
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_gen_int

  - name: gen_matrix_a
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_gen_matrix_a

  - name: gen_matrix_b
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_gen_matrix_b

  - name: fast_fourier_transform
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_fast_fourier_transform

  - name: sine
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_sine

  - name: cosine
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_cosine

  - name: factors
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_factors

  - name: aggregator_mid
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_aggregator

  - name: aggregator_matrix
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_aggregator

  - name: linpack
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_linpack

  - name: matrix_multiplication
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_matrix_multiplication

  - name: aggregator_matrix2
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_aggregator

  - name: aggregator
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:math_aggregator

dependencies:
  - from: source
    to: gen_list
    data_size: ${SIZE_SOURCE}

  - from: source
    to: gen_int
    data_size: ${SIZE_SOURCE}

  - from: source
    to: gen_matrix_a
    data_size: ${SIZE_SOURCE}

  - from: source
    to: gen_matrix_b
    data_size: ${SIZE_SOURCE}

  - from: gen_list
    to: fast_fourier_transform
    data_size: ${SIZE_GEN_LIST}

  - from: gen_int
    to: sine
    data_size: ${SIZE_GEN_INT}

  - from: gen_int
    to: cosine
    data_size: ${SIZE_GEN_INT}

  - from: gen_int
    to: factors
    data_size: ${SIZE_GEN_INT}

  - from: sine
    to: aggregator_mid
    data_size: ${SIZE_SINE}

  - from: cosine
    to: aggregator_mid
    data_size: ${SIZE_COSINE}

  - from: factors
    to: aggregator_mid
    data_size: ${SIZE_FACTORS}

  - from: gen_matrix_a
    to: aggregator_matrix
    data_size: ${SIZE_GEN_MATRIX_A}

  - from: gen_matrix_b
    to: aggregator_matrix
    data_size: ${SIZE_GEN_MATRIX_B}

  - from: aggregator_matrix
    to: linpack
    data_size: ${SIZE_AGGREGATOR_MATRIX}

  - from: aggregator_matrix
    to: matrix_multiplication
    data_size: ${SIZE_AGGREGATOR_MATRIX}

  - from: linpack
    to: aggregator_matrix2
    data_size: ${SIZE_LINPACK}

  - from: matrix_multiplication
    to: aggregator_matrix2
    data_size: ${SIZE_MATRIX_MUL}

  - from: fast_fourier_transform
    to: aggregator
    data_size: ${SIZE_FFT}

  - from: aggregator_mid
    to: aggregator
    data_size: ${SIZE_AGGREGATOR_MID}

  - from: aggregator_matrix2
    to: aggregator
    data_size: ${SIZE_AGGREGATOR_MATRIX2}
EOF

    echo "  ✅ ${OUTPUT_DIR}/math_workflow_${SIZE}.yaml created"
}

# ============================================
# Generate all three sizes
# ============================================
generate_workflow "small"
generate_workflow "medium"
generate_workflow "large"

echo ""
echo "✅ All math workflows generated in ${OUTPUT_DIR}/"
ls -lh "${OUTPUT_DIR}"