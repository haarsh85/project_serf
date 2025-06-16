import re
import numpy as np

log_file_path = "ping_rtt_values_new.log"  # Update as needed

rtt_values = []
max_rtt = 0.0
max_line = ""

min_rtt = float('inf')
min_line = ""

with open(log_file_path, "r") as file:
    for line in file:
        if line.startswith("==="):
            continue

        match = re.search(r": ([\d\.]+)ms", line)
        if match:
            rtt = float(match.group(1))
            rtt_values.append(rtt)

            if rtt > max_rtt:
                max_rtt = rtt
                max_line = line.strip()
            if rtt < min_rtt:
                min_rtt = rtt
                min_line = line.strip()

if not rtt_values:
    print("❌ No RTT values found in the log.")
else:
    percentile_99 = np.percentile(rtt_values, 99)

    print(f"✅ Maximum RTT: {max_rtt} ms")
    print(f"🔍 Occurred in: {max_line}")

    print(f"✅ Minimum RTT: {min_rtt} ms")
    print(f"🔍 Occurred in: {min_line}")

    print(f"📈 99th Percentile RTT: {percentile_99:.3f} ms (based on {len(rtt_values)} samples)")
