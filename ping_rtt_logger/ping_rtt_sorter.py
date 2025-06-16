import re
from pathlib import Path

def extract_serf_id(line):
    """Extract serf IDs for sorting (serfX -> X)."""
    match = re.search(r"clab-nebula-serf(\d+).*→.*clab-nebula-serf(\d+)", line)
    if match:
        return int(match.group(1)), int(match.group(2))
    return float('inf'), float('inf')  # fallback for malformed lines

def sort_ping_log(input_path, output_path):
    with open(input_path, "r") as f:
        lines = f.readlines()

    sorted_lines = []
    current_section = []
    header = None

    for line in lines:
        if line.startswith("==="):  # New section header
            if header and current_section:
                current_section.sort(key=extract_serf_id)
                sorted_lines.append(header)
                sorted_lines.extend(current_section)
            header = line
            current_section = []
        elif line.strip() == "":
            continue
        else:
            current_section.append(line)

    # Don't forget to process the last section
    if header and current_section:
        current_section.sort(key=extract_serf_id)
        sorted_lines.append(header)
        sorted_lines.extend(current_section)

    # Write to new sorted log file
    with open(output_path, "w") as f:
        f.writelines(sorted_lines)

# Run the function
sort_ping_log("ping_rtt_values_new.log", "ping_sorted_rtt_new.log")
