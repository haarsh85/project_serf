import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re

# Load the log file
with open("serf_ping_rtt_absolute_diff_28062025_2.log", "r") as file:
    lines = file.readlines()

# Extract RTT differences using regex
pattern = re.compile(r': ([\d.]+) \[serf_rtt: ([\d.]+) ms, ping_rtt: ([\d.]+) ms\]')
rtt_diffs = [float(match.group(1)) for line in lines if (match := pattern.search(line))]

# Create DataFrame
df = pd.DataFrame(rtt_diffs, columns=["RTT_Diff"])

# Dynamic binning (0–1, 1–2, ..., up to ceiling of max RTT)
max_rtt = int(df["RTT_Diff"].max()) + 1
bins = list(range(0, max_rtt + 1))
labels = [f"{i}–{i+1} ms" for i in range(len(bins)-1)]

# Bin the RTT differences
df["RTT_Range"] = pd.cut(df["RTT_Diff"], bins=bins, labels=labels, include_lowest=True, right=False)

# Summarize data
summary = df["RTT_Range"].value_counts().sort_index()
summary_percent = (summary / len(df)) * 100

summary_table = pd.DataFrame({
    "RTT Range": summary.index,
    "Node Pairs": summary.values,
    "Percentage": summary_percent.values
}).round(2)

# Print the summary table
print(summary_table)

# Plot the distribution
plt.figure(figsize=(12, 6))
sns.barplot(data=summary_table, x="RTT Range", y="Percentage", palette="Blues_d")
plt.title("Serf RTT Difference Distribution")
plt.xlabel("RTT Difference Range")
plt.ylabel("Percentage of Total Node Pairs (%)")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("serf_rtt_diff_distribution.png", dpi=300)  # Save the plot
plt.show()
