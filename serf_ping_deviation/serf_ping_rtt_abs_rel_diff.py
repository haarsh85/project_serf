import re
import math

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

def compare_logs(ping_file, serf_file, output_file_abs, output_file_rel, output_file_signed):
    ping_lines = parse_log_lines(ping_file)
    serf_lines = parse_log_lines(serf_file)

    with open(output_file_abs, "w") as f_abs, open(output_file_rel, "w") as f_rel, open(output_file_signed, "w") as f_signed:
        for (ping_entry, ping_rtt), (serf_entry, serf_rtt) in zip(ping_lines, serf_lines):
            # Handle section headers and errors
            if ping_rtt is None or serf_rtt is None:
                f_abs.write(ping_entry + "\n")
                f_rel.write(ping_entry + "\n")
                f_signed.write(ping_entry + "\n")
                continue
            
            # Signed error
            signed_error = serf_rtt - ping_rtt
            abs_error = abs(signed_error)

            # Absolute error file: only absolute positive value (no sign)
            abs_error_str = f"{abs_error:.3f}"
            
            # Signed error file: keep sign (+/-)
            sign = "+" if signed_error >= 0 else "-"
            signed_error_str = f"{sign}{abs_error:.3f} ms"
            
            # Relative error (avoid division by zero)
            if ping_rtt == 0:
                relative_error = float('nan')
                rel_str = "NaN"
            else:
                relative_error = abs_error / ping_rtt
                rel_str = f"{relative_error:.3f}"
            
            # Write to absolute error file (no sign)
            f_abs.write(f"{ping_entry}: {abs_error_str} [serf_rtt: {serf_rtt:.3f} ms, ping_rtt: {ping_rtt:.3f} ms]\n")

            # Write to relative error file
            f_rel.write(f"{ping_entry}: {rel_str} [serf_rtt: {serf_rtt:.3f} ms, ping_rtt: {ping_rtt:.3f} ms]\n")

            # Write to signed error file
            f_signed.write(f"{ping_entry}: {signed_error_str} [serf_rtt: {serf_rtt:.3f} ms, ping_rtt: {ping_rtt:.3f} ms]\n")


# Update with your actual file paths
ping_file = "ping_rtt_values.log"
serf_file = "serf_rtt_values_2D_13062025.log"
output_file_abs = "serf_ping_rtt_absolute_diff.log"
output_file_rel = "serf_ping_rtt_relative_diff.log"
output_file_signed = "serf_ping_rtt_signed_diff.log"

compare_logs(ping_file, serf_file, output_file_abs, output_file_rel, output_file_signed)
