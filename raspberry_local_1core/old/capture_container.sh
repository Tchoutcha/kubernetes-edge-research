#!/bin/bash
mkdir -p logs
OUTPUT_FILE="logs/containers_live_$(date +%Y%m%d_%H%M%S).csv"
#OUTPUT_FILE="containers_live_$(date +%Y%m%d_%H%M%S).csv"
echo "timestamp,pod,container_id,container_name,node,createdAt,startedAt" > "$OUTPUT_FILE"

NODES=("worker1" "worker2" "worker3" "worker4" "worker5" "worker6" "worker7" "worker8" "worker9" "worker10" "worker11" "worker12" "worker13" "worker14" "worker15")

declare -A SEEN_CONTAINERS
INTERVAL=0.01

echo "Starting container capture..."
echo "Output -> $OUTPUT_FILE"

while true; do
    TIMESTAMP=$(date +%s.%N)

    for node in "${NODES[@]}"; do

        while IFS=$'\t' read -r CID NAME POD; do

            KEY="${node}_${CID}"

            # Skip if already logged
            if [[ -n "${SEEN_CONTAINERS[$KEY]}" ]]; then
                continue
            fi

            # Inspect container for precise timestamps
            INSPECT=$(ssh "$node" "sudo crictl inspect $CID" 2>/dev/null)

            CREATED=$(echo "$INSPECT" | jq -r '.status.createdAt // empty')
            STARTED=$(echo "$INSPECT" | jq -r '.status.startedAt // empty')

            echo "$TIMESTAMP,$POD,$CID,$NAME,$node,$CREATED,$STARTED" >> "$OUTPUT_FILE"

            SEEN_CONTAINERS[$KEY]=1

        done < <(
            ssh "$node" "sudo crictl ps -a --output=json" 2>/dev/null | \
            jq -r '.containers[]
              | select(.metadata.name=="queue-proxy" or .metadata.name=="user-container")
              | [.id, .metadata.name, (.labels["io.kubernetes.pod.name"] // "")]
              | @tsv'
        )

    done

    sleep "$INTERVAL"
done
