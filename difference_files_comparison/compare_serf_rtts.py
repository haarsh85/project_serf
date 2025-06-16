import re
from collections import OrderedDict

# File names
file_5d = "serf_ping_rtt_signed_diff_5D.log"
file_8d = "serf_ping_rtt_signed_diff_8D.log"
output_file = "serf_rtt_comparison_output.txt"

# Regex to extract key and diff
line_pattern = re.compile(r"\[(.*?)\] (.*?) \((.*?)\) → \[(.*?)\] (.*?) \((.*?)\): ([+-]?\d+\.\d+) ms")

def parse_file_ordered(file_path):
    data = OrderedDict()
    with open(file_path, "r") as f:
        for line in f:
            match = line_pattern.search(line)
            if match:
                src_net, src_host, src_ip, dst_net, dst_host, dst_ip, diff = match.groups()
                key = f"[{src_net}] {src_host} → [{dst_net}] {dst_host}"
                data[key] = float(diff)
    return data

def parse_file(file_path):
    data = {}
    with open(file_path, "r") as f:
        for line in f:
            match = line_pattern.search(line)
            if match:
                src_net, src_host, src_ip, dst_net, dst_host, dst_ip, diff = match.groups()
                key = f"[{src_net}] {src_host} → [{dst_net}] {dst_host}"
                data[key] = float(diff)
    return data

# Parse files
data_5d = parse_file_ordered(file_5d)  # preserve order
data_8d = parse_file(file_8d)

# Comparison results
results = []
summary = {"5D": 0, "8D": 0, "Tie": 0}

for key, diff_5d in data_5d.items():
    if key in data_8d:
        diff_8d = data_8d[key]
        abs_5d = abs(diff_5d)
        abs_8d = abs(diff_8d)

        if abs_5d < abs_8d:
            better = "5D"
        elif abs_8d < abs_5d:
            better = "8D"
        else:
            better = "Tie"

        summary[better] += 1

        results.append(f"{key}\n5D: {diff_5d:+.3f} ms | 8D: {diff_8d:+.3f} ms | Better: {better}\n")

# Overall result
if summary["5D"] > summary["8D"]:
    overall = "5D"
elif summary["8D"] > summary["5D"]:
    overall = "8D"
else:
    overall = "Tie"

# Write output
with open(output_file, "w") as out:
    out.write("\n".join(results))
    out.write("\n\nOverall Summary:\n")
    out.write(f"5D better: {summary['5D']}\n")
    out.write(f"8D better: {summary['8D']}\n")
    out.write(f"Tie: {summary['Tie']}\n")
    out.write(f"Best overall: {overall}\n")

print(f"Comparison written in original order to: {output_file}")
