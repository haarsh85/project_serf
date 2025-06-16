import re
from collections import OrderedDict

def process_sorted_log(input_path, output_path):
    """Process sorted log to create RTT-ordered version without test durations."""
    with open(input_path, "r") as f:
        lines = f.readlines()

    output_lines = []
    current_header = None
    current_section = []

    for line in lines:
        if line.startswith("==="):
            if current_header is not None:
                processed = process_section(current_section)
                output_lines.append(current_header)
                output_lines.extend(processed)
            current_header = line
            current_section = []
        elif line.strip():
            current_section.append(line)

    # Process final section
    if current_header is not None:
        processed = process_section(current_section)
        output_lines.append(current_header)
        output_lines.extend(processed)

    with open(output_path, "w") as f:
        f.writelines(output_lines)

def process_section(section_lines):
    """Process a section while properly grouping by source node."""
    # Regex to capture: [network] node (IP) → [network] node (IP): RTTms
    pattern = re.compile(
        r'^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) '  # Timestamp
        r'(\[.+?\]\sclab-nebula-serf\d+\s\([^)]+\))'  # Source node
        r'\s→\s'
        r'(\[.+?\]\sclab-nebula-serf\d+\s\([^)]+\)):\s'  # Dest node
        r'([\d.]+)ms'  # RTT
    )

    source_groups = OrderedDict()
    
    for line in section_lines:
        match = pattern.search(line)
        if not match:
            continue

        timestamp, source, dest, rtt = match.groups()
        rtt = float(rtt)
        
        # Rebuild line without test duration
        clean_line = f"{timestamp} {source} → {dest}: {rtt:.3f}ms\n"
        
        # Group by source node identifier (without timestamp)
        if source not in source_groups:
            source_groups[source] = []
        source_groups[source].append((rtt, clean_line))

    # Sort each source group by RTT and flatten
    sorted_lines = []
    for source, entries in source_groups.items():
        # Sort by RTT ascending, then timestamp ascending
        entries.sort(key=lambda x: (x[0], x[1]))
        sorted_lines.extend([entry[1] for entry in entries])
    
    return sorted_lines

# Execute the processing
process_sorted_log("ping_sorted_rtt_new.log", "closer_nodes_per_ping_rtt.log")