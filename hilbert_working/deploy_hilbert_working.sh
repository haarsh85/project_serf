#!/bin/bash

# List of containers
containers=()
for i in {1..162}; do
  containers+=(clab-nebula-serf$i)
done

# Paths and file names
net_file="networks_nodes.txt"
go_binary="hilbert_working"  # Compiled Go binary
destination_dir="/opt/serfapp"

# Ensure the Go binary is compiled
if [ ! -f "$go_binary" ]; then
  echo "Error: Compiled Go binary ($go_binary) not found. Please build it first using 'go build'."
  exit 1
fi

# Function to set up the Go binary on nodes
deploy_coordinate_binary() {
  for container in "${containers[@]}"; do
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "$container"; then
      echo "Container $container is not running, skipping..."
      continue
    fi
    
    echo "Copying coordinate binary & net file to $container..."

    # Copy the Go binary into the /opt/serfapp/ directory
    docker cp "$go_binary" "$container":"$destination_dir"/ || { echo "Failed to copy Go binary to $container"; exit 1; }
    docker cp "$net_file" "$container":"$destination_dir"/ || { echo "Failed to copy net file to $container"; exit 1; }

    # Make the binary executable
    docker exec "$container" chmod +x "$destination_dir"/"$go_binary" || { echo "Failed to make Go binary executable on $container"; exit 1; }

    echo "hilbert binary successfully set up on $container."
  done
}

# Main script execution
deploy_coordinate_binary