import re
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np

def parse_log_file(filename):
    data = defaultdict(list)
    current_section = None
    current_source_net = None
    current_dest_net = None
    
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('==='):
                if 'Intra-network' in line:
                    current_section = 'intra'
                    parts = line.split(' ')
                    current_source_net = parts[4]
                    current_dest_net = current_source_net
                elif 'Inter-network' in line:
                    current_section = 'inter'
                    parts = line.split('→')
                    current_source_net = parts[0].split(' ')[-1].strip()
                    current_dest_net = parts[1].split(' ')[0].strip()
                else:
                    current_section = None
                    current_source_net = None
                    current_dest_net = None
            elif line.startswith('---'):
                continue
            else:
                if current_section is None:
                    continue
                match = re.match(r'.*?\[.*?\] (.*?) \(.*?\) → \[.*?\] (.*?) \(.*?\): (\d+\.\d+)ms', line)
                if match:
                    source_node = match.group(1)
                    dest_node = match.group(2)
                    rtt = float(match.group(3))
                    key = (source_node, dest_node, current_source_net, current_dest_net)
                    data[key].append(rtt)
    return data

# Parse the log files
ping_data = parse_log_file('ping_rtt_values.log')
serf_data = parse_log_file('serf_rtt_values_2D.log')

# Prepare data for comparison
comparison_data = []
differences = []
intra_diffs = []
inter_diffs = []

for key in serf_data:
    s_node, d_node, s_net, d_net = key
    if key in ping_data:
        ping_rtts = ping_data[key]
        avg_ping = sum(ping_rtts) / len(ping_rtts)
        for serf_rtt in serf_data[key]:
            diff = serf_rtt - avg_ping
            differences.append(diff)
            comparison_data.append((avg_ping, serf_rtt))
            if s_net == d_net:
                intra_diffs.append(diff)
            else:
                inter_diffs.append(diff)
    else:
        print(f"No ping data for {key}")

# Calculate statistics
if differences:
    mae = np.mean(np.abs(differences))
    rmse = np.sqrt(np.mean(np.square(differences)))
    mean_diff = np.mean(differences)
    median_diff = np.median(differences)
    std_diff = np.std(differences)
    ping_avg = [x[0] for x in comparison_data]
    serf_rtts = [x[1] for x in comparison_data]
    corr_coef = np.corrcoef(ping_avg, serf_rtts)[0, 1]
else:
    print("No overlapping data to compare.")
    exit()

# Print statistics
print(f"Mean Absolute Error (MAE): {mae:.3f} ms")
print(f"Root Mean Squared Error (RMSE): {rmse:.3f} ms")
print(f"Mean Difference: {mean_diff:.3f} ms")
print(f"Median Difference: {median_diff:.3f} ms")
print(f"Standard Deviation: {std_diff:.3f} ms")
print(f"Correlation Coefficient: {corr_coef:.3f}")

# Plotting
plt.figure(figsize=(10, 5))
plt.scatter(ping_avg, serf_rtts, alpha=0.5)
max_val = max(max(ping_avg), max(serf_rtts))
plt.plot([0, max_val], [0, max_val], 'r--')
plt.xlabel('Average Ping RTT (ms)')
plt.ylabel('Serf RTT (ms)')
plt.title('Serf vs Ping RTT Comparison')
plt.grid(True)
plt.show()

plt.figure(figsize=(10, 5))
plt.hist(differences, bins=20, edgecolor='black')
plt.xlabel('Difference (Serf RTT - Average Ping RTT) (ms)')
plt.ylabel('Frequency')
plt.title('Distribution of RTT Differences')
plt.show()

# Box plot for Intra vs Inter differences
plot_data = []
labels = []
if intra_diffs:
    plot_data.append(intra_diffs)
    labels.append('Intra-network')
if inter_diffs:
    plot_data.append(inter_diffs)
    labels.append('Inter-network')

if plot_data:
    plt.figure(figsize=(10, 5))
    plt.boxplot(plot_data, labels=labels)
    plt.ylabel('Difference (ms)')
    plt.title('Differences by Network Type')
    plt.show()