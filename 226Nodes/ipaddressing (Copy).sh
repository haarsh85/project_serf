#!/bin/bash

# File containing network and node details
file="networks_nodes.txt"

# Loop through each line in the file
while IFS= read -r line; do
    # Extract network name, subnet, and node details
    network_name=$(echo "$line" | cut -d' ' -f1)
    subnet=$(echo "$line" | cut -d' ' -f2)
    nodes=$(echo "$line" | cut -d' ' -f3-)

    # Debugging: Print the network, subnet, and nodes
    echo "Processing Network: $network_name"
    echo "Subnet: $subnet"
    echo "Nodes: $nodes"

    # Extract the base IP (e.g., 10.0.1.0)
    base_ip=$(echo "$subnet" | cut -d'/' -f1)
    base_ip_octets=(${base_ip//./ })

    # Calculate the gateway IP (e.g., 10.0.1.1)
    gateway_ip="${base_ip_octets[0]}.${base_ip_octets[1]}.${base_ip_octets[2]}.1"

    # Assign IPs and update routes for each node
    count=10  # Start from .10 for the first node
    for node in $nodes; do
        # Assign the IP address by changing the last octet
        ip="${base_ip_octets[0]}.${base_ip_octets[1]}.${base_ip_octets[2]}.$count"

        # Debugging: Print the node and IP being assigned
        echo "Configuring node $node with IP $ip and gateway $gateway_ip"

        # Ensure eth1 is up
        sudo docker exec -d "$node" ip link set dev eth1 up

        # Add the IP address to eth1
        sudo docker exec -d "$node" ip addr add "$ip/24" brd + dev eth1

        # Delete the existing default route
        sudo docker exec -d "$node" ip route del default

        # Add the new default route via the gateway
        sudo docker exec -d "$node" ip route add default via "$gateway_ip"

        # Get the eth0 IP dynamically from inside the container
        eth0_ip=$(sudo docker exec "$node" ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
        
        if [ -n "$eth0_ip" ]; then
            # Add the route to the host using the dynamically retrieved eth0 IP
            sudo docker exec -d "$node" ip route add 172.22.120.21/32 via "$eth0_ip" dev eth0
            echo "Added route to 172.22.120.21 via $eth0_ip for node $node"
        else
            echo "Error: Could not determine eth0 IP address for node $node"
        fi

        # Increment the IP address for the next node
        count=$((count + 1))

        echo "Node $node configured with IP $ip and default route $gateway_ip"
    done
done < "$file"

echo "IP addresses and routes have been configured for all nodes."
