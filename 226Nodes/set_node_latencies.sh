#!/bin/bash

# Define the node names and their respective latencies in an array
# Format: "node_name interface_name latency_value"
nodes=(
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    "clab-nebula-serf1 eth1 5ms"
    


    # Add the rest of your nodes here
)

# Iterate through the nodes and apply the latency
for node_info in "${nodes[@]}"; do
    # Split the node_info into variables
    node_name=$(echo $node_info | awk '{print $1}')
    interface=$(echo $node_info | awk '{print $2}')
    latency=$(echo $node_info | awk '{print $3}')
    
    # Apply the latency using the containerlab tools netem command
    echo "Setting latency $latency on $node_name ($interface)..."
    containerlab tools netem set -n "$node_name" -i "$interface" --delay "$latency"
    
    # Check if the command succeeded
    if [ $? -eq 0 ]; then
        echo "Latency set successfully for $node_name."
    else
        echo "Failed to set latency for $node_name. Please check."
    fi
done

echo "Latency configuration completed!"
