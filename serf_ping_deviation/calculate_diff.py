import re
from collections import defaultdict

def parse_log_file(file_path):
    """Parse log files into structured format with directional awareness"""
    entries = defaultdict(dict)
    current_section = None
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # Handle section headers
            if line.startswith("==="):
                current_section = line.strip('= ')
                continue
                
            # Extract node pairs and RTT using regex
            match = re.match(
                r'^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} )?'  # Optional timestamp
                r'\[([^\]]+)\] ([^\s]+) \(([^)]+)\) → '       # From node
                r'\[([^\]]+)\] ([^\s]+) \(([^)]+)\): '        # To node
                r'([\d.]+)ms.*',                              # RTT and optional duration
                line
            )
            if match:
                _, net_from, from_node, from_ip, net_to, to_node, to_ip, rtt = match.groups()
                key = (current_section, from_node, to_node)
                entries[key] = float(rtt)
                
    return entries

def generate_diff_log(ping_file, serf_file, output_file):
    """Generate difference log file comparing Serf and Ping RTTs"""
    # Parse both log files
    ping_data = parse_log_file(ping_file)
    serf_data = parse_log_file(serf_file)
    
    # Group entries by section for organized output
    section_entries = defaultdict(list)
    
    # Find common keys and calculate differences
    for key in serf_data:
        if key in ping_data:
            section, from_node, to_node = key
            serf_rtt = serf_data[key]
            ping_rtt = ping_data[key]
            diff = serf_rtt - ping_rtt
            
            # Format the difference string
            sign = '+' if diff >= 0 else '-'
            diff_str = f"{sign}{abs(diff):.3f}ms"
            
            entry = (
                f"[{section}] {from_node} → {to_node}: "
                f"{diff_str} [serf_rtt:{serf_rtt:.3f}ms, ping_rtt:{ping_rtt:.3f}ms]"
            )
            section_entries[section].append(entry)
    
    # Write output preserving section order
    with open(output_file, 'w') as f:
        # Write header
        f.write("=== RTT Differences (Serf - Real) ===\n\n")
        
        # Write sections and their entries
        for section in sorted(section_entries.keys()):
            f.write(f"=== {section} ===\n")
            for entry in section_entries[section]:
                f.write(f"{entry}\n")
            f.write("\n")

# Example usage
if __name__ == "__main__":
    generate_diff_log(
        ping_file="ping_sorted_rtt_new.log",
        serf_file="serf_rtt_values_2D.log",
        output_file="rtt_differences.log"
    )