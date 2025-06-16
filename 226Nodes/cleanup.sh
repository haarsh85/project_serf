#!/bin/bash

echo "🛑 Destroying Containerlab topology..."
sudo clab destroy -t 226nodes_ovs.yml

echo "🔍 Checking for remaining OVS interfaces..."

# Extract only valid OVS interfaces (ignoring ovs-system)
OVS_INTERFACES=$(ip link show | grep ovs | awk -F '[@:]' '{print $2}' | grep -v "ovs-system")

if [[ -n "$OVS_INTERFACES" ]]; then
    echo "🗑️ Found leftover OVS interfaces. Deleting..."
    for iface in $OVS_INTERFACES; do
        sudo ip link delete "$iface" 2>/dev/null && echo "✅ Deleted: $iface"
    done
else
    echo "✅ No leftover interfaces to clean up."
fi

echo "🎉 Cleanup completed successfully!"