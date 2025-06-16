import re
import datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use a non-GUI backend
import matplotlib.pyplot as plt

# File containing Serf Vivaldi coordinate logs
log_file = "coordinates.log"

# Regular expression to extract data
log_pattern = re.compile(
    r"Time: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) - Node: (\S+) \| Vec: \[([-0-9.e]+) ([-0-9.e]+)\]"
)

# Dictionary to store extracted data {timestamp: [list of magnitudes]}
data = {}

# Read log file and extract coordinates
with open(log_file, "r") as file:
    for line in file:
        match = log_pattern.search(line)
        if match:
            timestamp, node, x, y = match.groups()
            timestamp = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
            magnitude = np.sqrt(float(x)**2 + float(y)**2)

            if timestamp not in data:
                data[timestamp] = []
            data[timestamp].append(magnitude)

# Convert dictionary to sorted lists
timestamps = sorted(data.keys())
magnitudes = [data[t] for t in timestamps]

# Aggregate every 10 minutes to reduce clutter
aggregation_window = datetime.timedelta(minutes=10)
agg_timestamps = []
agg_means = []
agg_mins = []
agg_maxs = []

start_time = timestamps[0]
window_magnitudes = []

for t, mag_list in zip(timestamps, magnitudes):
    if t - start_time >= aggregation_window:
        if window_magnitudes:
            agg_timestamps.append(start_time)
            agg_means.append(np.mean(window_magnitudes))
            agg_mins.append(np.min(window_magnitudes))
            agg_maxs.append(np.max(window_magnitudes))
        start_time = t
        window_magnitudes = []
    
    window_magnitudes.extend(mag_list)

# Final aggregation
if window_magnitudes:
    agg_timestamps.append(start_time)
    agg_means.append(np.mean(window_magnitudes))
    agg_mins.append(np.min(window_magnitudes))
    agg_maxs.append(np.max(window_magnitudes))

# Plot the results
plt.figure(figsize=(12, 6))
plt.plot(agg_timestamps, agg_means, label="Mean Magnitude", color="blue", linewidth=2)
plt.fill_between(agg_timestamps, agg_mins, agg_maxs, color="blue", alpha=0.2, label="Min-Max Range")

# Formatting
plt.xlabel("Time")
plt.ylabel("Magnitude (Distance from Origin)")
plt.title("Vivaldi Coordinate Drift Over Time")
plt.xticks(rotation=45)
plt.legend()
plt.grid(True)
plt.tight_layout()

# Show the plot
#plt.show()
plt.savefig("vivaldi_drift_plot.png")
