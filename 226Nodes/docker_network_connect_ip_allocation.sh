#!/bin/bash

# File containing network and node details
file="networks_nodes.txt"

# Loop through each line in the file
while IFS=: read -r net_details; do
    # Print the processing line
    echo "Processing line: $net_details"
    
    # Extract network name (first word before ':')
    network_name=$(echo $net_details | cut -d' ' -f1)
    
    # Extract the remaining details (subnet and nodes)
    details=$(echo $net_details | sed 's/^[^ ]* //')
    
    # Extract subnet and nodes
    subnet=$(echo $details | cut -d' ' -f1)
    nodes=$(echo $details | cut -d' ' -f2-)
    
    # Extract the base IP (e.g., 10.0.1.0)
    base_ip=$(echo $subnet | cut -d'/' -f1)
    base_ip_octets=(${base_ip//./ })

    # Print the network name, subnet, nodes, and base IP
    echo "Network name: $network_name"
    echo "Subnet: $subnet"
    echo "Nodes: $nodes"
    echo "Base IP: $base_ip"
    
    # Check if the network exists before trying to connect nodes
    docker network inspect $network_name > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "ERROR: Network $network_name not found!"
        continue  # Skip this network and move to the next one
    else
        echo "Network $network_name found."
    fi

    # Loop through each node in the network and assign IP
    count=2  # Start from .2 for the first node
    for node in $nodes; do
        # Assign the IP address by changing the last octet
        ip="${base_ip_octets[0]}.${base_ip_octets[1]}.${base_ip_octets[2]}.$count"
        
        # Try connecting the node to the network with the assigned IP
        attempt=1
        while [ $attempt -le 2 ]; do
            echo "Connecting node $node to network $network_name with IP $ip (Attempt $attempt)"
            
            # Connect the Serf node to the Docker network with the assigned IP
            docker network connect --ip $ip $network_name $node
            
            # Check if the connection was successful
            if [ $? -eq 0 ]; then
                echo "Node $node connected to network $network_name with IP $ip"
                break  # Exit the loop if connection is successful
            else
                # If it failed, increment attempt and retry
                echo "Failed to connect node $node. Retrying..."
                attempt=$((attempt + 1))
            fi
        done
        
        # Increment the IP address for the next node
        count=$((count + 1))
    done
done < "$file"

echo "All nodes connected to their respective networks."
