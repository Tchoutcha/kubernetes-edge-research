#!/bin/bash

mkdir -p logs
OUTPUT_FILE="logs/containers_live_$(date +%Y%m%d_%H%M%S).csv"
echo "timestamp,pod,container_id,container_name,node,createdAt,startedAt" > "$OUTPUT_FILE"

NODES=("worker1" "worker2" "worker3" "worker4" "worker5" "worker6" "worker7"
       "worker8" "worker9" "worker10" "worker11" "worker12" "worker13" "worker14" )

declare -A SEEN_CONTAINERS
TMPDIR_BASE=$(mktemp -d)

# 🔥 plus agressif → réduit perte de containers
INTERVAL=0.01  # 20 ms

echo "Starting container capture (parallel SSH)..."
echo "Output -> $OUTPUT_FILE"
echo "Ctrl+C pour arrêter"

capture_node() {
    local node=$1
    local outfile=$2

    ssh -o ConnectTimeout=2 -o BatchMode=yes -o StrictHostKeyChecking=no "$node" \
    'sudo crictl ps -a --output=json 2>/dev/null | \
     python3 -c "
import sys, json, subprocess

data = json.load(sys.stdin)

for c in data.get(\"containers\", []):
    name = c.get(\"metadata\", {}).get(\"name\", \"\")
    if name not in (\"queue-proxy\", \"user-container\"):
        continue

    cid = c[\"id\"]
    pod = c.get(\"labels\", {}).get(\"io.kubernetes.pod.name\", \"\")

    created, started = \"\", \"\"

    try:
        r = subprocess.run(
            [\"sudo\", \"crictl\", \"inspect\", cid],
            capture_output=True,
            text=True,
            timeout=5   #  augmenté
        )

        if r.returncode == 0 and r.stdout:
            s = json.loads(r.stdout).get(\"status\", {})
            created = s.get(\"createdAt\", \"\")
            started = s.get(\"startedAt\", \"\")

    except Exception:
        pass

    print(f\"{cid}\t{name}\t{pod}\t{created}\t{started}\")
"' > "$outfile" 2>/dev/null
}

export -f capture_node

cleanup() {
    rm -rf "$TMPDIR_BASE"
    echo ""
    echo "✓ Saved: $OUTPUT_FILE"
    exit 0
}
trap cleanup SIGINT SIGTERM

while true; do
    TIMESTAMP=$(date +%s.%N)
    ROUND_DIR="$TMPDIR_BASE/round_$$"
    mkdir -p "$ROUND_DIR"

    # parallèle
    for node in "${NODES[@]}"; do
        capture_node "$node" "$ROUND_DIR/$node" &
    done
    wait

    # agrégation
    for node in "${NODES[@]}"; do
        [ -f "$ROUND_DIR/$node" ] || continue

        while IFS=$'\t' read -r CID NAME POD CREATED STARTED; do
            [ -z "$CID" ] && continue

            KEY="${node}_${CID}"

            if [[ -z "${SEEN_CONTAINERS[$KEY]}" ]]; then
                printf "%s,%s,%s,%s,%s,%s,%s\n" \
                    "$TIMESTAMP" "$POD" "$CID" "$NAME" "$node" "$CREATED" "$STARTED" \
                    >> "$OUTPUT_FILE"

                SEEN_CONTAINERS[$KEY]=1
            fi
        done < "$ROUND_DIR/$node"
    done

    rm -rf "$ROUND_DIR"
    sleep "$INTERVAL"
done
