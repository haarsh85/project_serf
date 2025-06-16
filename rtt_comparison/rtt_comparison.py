import re

# Read RTT from ping_rtt.txt
ping_rtt = {}
with open("ping_rtt.txt", "r") as ping_file:
    for line in ping_file:
        match = re.match(r".*RTT from (\S+) \((\S+)\) to (\S+) \((\S+)\) (\d+\.\d+)ms", line)
        if match:
            node1, ip1, node2, ip2, rtt = match.groups()
            ping_rtt[(node1, node2)] = float(rtt)

# Read RTT from serf_rtt.txt
serf_rtt = {}
with open("serf_rtt.txt", "r") as serf_file:
    for line in serf_file:
        match = re.match(r"Estimated (\S+) <-> (\S+) rtt: (\d+\.\d+) ms", line)
        if match:
            node1, node2, rtt = match.groups()
            serf_rtt[(node1, node2)] = float(rtt)

# Compare the RTT values
differences = []
for (node1, node2), ping_value in ping_rtt.items():
    if (node1, node2) in serf_rtt:
        serf_value = serf_rtt[(node1, node2)]
        difference = round(serf_value - ping_value, 2)  # Round the difference to 2 decimal places
        differences.append((node1, node2, ping_value, serf_value, difference))

# Output the result
for node1, node2, ping_value, serf_value, difference in differences:
    print(f"RTT between {node1} and {node2}:")
    print(f"  Ping RTT: {ping_value} ms")
    print(f"  Serf RTT: {serf_value} ms")
    print(f"  Difference: {difference} ms\n")