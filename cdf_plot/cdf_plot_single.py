import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import os

def process_log(input_file, output_file, is_relative=False, is_absolute=False):
    differences = []
    diff_lines = []

    with open(input_file, "r") as f:
        for line in f:
            if is_relative:
                match = re.search(r'(\d+\.\d+)\s*\[serf_rtt:', line)
            elif is_absolute:
                match = re.search(r':\s*([0-9.]+)\s+\[serf_rtt:', line)
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
    }

    # Over/underestimation only for signed errors
    if not is_relative and not is_absolute:
        metrics["% Overestimations (Serf > Actual)"] = (sum(d > 0 for d in differences) / len(differences)) * 100
        metrics["% Underestimations (Serf < Actual)"] = (sum(d < 0 for d in differences) / len(differences)) * 100

    print(f"\nKey Metrics for {os.path.basename(input_file)}:")
    for key, value in metrics.items():
        if key == "Total Samples":
            print(f"{key}: {int(value)}")
        elif "%" in key:
            print(f"{key}: {value:.3f}%")
        else:
            unit = " ms" if not is_relative else ""
            print(f"{key}: {value:.3f}{unit}")

    # Write output file
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

    # Generate plot
    sorted_diffs = np.sort(differences)
    if is_relative:
        plot_filename = "serf_rtt_accuracy_cdf_relative.png"
        plot_relative_cdf(sorted_diffs, plot_filename)
    elif is_absolute:
        plot_filename = "serf_rtt_accuracy_cdf_absolute.png"
        plot_absolute_cdf(sorted_diffs, plot_filename)
    else:
        plot_filename = "serf_rtt_accuracy_cdf_signed.png"
        plot_signed_cdf(sorted_diffs, min_diff, max_diff, plot_filename)

def plot_signed_cdf(sorted_diffs, min_val, max_val, filename):
    plt.figure(figsize=(12, 7))
    n = len(sorted_diffs)
    y_values = np.arange(1, n + 1) / n
    plt.plot(sorted_diffs, y_values, color='blue', linewidth=2)

    plt.xlabel('Signed Difference (Serf RTT - Actual RTT) (ms)', fontsize=12)
    plt.ylabel('Cumulative Probability', fontsize=12)
    plt.title('CDF of Signed RTT Differences', fontsize=14)

    x_padding = 0.05 * (max_val - min_val) if len(sorted_diffs) > 1 else 1
    plt.xlim(left=min_val - x_padding, right=max_val + x_padding)
    plt.ylim(-0.05, 1.05)

    y_min = np.interp(min_val, sorted_diffs, y_values)
    y_max = np.interp(max_val, sorted_diffs, y_values)
    plt.vlines(min_val, 0, y_min, colors='blue', linestyles=':', linewidth=1)
    plt.vlines(max_val, 0, y_max, colors='blue', linestyles=':', linewidth=1)
    plt.text(min_val, y_min + 0.02, f'{min_val:.3f}ms', ha='center', va='bottom', fontsize=9, rotation=90)
    plt.text(max_val, y_max - 0.03, f'{max_val:.3f}ms', ha='center', va='top', fontsize=9, rotation=90)

    plt.axvline(0, color='red', linestyle='--', linewidth=1, label="Perfect Match")
    plt.legend(loc='lower right')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Signed CDF plot saved to {filename}")

def plot_relative_cdf(sorted_diffs, filename):
    plt.figure(figsize=(12, 7))
    n = len(sorted_diffs)
    y_values = np.arange(1, n + 1) / n
    plt.plot(sorted_diffs, y_values, color='blue', linewidth=2)

    plt.xlabel('Relative Error (|Serf - Actual| / Actual)', fontsize=12)
    plt.ylabel('Cumulative Probability', fontsize=12)
    plt.title('CDF of Relative RTT Differences', fontsize=14)

    plt.xlim(0, 3)
    plt.ylim(-0.05, 1.05)
    plt.xticks(np.arange(0, 3.1, 0.5))
    ax = plt.gca()
    ax.xaxis.set_minor_locator(MultipleLocator(0.1))
    ax.tick_params(which='minor', length=3, color='black')

    plt.grid(True, linestyle='--', alpha=0.7)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Relative CDF plot saved to {filename}")

def plot_absolute_cdf(sorted_diffs, filename):
    plt.figure(figsize=(12, 7))
    n = len(sorted_diffs)
    y_values = np.arange(1, n + 1) / n
    plt.plot(sorted_diffs, y_values, color='blue', linewidth=2)

    plt.xlabel('Absolute Error |Serf RTT - Actual RTT| (ms)', fontsize=12)
    plt.ylabel('Cumulative Probability', fontsize=12)
    plt.title('CDF of Absolute RTT Differences', fontsize=14)

    plt.xlim(left=0)
    plt.ylim(-0.05, 1.05)
    ax = plt.gca()
    ax.xaxis.set_minor_locator(MultipleLocator(0.1))
    ax.tick_params(which='minor', length=3, color='black')

    plt.grid(True, linestyle='--', alpha=0.7)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Absolute CDF plot saved to {filename}")

# --------- Main Execution ---------

# Signed error
signed_input = "signed_error_logs/serf_ping_rtt_signed_diff_14072025_x.log" #28062025_2
signed_output = "metrics_signed.txt"
process_log(signed_input, signed_output, is_relative=False)

# Relative error
relative_input = "relative_error_logs/serf_ping_rtt_relative_diff_14072025_x.log"
relative_output = "metrics_relative.txt"
process_log(relative_input, relative_output, is_relative=True)

# Absolute error
absolute_input = "absolute_error_logs/serf_ping_rtt_absolute_diff_14072025_x.log"
absolute_output = "metrics_absolute.txt"
process_log(absolute_input, absolute_output, is_absolute=True)
