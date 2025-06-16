import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# Read log file
data = []
with open("centroid_drift.log", "r") as f:
    for line in f:
        if "DRIFT_DATA" in line:
            parts = line.strip().split(",")
            time_str = parts[1].split("=")[1]
            drift_str = parts[2].split("=")[1]
            time = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
            drift = float(drift_str)
            data.append({"Time": time, "Drift (ms)": drift})

# Create DataFrame
df = pd.DataFrame(data)

# Plot
plt.figure(figsize=(10, 5))
plt.plot(df["Time"], df["Drift (ms)"], marker="o", linestyle="-", color="skyblue")
plt.xlabel("Time")
plt.ylabel("Centroid Drift (ms)")
plt.title("Centroid Drift Over Time")
plt.grid(True)
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()