import re

def parse_log_lines(file_path):
    parsed_lines = []
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Remove timestamp and test duration
            line = re.sub(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} ", "", line)  # Remove timestamp if exists
            line = re.sub(r"\(test duration: [^)]+\)", "", line).strip()      # Remove (test duration: X.XXXs)
            
            # Match pattern and extract RTT
            match = re.match(r"(.*?)\s*:\s*([\d.]+)ms", line)
            if match:
                node_pair = match.group(1).strip()
                rtt = float(match.group(2))
                parsed_lines.append((node_pair, rtt))
            elif line.startswith("==="):
                parsed_lines.append((line, None))
            else:
                parsed_lines.append((f"Could not parse: {line}", None))
    return parsed_lines

def compare_logs(ping_file, serf_file, output_file):
    ping_lines = parse_log_lines(ping_file)
    serf_lines = parse_log_lines(serf_file)

    with open(output_file, "w") as f:
        for (ping_entry, ping_rtt), (serf_entry, serf_rtt) in zip(ping_lines, serf_lines):
            # Handle section headers and errors
            if ping_rtt is None or serf_rtt is None:
                f.write(ping_entry + "\n")
                continue
            
            diff = serf_rtt - ping_rtt
            sign = "+" if diff >= 0 else "-"
            diff_str = f"{sign}{abs(diff):.3f}ms"
            
            # Add the ping_rtt and serf_rtt values in the format requested
            f.write(f"{ping_entry}: {diff_str} [serf_rtt:{serf_rtt:.3f}ms, ping_rtt:{ping_rtt:.3f}ms]\n")

# Update with your actual file paths
ping_file = "ping_rtt_values.log"
serf_file = "serf_rtt_values_5D_16052025.log"
output_file = "serf_ping_rtt_diff.log"

compare_logs(ping_file, serf_file, output_file)
