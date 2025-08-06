#!/bin/bash

for i in $(seq 1 162); do
    container="clab-nebula-serf$i"
    echo "Checking container: $container..."

    # Run the command and capture any warnings (timeout after 3s)
    output=$(docker exec "$container" bash -c "cd /opt/serfapp && timeout 3 ./serf_2D monitor -log-level=warn" 2>/dev/null)

    # Check if there is any output
    if [[ -n "$output" ]]; then
        echo "⚠️  WARN logs found in $container:"
        echo "$output"
        echo "------------------------------------------------------------"
    else
        echo "✅ No WARN logs in $container"
    fi
done
