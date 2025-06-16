import re
from statistics import median

log_file = "ping_sorted_rtt_new.log"
rtt_values = []

# Regex to extract RTT values like: 7.707ms, 12.107ms, etc.
rtt_pattern = re.compile(r'(\d+\.\d+)ms')

with open(log_file, "r") as f:
    for line in f:
        match = rtt_pattern.search(line)
        if match:
            rtt_values.append(float(match.group(1)))

if rtt_values:
    print(f"Total RTT values found: {len(rtt_values)}")
    print(f"Median RTT: {median(rtt_values):.3f} ms")
else:
    print("No RTT values found.")
