#!/bin/bash
# ============================================
# Generate text workflow YAML files
# for small, medium, and large payload sizes
# Data sizes are read from actual output.json files
# Workflow structure:
#   Trigger → TextDataGen_1..10 → TextSort_1..10 → AggregateLines → MergeAggregate → SingleString → Encrypt
# ============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/workflows"
mkdir -p "$OUTPUT_DIR"

# Number of parallel TextDataGen → TextSort branches
N_BRANCHES=10

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

    echo "Generating text_workflow_${SIZE}.yaml..."

    # Collect data sizes
    local SIZE_TRIGGER SIZE_TEXT_DATA_GEN SIZE_TEXT_SORT
    local SIZE_AGGREGATE_LINES SIZE_MERGE_AGGREGATE SIZE_SINGLE_STRING

    SIZE_TRIGGER=$(get_output_size_mb          "trigger"         "$SIZE")
    SIZE_TEXT_DATA_GEN=$(get_output_size_mb    "text_data_gen"   "$SIZE")
    SIZE_TEXT_SORT=$(get_output_size_mb        "text_sort"       "$SIZE")
    SIZE_AGGREGATE_LINES=$(get_output_size_mb  "aggregate_lines" "$SIZE")
    SIZE_MERGE_AGGREGATE=$(get_output_size_mb  "merge_aggregate" "$SIZE")
    SIZE_SINGLE_STRING=$(get_output_size_mb    "single_string"   "$SIZE")

    echo "  trigger           output → ${SIZE_TRIGGER} MB"
    echo "  text_data_gen     output → ${SIZE_TEXT_DATA_GEN} MB"
    echo "  text_sort         output → ${SIZE_TEXT_SORT} MB"
    echo "  aggregate_lines   output → ${SIZE_AGGREGATE_LINES} MB"
    echo "  merge_aggregate   output → ${SIZE_MERGE_AGGREGATE} MB"
    echo "  single_string     output → ${SIZE_SINGLE_STRING} MB"

    # ============================================
    # Start YAML
    # ============================================
    local YAML_FILE="${OUTPUT_DIR}/text_workflow_${SIZE}.yaml"

    cat > "$YAML_FILE" << EOF
workflow_name: text_workflow_${SIZE}
functions:
  - name: trigger
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:text_trigger

EOF

    # Add N_BRANCHES text_data_gen + text_sort functions
    for ((i=1; i<=N_BRANCHES; i++)); do
        cat >> "$YAML_FILE" << EOF
  - name: text_data_gen_${i}
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:text_text_data_gen

  - name: text_sort_${i}
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:text_text_sort

EOF
    done

    # Add aggregation + tail functions
    cat >> "$YAML_FILE" << EOF
  - name: aggregate_lines
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:text_aggregate_lines

  - name: merge_aggregate
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:text_merge_aggregate

  - name: single_string
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:text_single_string

  - name: encrypt
    requirements:
      cpu: 500m
      ram: 128Mi
    image: arjiba/profiling:text_encrypt

dependencies:
EOF

    # Trigger → text_data_gen_i
    for ((i=1; i<=N_BRANCHES; i++)); do
        cat >> "$YAML_FILE" << EOF
  - from: trigger
    to: text_data_gen_${i}
    data_size: ${SIZE_TRIGGER}

EOF
    done

    # text_data_gen_i → text_sort_i
    for ((i=1; i<=N_BRANCHES; i++)); do
        cat >> "$YAML_FILE" << EOF
  - from: text_data_gen_${i}
    to: text_sort_${i}
    data_size: ${SIZE_TEXT_DATA_GEN}

EOF
    done

    # text_sort_i → aggregate_lines
    for ((i=1; i<=N_BRANCHES; i++)); do
        cat >> "$YAML_FILE" << EOF
  - from: text_sort_${i}
    to: aggregate_lines
    data_size: ${SIZE_TEXT_SORT}

EOF
    done

    # Tail chain
    cat >> "$YAML_FILE" << EOF
  - from: aggregate_lines
    to: merge_aggregate
    data_size: ${SIZE_AGGREGATE_LINES}

  - from: merge_aggregate
    to: single_string
    data_size: ${SIZE_MERGE_AGGREGATE}

  - from: single_string
    to: encrypt
    data_size: ${SIZE_SINGLE_STRING}
EOF

    echo "  ✅ ${YAML_FILE} created"
}

# ============================================
# Generate all three sizes
# ============================================
generate_workflow "small"
generate_workflow "medium"
generate_workflow "large"

echo ""
echo "✅ All text workflows generated in ${OUTPUT_DIR}/"
ls -lh "${OUTPUT_DIR}"