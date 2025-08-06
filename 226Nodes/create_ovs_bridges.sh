#!/bin/bash

# Create 37 OVS bridges (switch1 to switch37)
for i in {1..37}; do
    sudo ovs-vsctl add-br switch$i
    echo "Created OVS bridge: switch$i"
done

echo "All Open vSwitch bridges created successfully."
