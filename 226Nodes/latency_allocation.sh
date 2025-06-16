#!/bin/bash

LATENCY_FILE="latency_list.txt"

reset_container_latency() {
    node=$1
    interface=$2
    echo "  [Container] Resetting latency on ${node}:${interface}..."
    sudo containerlab tools netem set -n "${node}" -i "${interface}"
}

set_container_latency() {
    node=$1
    interface=$2
    delay=$3
    echo "  [Container] Applying ${delay}ms to ${node}:${interface}..."
    sudo containerlab tools netem set -n "${node}" -i "${interface}" --delay "${delay}ms"
}

reset_switch_latency() {
    interface=$1
    echo "  [Switch] Resetting latency on ${interface}..."
    sudo tc qdisc del dev "${interface}" root 2>/dev/null
}

set_switch_latency() {
    interface=$1
    delay=$2
    echo "  [Switch] Applying ${delay}ms to ${interface}..."
    sudo tc qdisc add dev "${interface}" root netem delay "${delay}ms"
}

process_endpoint() {
    endpoint=$1
    delay=$2
    
    IFS=':' read -r node interface <<< "${endpoint}"
    echo "Processing: ${node}:${interface}"

    if [[ "${node}" == clab-* ]]; then
        # Container node operations
        reset_container_latency "${node}" "${interface}"
        set_container_latency "${node}" "${interface}" "${delay}"
        
    elif [[ "${node}" == switch* ]]; then
        # Switch operations
        reset_switch_latency "${interface}"
        set_switch_latency "${interface}" "${delay}"
    else
        echo "  ERROR: Unknown node type '${node}'"
        exit 1
    fi
}

echo "========== Starting Latency Configuration =========="
echo "Reading latency file: ${LATENCY_FILE}"
echo "-----------------------------------------------------"

while IFS= read -r line; do
    # Skip empty lines and comments
    [[ -z "${line}" || "${line}" == \#* ]] && continue

    echo "Processing connection: ${line}"
    
    # Split line into components
    read -r ep1 ep2 rtt <<< "${line}"
    
    # Calculate one-way delay
    delay=$(echo "scale=4; ${rtt}/2" | bc)
    echo "  RTT: ${rtt}ms → One-way delay: ${delay}ms"

    # Process both endpoints
    process_endpoint "${ep1}" "${delay}"
    process_endpoint "${ep2}" "${delay}"
    
    echo "-----------------------------------------------------"
done < "${LATENCY_FILE}"

echo "========== Latency Configuration Complete =========="
echo "Verification commands:"
echo "For containers: clab tools netem show -n <node>"
echo "For switches: tc qdisc show dev <interface>"