#!/bin/bash
# call this script as:
# pcap.sh <container-name> <interface-name>
# example: pcap.sh clab-century-serf1 eth1

# To support multiple interfaces, pass them as comma separated list
# Split $2 into individual interfaces and format them for tcpdump
IFS=',' read -ra ADDR <<< "$2"
IFACES=""
for i in "${ADDR[@]}"; do
    IFACES+="$i"
done

# Local capture using tcpdump in the network namespace
sudo ip netns exec $1 tcpdump -U -nni "${IFACES}" -w - | \
    sudo wireshark -k -i -
