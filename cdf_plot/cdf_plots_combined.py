import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator

def process_files(file_group, data_type='signed'):
    """Process a group of log files and return sorted values for plotting"""
    all_data = {}
    
    for filepath, dimension in file_group:
        differences = []
        
        with open(filepath, "r") as f:
            for line in f:
                if data_type == 'signed':
                    # Match signed values like "+14.365 ms" or "-5.234 ms"
                    match = re.search(r'([+-]?\d+\.\d+)\s*ms\s*\[serf_rtt:', line)
                elif data_type == 'absolute':
                    # Match absolute values like "14.365"
                    match = re.search(r'(\d+\.\d+)\s*\[serf_rtt:', line)
                elif data_type == 'relative':
                    # Match relative values like "1.864"
                    match = re.search(r'(\d+\.\d+)\s*\[serf_rtt:', line)
                
                if match:
                    value = float(match.group(1))
                    differences.append(value)
        
        if not differences:
            print(f"[Warning] No data found in file: {filepath}")
        
        all_data[dimension] = np.sort(differences)
    
    return all_data

def plot_signed_differences_cdf(data_dict, filename):
    """Generate CDF plot for signed differences (Serf RTT - Actual RTT)"""
    plt.figure(figsize=(12, 7))
    colors = {'2D': 'blue', '5D': 'orange'}
    
    legend_handles = []
    legend_labels = []
    
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

    if not legend_handles:
        print(f"[Error] No data to plot. Plot skipped.")
        return

    plt.xlabel('Signed Difference (Serf RTT - Actual RTT) (ms)', fontsize=12)
    plt.ylabel('Cumulative Probability', fontsize=12)
    plt.title('CDF of Signed RTT Differences', fontsize=14)
    
    all_values = np.concatenate(list(data_dict.values()))
    x_padding = 0.05 * (np.max(all_values) - np.min(all_values)) if len(all_values) > 1 else 1
    plt.xlim(left=np.min(all_values) - x_padding, 
             right=np.max(all_values) + x_padding)
    plt.ylim(bottom=-0.05, top=1.05)
    
    plt.legend(legend_handles, legend_labels, loc='lower right')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Signed differences plot saved to {filename}")

def plot_absolute_differences_cdf(data_dict, filename):
    """Generate CDF plot for absolute differences with Vivaldi-style formatting"""
    plt.figure(figsize=(12, 7))
    colors = {'2D': 'blue', '5D': 'orange'}
    
    for dim in ['2D', '5D']:
        if dim not in data_dict or len(data_dict[dim]) == 0:
            print(f"[Warning] No data for {dim}, skipping plot for this dataset.")
            continue

        # Take absolute values of the differences
        abs_values = np.abs(data_dict[dim])
        values = np.sort(abs_values)
        y = np.arange(1, len(values) + 1) / len(values)
        plt.plot(values, y,
                color=colors[dim],
                linestyle='-',
                linewidth=2,
                label=dim)
    
    plt.xlabel('Absolute Difference |Serf RTT - Actual RTT| (ms)', fontsize=12)
    plt.ylabel('Cumulative Probability', fontsize=12)
    plt.title('CDF of Absolute RTT Differences', fontsize=14)
    
    plt.xlim(0, None)  # Let matplotlib auto-scale the x-axis
    plt.legend(loc='lower right')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Absolute differences plot saved to {filename}")

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

# Process signed differences
signed_files = [
    ('signed_error_logs/serf_ping_rtt_signed_diff_5D.log', '5D'),
    ('signed_error_logs/serf_ping_rtt_signed_diff_8D.log', '8D')
]
signed_data = process_files(signed_files, data_type='signed')

# Process absolute differences
absolute_files = [
    ('absolute_error_logs/serf_ping_rtt_absolute_diff_5D.log', '5D'),
    ('absolute_error_logs/serf_ping_rtt_absolute_diff_8D.log', '8D')
]
absolute_data = process_files(absolute_files, data_type='absolute')

# Process relative differences
relative_files = [
    ('relative_error_logs/serf_ping_rtt_relative_diff_5D.log', '5D'),
    ('relative_error_logs/serf_ping_rtt_relative_diff_8D.log', '8D')
]
relative_data = process_files(relative_files, data_type='relative')

# ========================
# Updated Statistics and Plotting Calls
# ========================

# Signed differences statistics and plotting (unchanged except data source)
print("\n[Signed Difference Statistics (in ms)]")
for dim in ['5D', '8D']:
    if dim in signed_data and len(signed_data[dim]) > 0:
        signed_diffs = signed_data[dim]
        median = np.percentile(signed_diffs, 50)
        p80 = np.percentile(signed_diffs, 80)
        p90 = np.percentile(signed_diffs, 90)
        print(f"{dim}: Median = {median:.3f} ms, 80th = {p80:.3f} ms, 90th = {p90:.3f} ms")
    else:
        print(f"{dim}: No data available.")

plot_signed_differences_cdf(signed_data, 'signed_differences_comparison.png')

# Absolute differences statistics and plotting (updated data source)
print("\n[Absolute Difference Statistics (in ms)]")
for dim in ['5D', '8D']:
    if dim in absolute_data and len(absolute_data[dim]) > 0:
        abs_diffs = absolute_data[dim]
        median = np.percentile(abs_diffs, 50)
        p80 = np.percentile(abs_diffs, 80)
        p90 = np.percentile(abs_diffs, 90)
        print(f"{dim}: Median = {median:.3f} ms, 80th = {p80:.3f} ms, 90th = {p90:.3f} ms")
    else:
        print(f"{dim}: No data available.")

plot_absolute_differences_cdf(absolute_data, 'absolute_differences_comparison.png')

# Relative error statistics and plotting (unchanged except data source)
print("\n[Relative Error Statistics (as percentage)]")
for dim in ['5D', '8D']:
    if dim in relative_data and len(relative_data[dim]) > 0:
        rel_errors = relative_data[dim]
        median_raw = np.percentile(rel_errors, 50)
        p80_raw = np.percentile(rel_errors, 80)
        p90_raw = np.percentile(rel_errors, 90)
        median_pct = median_raw * 100
        p80_pct = p80_raw * 100
        p90_pct = p90_raw * 100
        print(f"{dim}: Median = {median_pct:.2f}% ({median_raw:.3f}), "
              f"80th = {p80_pct:.2f}% ({p80_raw:.3f}), "
              f"90th = {p90_pct:.2f}% ({p90_raw:.3f})")
    else:
        print(f"{dim}: No data available.")

plot_relative_cdf(relative_data, 'relative_errors_comparison.png')