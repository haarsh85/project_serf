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
df = parse_log('coordinates.log')

# Convert to datetime with UTC timezone
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

# --------------------------------
# 3. Compute Migration of Centroid
# --------------------------------
# Group by timestamp and compute centroid at each time
centroids = df.groupby('timestamp')[['x_coord', 'y_coord']].mean().reset_index()

# Compute the distance the centroid has moved from the previous timestamp
centroids['centroid_migration'] = np.sqrt(
    (centroids['x_coord'].diff())**2 + (centroids['y_coord'].diff())**2
)

# Convert to CET for display
cet = pytz.timezone('Europe/Paris')
centroids['timestamp_cet'] = centroids['timestamp'].dt.tz_convert(cet)

# --------------------------------
# 4. Compute Standard Deviation of Coordinates
# --------------------------------
coord_std = df.groupby('timestamp')[['x_coord', 'y_coord']].std().reset_index()
coord_std['std_distance'] = np.sqrt(coord_std['x_coord']**2 + coord_std['y_coord']**2)
coord_std['timestamp_cet'] = coord_std['timestamp'].dt.tz_convert(cet)

# --------------------------------
# 5. Create Visualization
# --------------------------------
fig, ax1 = plt.subplots(figsize=(14, 7))

# Plot Centroid Migration
ax1.plot(
    centroids['timestamp_cet'],
    centroids['centroid_migration'] * 1000,  # Convert to ms
    color='#e74c3c',
    linewidth=1.5,
    label='Centroid Migration (ms)'
)

# Plot Standard Deviation of Coordinates
ax2 = ax1.twinx()
ax2.plot(
    coord_std['timestamp_cet'],
    coord_std['std_distance'],
    color='#3498db',
    linestyle='dashed',
    label='Standard Deviation of Coordinates'
)

# Formatting
ax1.set_ylabel("Centroid Migration (ms)", color='#e74c3c')
ax2.set_ylabel("Standard Deviation of Coordinates", color='#3498db')
plt.title('Vivaldi Coordinate Drift Over Time', fontsize=14)

fig.legend(loc="upper left", bbox_to_anchor=(0.1,0.9))
plt.show()
