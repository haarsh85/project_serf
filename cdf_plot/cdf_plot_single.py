import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator
import os

def process_log(input_file, output_file, is_relative=False):
    differences = []
    diff_lines = []

    with open(input_file, "r") as f:
        for line in f:
            if is_relative:
                match = re.search(r'(\d+\.\d+)\s*\[serf_rtt:', line)
            else:
                match = re.search(r'([+-]?\d+\.\d+)\s*ms\s*\[serf_rtt:', line)

            if match:
                diff = float(match.group(1))
                differences.append(diff)
                diff_lines.append((diff, line.strip()))

    if not differences:
        print(f"Warning: No RTT differences found in {input_file}")
        return

    # Compute metrics
    metrics = {
        "Total Samples": len(differences),
        "Mean Difference": np.mean(differences),
        "Median Difference": np.median(differences),
        "Standard Deviation": np.std(differences),
        "Minimum Difference": np.min(differences),
        "Maximum Difference": np.max(differences),
        "50th Percentile (Median)": np.percentile(differences, 50),
        "80th Percentile": np.percentile(differences, 80),
        "90th Percentile": np.percentile(differences, 90),
        "95th Percentile": np.percentile(differences, 95),
        "% Overestimations (Serf > Actual)": (sum(d > 0 for d in differences) / len(differences)) * 100,
        "% Underestimations (Serf < Actual)": (sum(d < 0 for d in differences) / len(differences)) * 100,
    }

    print(f"\nKey Metrics for {os.path.basename(input_file)}:")
    for key, value in metrics.items():
        if key == "Total Samples":
            print(f"{key}: {int(value)}")
        elif "%" in key:
            print(f"{key}: {value:.3f}%")
        else:
            unit = " ms" if not is_relative else ""
            print(f"{key}: {value:.3f}{unit}")

    # Save to output file
    with open(output_file, "w") as out:
        out.write(f"Source file: {os.path.basename(input_file)}\n\n")
        headers = list(metrics.keys())
        out.write(" | ".join(f"{h:^30}" for h in headers) + "\n")
        out.write("-" * (len(headers) * 33) + "\n")

        values = []
        for key in headers:
            value = metrics[key]
            if key == "Total Samples":
                values.append(f"{int(value):^30}")
            elif "%" in key:
                values.append(f"{value:.3f}%".center(30))
            else:
                unit = " ms" if not is_relative else ""
                values.append(f"{value:.3f}{unit}".center(30))
        out.write(" | ".join(values) + "\n\n")

        min_diff, min_line = min(diff_lines, key=lambda x: x[0])
        max_diff, max_line = max(diff_lines, key=lambda x: x[0])
        out.write("Nodes with Minimum and Maximum Difference:\n")
        out.write(f"Minimum Difference: {min_diff:.3f}{' ms' if not is_relative else ''} → {min_line}\n")
        out.write(f"Maximum Difference: {max_diff:.3f}{' ms' if not is_relative else ''} → {max_line}\n")

    print("\nNodes with Minimum and Maximum Difference:")
    print(f"Minimum Difference: {min_diff:.3f}{' ms' if not is_relative else ''} → {min_line}")
    print(f"Maximum Difference: {max_diff:.3f}{' ms' if not is_relative else ''} → {max_line}")

    # Generate appropriate plot
    sorted_diffs = np.sort(differences)
    plot_filename = f"serf_rtt_accuracy_cdf_{'relative' if is_relative else 'signed'}.png"
    
    if is_relative:
        plot_relative_cdf(sorted_diffs, plot_filename)
    else:
        plot_signed_cdf(sorted_diffs, min_diff, max_diff, plot_filename)

def plot_signed_cdf(sorted_diffs, min_val, max_val, filename):
    """Create signed CDF plot with Code A's styling"""
    plt.figure(figsize=(12, 7))
    n = len(sorted_diffs)
    y_values = np.arange(1, n + 1) / n

    # Main plot
    plt.plot(sorted_diffs, y_values, color='blue', linewidth=2)
    
    # Axis configuration
    plt.xlabel('Signed Difference (Serf RTT - Actual RTT) (ms)', fontsize=12)
    plt.ylabel('Cumulative Probability', fontsize=12)
    plt.title('CDF of Signed RTT Differences', fontsize=14)
    
    # Dynamic x-axis limits with padding
    x_padding = 0.05 * (max_val - min_val) if len(sorted_diffs) > 1 else 1
    plt.xlim(left=min_val - x_padding, right=max_val + x_padding)
    plt.ylim(-0.05, 1.05)
    
    # Min/max annotations
    y_min = np.interp(min_val, sorted_diffs, y_values)
    y_max = np.interp(max_val, sorted_diffs, y_values)
    
    plt.vlines(min_val, 0, y_min, colors='blue', linestyles=':', linewidth=1)
    plt.vlines(max_val, 0, y_max, colors='blue', linestyles=':', linewidth=1)
    
    plt.text(min_val, y_min + 0.02, f'{min_val:.3f}ms',
             ha='center', va='bottom', fontsize=9, rotation=90)
    plt.text(max_val, y_max - 0.03, f'{max_val:.3f}ms',
             ha='center', va='top', fontsize=9, rotation=90)

    # Zero reference line
    plt.axvline(0, color='red', linestyle='--', linewidth=1, label="Perfect Match")
    plt.legend(loc='lower right')
    
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Signed CDF plot saved to {filename}")

def plot_relative_cdf(sorted_diffs, filename):
    """Create relative CDF plot with Code A's styling"""
    plt.figure(figsize=(12, 7))
    n = len(sorted_diffs)
    y_values = np.arange(1, n + 1) / n

    # Main plot
    plt.plot(sorted_diffs, y_values, color='blue', linewidth=2)
    
    # Axis configuration
    plt.xlabel('Relative Error (|Serf - Actual| / Actual)', fontsize=12)
    plt.ylabel('Cumulative Probability', fontsize=12)
    plt.title('CDF of Relative RTT Differences', fontsize=14)
    
    # Fixed x-axis limits
    plt.xlim(0, 3)
    plt.ylim(-0.05, 1.05)
    
    # Tick configuration
    plt.xticks(np.arange(0, 3.1, 0.5))
    ax = plt.gca()
    ax.xaxis.set_minor_locator(MultipleLocator(0.1))
    ax.tick_params(which='minor', length=3, color='black')
    
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Relative CDF plot saved to {filename}")

# --------- Main Execution ---------
# Signed error file
signed_input = "signed_error_logs/serf_ping_rtt_signed_diff_2D_13062025.log"
signed_output = "metrics.txt"

# Relative error file
relative_input = "relative_error_logs/serf_ping_rtt_relative_diff_2D_13062025.log"
relative_output = "metrics_relative.txt"

process_log(signed_input, signed_output, is_relative=False)
process_log(relative_input, relative_output, is_relative=True)