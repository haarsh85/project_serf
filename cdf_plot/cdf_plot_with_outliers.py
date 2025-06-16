# ========================
# CONFIGURATION PARAMETERS
# ========================
NUM_POINTS = 10            # Number of points per group (positive/negative/close)
COLOR_START = 0.8          # Darkest color value (0-1)
COLOR_END = 0.2            # Lightest color value (0-1) 
MARKER_SIZE = 80           # Size of scatter plot markers
LEGEND_COLUMNS = 1         # Number of columns in legend
LEGEND_FONTSIZE = 8        # Legend font size

# Color gradient ranges
POS_COLOR_RANGE = (0.8, 0.2)  # Red gradient (dark to light)
NEG_COLOR_RANGE = (0.8, 0.2)  # Blue gradient (dark to light)
CLOSE_COLOR_RANGE = (0.3, 0.7)  # Green gradient

import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# ----------------------------
# 1. Data Extraction and Processing
# ----------------------------
node_data = []
differences = []

with open("signed_error_logs/serf_ping_rtt_signed_diff_2D_26052025.log", "r") as f:
    for line in f:
        if line.startswith("===") or not line.strip():
            continue
            
        #REGEX for log lines without spaces: EG: [net_1] clab-nebula-serf1 (10.0.1.10) → [net_1] clab-nebula-serf2 (10.0.1.11): +4.611ms [serf_rtt:12.318ms, ping_rtt:7.707ms]    
        # match = re.match(
        #     r'(\[.*?\]) (clab-nebula-serf\d+) \(.*?\) → (\[.*?\]) (clab-nebula-serf\d+) \(.*?\): ([+-]?\d+\.\d+)ms \[serf_rtt:.*?ping_rtt:.*?\]',
        #     line
        # )

        #REGEX for log lines with spaces: EG: [net_1] clab-nebula-serf1 (10.0.1.10) → [net_1] clab-nebula-serf2 (10.0.1.11): +14.365 ms [serf_rtt: 22.072 ms, ping_rtt: 7.707 ms]
        match = re.match(
            r'(\[.*?\]) (clab-nebula-serf\d+) \(.*?\) → (\[.*?\]) (clab-nebula-serf\d+) \(.*?\): ([+-]?\d+\.\d+)\s*ms \[serf_rtt:\s*[\d.]+\s*ms,\s*ping_rtt:\s*[\d.]+\s*ms\]',
            line
        )
        
        if match:
            src_net, src_node, dst_net, dst_node, diff = match.groups()
            node_data.append({
                "full_line": line.strip(),
                "src_node": src_node,
                "dst_node": dst_node,
                "diff": float(diff),
                "abs_diff": abs(float(diff))
            })
            differences.append(float(diff))

# ----------------------------
# 2. Calculate Key Metrics
# ----------------------------
sorted_diffs = np.sort(differences)
cdf = np.arange(1, len(sorted_diffs)+1) / len(sorted_diffs)
percentiles = {
    "50th": np.percentile(differences, 50),
    "80th": np.percentile(differences, 80),
    "90th": np.percentile(differences, 90),
    "95th": np.percentile(differences, 95)
}

# Get min/max values
min_diff = sorted_diffs[0]
max_diff = sorted_diffs[-1]
min_cdf = cdf[0]
max_cdf = cdf[-1]

# ----------------------------
# 3. Identify Node Groups
# ----------------------------
# Positive outliers (darkest first)
pos_outliers = sorted([d for d in node_data if d["diff"] > 0], 
                     key=lambda x: x["diff"], reverse=True)[:NUM_POINTS]
pos_colors = plt.cm.Reds(np.linspace(*POS_COLOR_RANGE, NUM_POINTS))

# Negative outliers (darkest first)
neg_outliers = sorted([d for d in node_data if d["diff"] < 0], 
                     key=lambda x: x["diff"])[:NUM_POINTS]
neg_colors = plt.cm.Blues(np.linspace(*NEG_COLOR_RANGE, NUM_POINTS))

# Closest matches
close_matches = sorted(node_data, key=lambda x: x["abs_diff"])[:NUM_POINTS]
close_colors = plt.cm.Greens(np.linspace(*CLOSE_COLOR_RANGE, NUM_POINTS))

# ----------------------------
# 4. Enhanced Plotting
# ----------------------------
plt.figure(figsize=(14, 7))  # Wider figure for more points
ax = plt.gca()

# Main CDF line
plt.plot(sorted_diffs, cdf, color='grey', linewidth=1.5, alpha=0.7)

# Percentile lines
for label, value in percentiles.items():
    plt.axvline(value, color='grey', linestyle=':', linewidth=1)
    plt.text(value, 0.95, f'{label}({value:.3f}ms)', 
            rotation=90, ha='right', va='top', fontsize=8)

# Min/Max difference markers
plt.axvline(min_diff, ymin=0, ymax=min_cdf, color='grey', linestyle=':', linewidth=1)
plt.text(min_diff, min_cdf + 0.02, f'Min: {min_diff:.3f}ms', 
        rotation=90, ha='right', va='bottom', fontsize=8)

plt.axvline(max_diff, ymin=0, ymax=max_cdf, color='grey', linestyle=':', linewidth=1)
plt.text(max_diff, max_cdf + 0.02, f'Max: {max_diff:.3f}ms', 
        rotation=90, ha='right', va='bottom', fontsize=8)

# Plot groups with distinct markers
def plot_group(data, colors, marker):
    for d, c in zip(data, colors):
        idx = np.where(sorted_diffs == d["diff"])[0][0]
        plt.scatter(d["diff"], cdf[idx], 
                   color=c, s=MARKER_SIZE, edgecolor='black',
                   marker=marker, zorder=5)

plot_group(pos_outliers, pos_colors, 'o')
plot_group(neg_outliers, neg_colors, 'o')
plot_group(close_matches, close_colors, 'o')

# ----------------------------
# 5. Legend Construction (Modified)
# ----------------------------
legend_elements = [
    Line2D([0], [0], color='w', marker='', 
          label='Serf RTT > Real RTT', markersize=0),
    *[Line2D([0], [0], marker='o', color='w', 
            label=f"{d['src_node'].split('-')[-1]} → {d['dst_node'].split('-')[-1]} (+{d['diff']:.3f}ms)",
            markerfacecolor=c, markersize=8, markeredgecolor='black')
      for d, c in zip(pos_outliers, pos_colors)],
    
    Line2D([0], [0], color='w', marker='', 
          label='\nSerf RTT < Real RTT', markersize=0),
    *[Line2D([0], [0], marker='o', color='w', 
            label=f"{d['src_node'].split('-')[-1]} → {d['dst_node'].split('-')[-1]} ({d['diff']:.3f}ms)",
            markerfacecolor=c, markersize=8, markeredgecolor='black')
      for d, c in zip(neg_outliers, neg_colors)],
    
    Line2D([0], [0], color='w', marker='', 
          label='\nSerf RTT ≈ Real RTT', markersize=0),
    *[Line2D([0], [0], marker='o', color='w', 
            label=f"{d['src_node'].split('-')[-1]} → {d['dst_node'].split('-')[-1]} ({d['diff']:.3f}ms)",
            markerfacecolor=c, markersize=8, markeredgecolor='black')
      for d, c in zip(close_matches, close_colors)]
]

legend = ax.legend(handles=legend_elements, loc='center left',
                  bbox_to_anchor=(1.02, 0.5), title="Node Details",
                  ncol=LEGEND_COLUMNS, fontsize=LEGEND_FONTSIZE,
                  columnspacing=0.8, handletextpad=0.5)

# ----------------------------
# 6. Final Formatting & Output
# ----------------------------
plt.xlabel('Difference (Serf RTT - Actual RTT) (ms)', fontsize=12)
plt.ylabel('Cumulative Probability', fontsize=12)
plt.title('CDF of Serf 2D RTT Differences with Outliers', fontsize=14)
plt.grid(True, linestyle='--', alpha=0.5)
plt.axvline(0, color='green', linestyle='--', linewidth=1)
plt.xlim(left=min(differences)-5, right=max(differences)+5)

# Save outliers to file
with open("outliers.txt", "w") as f:
    f.write("=== Serf RTT > Real RTT ===\n")
    for d in pos_outliers:
        f.write(f"{d['full_line']}\n")
    
    f.write("\n=== Serf RTT < Real RTT ===\n")
    for d in neg_outliers:
        f.write(f"{d['full_line']}\n")
    
    f.write("\n=== Serf RTT ≈ Real RTT ===\n")
    for d in close_matches:
        f.write(f"{d['full_line']}\n")

plt.savefig(f'serf_cdf_{NUM_POINTS}_points.png', dpi=300, bbox_inches='tight')
print(f"Generated serf_cdf_{NUM_POINTS}_points.png")