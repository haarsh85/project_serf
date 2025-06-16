import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator

def process_files(file_group, data_type='absolute'):
    """Process a group of log files and return sorted values for plotting"""
    all_data = {}
    
    for filepath, dimension in file_group:
        differences = []
        
        with open(filepath, "r") as f:
            for line in f:
                if data_type == 'absolute':
                    match = re.search(r'([+-]?\d+\.\d+)\s*ms\s*\[serf_rtt:', line)
                else:  # relative
                    match = re.search(r'(\d+\.\d+)\s*\[serf_rtt:', line)
                
                if match:
                    value = float(match.group(1))
                    differences.append(value)
        
        if not differences:
            print(f"[Warning] No data found in file: {filepath}")
        
        all_data[dimension] = np.sort(differences)
    
    return all_data

def plot_absolute_cdf(data_dict, filename):
    """Generate CDF plot for absolute differences with all requested markings"""
    plt.figure(figsize=(12, 7))
    colors = {'2D': 'blue', '5D': 'orange'}
    
    legend_handles = []
    legend_labels = []
    
    percentiles = {}
    
    for dim in ['2D', '5D']:
        if dim not in data_dict or len(data_dict[dim]) == 0:
            print(f"[Warning] No data for {dim}, skipping plot for this dataset.")
            continue

        values = data_dict[dim]
        y = np.arange(1, len(values) + 1) / len(values)
        
        line, = plt.plot(values, y,
                        color=colors[dim],
                        linestyle='-',
                        linewidth=2,
                        label=dim)
        legend_handles.append(line)
        legend_labels.append(dim)
        
        min_val = np.min(values)
        max_val = np.max(values)
        median_val = np.percentile(values, 50)
        p80_val = np.percentile(values, 80)
        percentiles[dim] = (median_val, p80_val)
        
        y_min = np.interp(min_val, values, y)
        y_max = np.interp(max_val, values, y)
        
        # Min/max vertical lines (from x-axis)
        plt.vlines(min_val, ymin=plt.ylim()[0], ymax=y_min, 
                  colors=colors[dim], linestyles=':', linewidth=1)
        plt.vlines(max_val, ymin=plt.ylim()[0], ymax=y_max, 
                  colors=colors[dim], linestyles=':', linewidth=1)
        
        # Min value text (rotated 90, above line)
        plt.text(min_val, y_min + 0.02, f'{min_val:.3f}ms',
                 ha='center', va='bottom', color='black', fontsize=9, rotation=90)
        # Max value text (rotated 90, just below plot line)
        plt.text(max_val, y_max - 0.03, f'{max_val:.3f}ms',
                 ha='center', va='top', color='black', fontsize=9, rotation=90)
        
        # Median and 80th percentile markers with dotted lines
        for val, perc in [(median_val, 0.5), (p80_val, 0.8)]:
            y_val = np.interp(val, values, y)
            # Horizontal dotted line to the curve
            plt.hlines(perc, xmin=plt.xlim()[0], xmax=val,
                      colors=colors[dim], linestyles=':', linewidth=1)
            # Vertical dotted line down from the curve
            plt.vlines(val, ymin=plt.ylim()[0], ymax=perc,
                      colors=colors[dim], linestyles=':', linewidth=1)

    if not legend_handles:
        print(f"[Error] No data to plot. Plot skipped.")
        return

    plt.xlabel('Absolute Difference (Serf RTT - Actual RTT) (ms)', fontsize=12)
    plt.ylabel('Cumulative Probability', fontsize=12)
    plt.title('CDF of Absolute RTT Differences', fontsize=14)
    
    all_values = np.concatenate(list(data_dict.values()))
    x_padding = 0.05 * (np.max(all_values) - np.min(all_values)) if len(all_values) > 1 else 1
    plt.xlim(left=np.min(all_values) - x_padding, 
             right=np.max(all_values) + x_padding)
    plt.ylim(bottom=-0.05, top=1.05)
    
    plt.legend(legend_handles, legend_labels, loc='lower right')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Add combined percentile annotations above horizontal lines
    if '2D' in percentiles and '5D' in percentiles:
        # Add small offset from y-axis
        x_offset = (plt.xlim()[1] - plt.xlim()[0]) * 0.01  # 1% of axis width

        # 50% annotation
        median_text = f"50%: {percentiles['2D'][0]:.3f}ms (2D) / {percentiles['5D'][0]:.3f}ms (5D)"
        plt.text(plt.xlim()[0] + x_offset, 0.52, median_text,
                 ha='left', va='bottom', fontsize=9, color='black')

        # 80% annotation
        p80_text = f"80%: {percentiles['2D'][1]:.3f}ms (2D) / {percentiles['5D'][1]:.3f}ms (5D)"
        plt.text(plt.xlim()[0] + x_offset, 0.82, p80_text,
                 ha='left', va='bottom', fontsize=9, color='black')

    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Absolute error plot saved to {filename}")

def plot_relative_cdf(data_dict, filename):
    """Generate CDF plot for relative differences with Vivaldi-style formatting"""
    plt.figure(figsize=(12, 7))
    colors = {'2D': 'blue', '5D': 'orange'}
    
    for dim in ['2D', '5D']:
        if dim not in data_dict or len(data_dict[dim]) == 0:
            print(f"[Warning] No data for {dim}, skipping plot for this dataset.")
            continue

        values = data_dict[dim]
        y = np.arange(1, len(values) + 1) / len(values)
        plt.plot(values, y,
                color=colors[dim],
                linestyle='-',
                linewidth=2,
                label=dim)
    
    plt.xlabel('Relative Error (|Serf - Actual| / Actual)', fontsize=12)
    plt.ylabel('Cumulative Probability', fontsize=12)
    plt.title('CDF of Relative RTT Differences', fontsize=14)
    
    plt.xlim(0, 3)
    plt.xticks(np.arange(0, 3.1, 0.5))
    
    ax = plt.gca()
    ax.xaxis.set_minor_locator(MultipleLocator(0.1))
    ax.tick_params(which='minor', length=3, color='black')
    
    plt.legend(loc='lower right')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Relative error plot saved to {filename}")

# ========================
# Main Processing
# ========================

# Process absolute differences
absolute_files = [
    ('serf_ping_rtt_absolute_diff_2D.log', '2D'),
    ('serf_ping_rtt_absolute_diff_5D.log', '5D')
]
absolute_data = process_files(absolute_files, data_type='absolute')

# Calculate and print percentiles for absolute error (RTT in milliseconds)
print("\n[Absolute Error Statistics (in ms)]")
for dim in ['2D', '5D']:
    if dim in absolute_data and len(absolute_data[dim]) > 0:
        abs_errors = absolute_data[dim]
        median = np.percentile(abs_errors, 50)
        p80 = np.percentile(abs_errors, 80)
        print(f"{dim}: Median = {median:.3f} ms, 80th percentile = {p80:.3f} ms")
    else:
        print(f"{dim}: No data available.")

plot_absolute_cdf(absolute_data, 'absolute_errors_comparison.png')

# Process relative differences
relative_files = [
    ('serf_ping_rtt_relative_diff_2D.log', '2D'),
    ('serf_ping_rtt_relative_diff_5D.log', '5D')
]
relative_data = process_files(relative_files, data_type='relative')

# Calculate and print percentiles for relative error
print("\n[Relative Error Statistics (as percentage)]")
for dim in ['2D', '5D']:
    if dim in relative_data and len(relative_data[dim]) > 0:
        rel_errors = relative_data[dim]
        median_raw = np.percentile(rel_errors, 50)
        p80_raw = np.percentile(rel_errors, 80)
        median_pct = median_raw * 100
        p80_pct = p80_raw * 100
        print(f"{dim}: Median = {median_pct:.2f}% ({median_raw:.3f}), "
              f"80th percentile = {p80_pct:.2f}% ({p80_raw:.3f})")
    else:
        print(f"{dim}: No data available.")

plot_relative_cdf(relative_data, 'relative_errors_comparison.png')
