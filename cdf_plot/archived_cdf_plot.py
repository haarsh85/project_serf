import re
import numpy as np
import matplotlib.pyplot as plt

# ----------------------------
# 1. Data Extraction
# ----------------------------
differences = []
diff_lines = []
exact_match_lines = []

with open("serf_ping_rtt_diff_5D.log", "r") as f:
    for line in f:
        # Extract difference (supports both + and - values)
        match = re.search(r'([+-]?\d+\.\d+)ms\s*\[serf_rtt:', line)
        if match:
            diff = float(match.group(1))
            differences.append(diff)
            diff_lines.append((diff, line.strip()))
            
            # Track exact matches
            if diff == 0:
                exact_match_lines.append(line.strip())

# ----------------------------
# 2. Compute Metrics
# ----------------------------
sorted_diffs = sorted(differences)
metrics = {
    "Total Samples": len(differences),
    "Mean Difference": np.mean(differences),
    "Median Difference": np.median(differences),
    "Standard Deviation": np.std(differences),
    "Minimum Difference": np.min(differences),
    "Maximum Difference": np.max(differences),
    "25th Percentile": np.percentile(differences, 25),
    "50th Percentile (Median)": np.percentile(differences, 50),
    "80th Percentile": np.percentile(differences, 80),
    "90th Percentile": np.percentile(differences, 90),
    "95th Percentile": np.percentile(differences, 95),
    "% Overestimations (Serf > Actual)": (sum(d > 0 for d in differences) / len(differences)) * 100,
    "% Underestimations (Serf < Actual)": (sum(d < 0 for d in differences) / len(differences)) * 100,
}

# ----------------------------
# 3. Print Metrics
# ----------------------------
print("\nKey Metrics:")
for key, value in metrics.items():
    if key == "Total Samples":
        print(f"{key}: {int(value)}")
    elif "%" in key:
        print(f"{key}: {value:.3f}%")
    else:
        print(f"{key}: {value:.3f} ms")

# Print exact matches if they exist
# if exact_match_lines:
#     print(f"\nExact Matches (Serf RTT = Actual RTT) - {len(exact_match_lines)} cases:")
#     for idx, line in enumerate(exact_match_lines, 1):
#         print(f"[{idx}] {line}")

# ----------------------------
# NEW: Print Min/Max Difference Node Pairs
# ----------------------------
min_diff, min_line = min(diff_lines, key=lambda x: x[0])
max_diff, max_line = max(diff_lines, key=lambda x: x[0])

print("\nNodes with Minimum and Maximum Difference:")
print(f"Minimum Difference: {min_diff:.3f} ms → {min_line}")
print(f"Maximum Difference: {max_diff:.3f} ms → {max_line}")

# ----------------------------
# 4. Plotting (Dynamic Annotations)
# ----------------------------
n = len(sorted_diffs)
x_values = np.array(sorted_diffs)
y_values = np.arange(1, n + 1) / n

plt.figure(figsize=(12, 7))
plt.plot(x_values, y_values, color='blue', linewidth=1.5)
plt.xlabel('Difference (Serf RTT - Actual RTT) (ms)', fontsize=12)
plt.ylabel('Cumulative Probability', fontsize=12)
plt.title('CDF of Serf RTT Differences', fontsize=14)
plt.grid(True, linestyle='--', alpha=0.7)

# Dynamic annotations for key percentiles and max
percentiles_to_annotate = {
    "25th": 25,
    "50th": 50,
    "80th": 80,
    "90th": 90,
    "95th": 95,
    "Max": None  # Special case for np.max
}

for label, p in percentiles_to_annotate.items():
    if p is None:
        value = np.max(differences)
    else:
        value = np.percentile(differences, p)
    
    plt.axvline(value, color='grey', linestyle=':', linewidth=1)
    plt.text(
        value, 0.95,
        f"{label} ({value:.3f} ms)",
        rotation=90, ha='right', va='top', fontsize=8
    )

# Add min annotation
plt.axvline(min_diff, color='grey', linestyle=':', linewidth=1)
plt.text(
    min_diff, 0.95,
    f"Min ({min_diff:.3f} ms)",
    rotation=90, ha='right', va='top', fontsize=8
)

plt.axvline(0, color='red', linestyle='--', linewidth=1, label="Perfect Match")
plt.legend(loc='lower right', bbox_to_anchor=(1.0, -0.15))

# Adjust axis limits to show full data range
plt.xlim(left=np.min(differences) - 5, right=np.max(differences) + 5)

# Save and show
plt.savefig('serf_rtt_accuracy_cdf_final.png', dpi=300, bbox_inches='tight')
plt.show()
