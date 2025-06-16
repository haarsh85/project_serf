import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re
import pytz
from matplotlib.dates import DateFormatter

# --------------------------------
# 1. Parse the Log File
# --------------------------------
def parse_log(file_path):
    data = []
    with open(file_path, 'r') as f:
        for line in f:
            # Extract timestamp (UTC)
            timestamp_str = re.search(r'Time: (.*?)Z', line).group(1) + 'Z'
            
            # Extract node name
            node = re.search(r'Node: (.*?) \|', line).group(1)
            
            # Extract coordinates
            vec_match = re.search(r'Vec: \[(.*?)\]', line)
            x, y = map(float, vec_match.group(1).split())
            
            data.append({
                'timestamp': timestamp_str,
                'node': node,
                'x_coord': x,
                'y_coord': y
            })
    return pd.DataFrame(data)

# --------------------------------
# 2. Process Data
# --------------------------------
# Load and parse data
df = parse_log('coordinates.log')

# Convert to datetime with UTC timezone
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

# Calculate distance from origin
df['distance'] = (df['x_coord']**2 + df['y_coord']**2)**0.5

# --------------------------------
# 3. Prepare Time Series Data
# --------------------------------
# Set timestamp as index and sort
df.set_index('timestamp', inplace=True)
df.sort_index(inplace=True)

# Resample to 5-minute intervals using mean
resampled = df.resample('5T')['distance'].mean().reset_index()

# Convert to CET for display
cet = pytz.timezone('Europe/Paris')
resampled['timestamp_cet'] = resampled['timestamp'].dt.tz_convert(cet)

# --------------------------------
# 4. Create Visualization (Critical Update)
# --------------------------------
plt.figure(figsize=(14, 7))

# Plot raw data (5-second intervals)
plt.scatter(
    df.index.tz_convert(cet),
    df['distance'],
    color='#3498db',
    alpha=0.1,
    label='Raw Data (5-second)'
)

# Plot 5-minute averages
plt.plot(
    resampled['timestamp_cet'],
    resampled['distance'],
    color='#e74c3c',
    linewidth=1.5,
    label='5-Minute Average'
)

# Add stability baseline
plt.axhline(
    y=resampled['distance'].mean(),
    color='#27ae60',
    linestyle='--',
    label=f'Stability Baseline: {resampled["distance"].mean():.4f}'
)

# Formatting
plt.ylim(0, 1.2 * resampled['distance'].max())  # Adjust based on your data
plt.title('Vivaldi Coordinates: Stability Analysis (Raw + Smoothed)', fontsize=14)
plt.legend()
plt.show()