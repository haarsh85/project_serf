import re
from collections import OrderedDict

def process_sorted_log(input_path, output_path):
    """Process log to create RTT-ordered version without headers or timestamps."""
    with open(input_path, "r") as f:
        lines = f.readlines()

    # Filter out header lines and empty lines
    ping_lines = [line.strip() for line in lines if not line.startswith("===") and line.strip()]

    # Process all ping lines to group by source and sort by RTT
    sorted_entries = process_ping_lines(ping_lines)

    with open(output_path, "w") as f:
        f.writelines(sorted_entries)

def process_ping_lines(ping_lines):
    """Process ping lines, group by source, sort by RTT, return sorted lines."""
    # Regex to extract source, destination, and RTT
    pattern = re.compile(
        r'^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} '  # Timestamp (ignored)
        r'(\[.+?\]\sclab-nebula-serf\d+\s\([^)]+\))'  # Source node
        r'\s→\s'
        r'(\[.+?\]\sclab-nebula-serf\d+\s\([^)]+\)):\s'  # Dest node
        r'([\d.]+)ms.*'  # RTT and ignore the rest
    )

    source_groups = OrderedDict()

    for line in ping_lines:
        match = pattern.match(line)
        if not match:
            continue  # Skip lines that don't match the pattern

        source, dest, rtt = match.groups()
        rtt = float(rtt)

        # Build the output line without timestamp or test duration
        clean_line = f"{source} → {dest}: {rtt:.3f}ms\n"

        # Group by source node
        if source not in source_groups:
            source_groups[source] = []
        source_groups[source].append((rtt, clean_line))

    # Sort each source's entries by RTT and flatten
    sorted_lines = []
    for source, entries in source_groups.items():
        # Sort by RTT ascending
        entries.sort(key=lambda x: x[0])
        # Add the sorted lines
        sorted_lines.extend([entry[1] for entry in entries])

    return sorted_lines

# Execute the processing
process_sorted_log("ping_sorted_rtt_bi_direct_new.log", "closer_nodes_per_ping_rtt.log")