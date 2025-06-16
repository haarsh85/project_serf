import pandas as pd
import re
import seaborn as sns
import matplotlib.pyplot as plt
from tabulate import tabulate

# --- Configuration ---
log_path = "serf_ping_rtt_signed_diff_2D_26052025.log"
low_deviation_threshold = 3
ping_bins = [0, 10, 30, 60, 90]
output_file = "analysis_output.txt"

# --- Step 1: Parse log file ---
pattern = re.compile(
    r"\[(?P<network_src>net_\d+)\] .*? \((?P<ip_src>\d+\.\d+\.\d+\.\d+)\) → "
    r"\[(?P<network_dst>net_\d+)\] .*? \((?P<ip_dst>\d+\.\d+\.\d+\.\d+)\): "
    r"(?P<diff>[+-]?\d+\.\d+)\s*ms \[serf_rtt:\s*(?P<serf_rtt>\d+\.\d+)\s*ms, ping_rtt:\s*(?P<ping_rtt>\d+\.\d+)\s*ms\]"
)

records = []
with open(log_path, "r") as file:
    for line in file:
        match = pattern.search(line)
        if match:
            records.append({
                "network_src": match.group("network_src"),
                "network_dst": match.group("network_dst"),
                "ip_src": match.group("ip_src"),
                "ip_dst": match.group("ip_dst"),
                "diff": float(match.group("diff")),
                "serf_rtt": float(match.group("serf_rtt")),
                "ping_rtt": float(match.group("ping_rtt")),
            })

df = pd.DataFrame(records)
df["network_type"] = df.apply(lambda row: "intra" if row["network_src"] == row["network_dst"] else "inter", axis=1)

# --- Output Block ---
with open(output_file, "w") as output:

    # --- Step 2: Basic Stats ---
    print("\n--- Basic Statistics ---", file=output)
    stats = df[["diff", "serf_rtt", "ping_rtt"]].describe(percentiles=[0.5, 0.8]).round(3)

    display_stats = stats.copy().astype(str)
    for row_label in ["mean", "max", "50%", "80%"]:
        if row_label in stats.index:
            display_stats.loc[row_label] = stats.loc[row_label].apply(lambda x: f"{x:+.3f}")

    wanted_rows = ["count", "mean", "std", "min", "25%", "50%", "80%", "75%", "max"]
    available_rows = [r for r in wanted_rows if r in display_stats.index]
    print(display_stats.loc[available_rows], file=output)

    # --- Step 3: Network Type Counts ---
    print("\n--- Network Type Counts ---", file=output)
    nt_counts = df["network_type"].value_counts().sort_index()
    nt_total = nt_counts.sum()
    nt_table = [[nt, f"{cnt:,}", f"{(cnt / nt_total * 100):.1f}%"] for nt, cnt in nt_counts.items()]
    print(tabulate(nt_table, headers=["Network Type", "Count", "%"], tablefmt="github"), file=output)

    # --- Step 4: Deviation Classification ---
    df["deviation_type"] = df["diff"].apply(
        lambda x: "low" if abs(x) <= low_deviation_threshold else ("high+" if x > low_deviation_threshold else "high-")
    )
    deviation_table = df.groupby(["network_type", "deviation_type"]).size().unstack(fill_value=0)

    formatted_dev_table = []
    for nt in ["inter", "intra"]:
        row = deviation_table.loc[nt]
        formatted_dev_table.append([
            f"{nt.capitalize()}",
            f"{row.get('high+', 0):,}",
            f"{row.get('high-', 0):,}",
            f"{row.get('low', 0):,}"
        ])
    print("\n--- Deviation Type Breakdown ---", file=output)
    print(tabulate(formatted_dev_table,
                   headers=["Network Type", "High Positive (≫)", "High Negative (≪)", "Low Deviation (±3ms)"],
                   tablefmt="github"), file=output)

    # --- Step 5: Impact of Ping RTT on Accuracy ---
    df["ping_rtt_range"] = pd.cut(df["ping_rtt"], bins=ping_bins, right=False)
    ping_rtt_groups = df.groupby(["ping_rtt_range", "network_type"], observed=False)["diff"].agg(["mean", "count"]).unstack()

    print("\n--- Impact of Ping RTT on Accuracy ---", file=output)
    impact_rows = []
    for rtt_range in ping_rtt_groups.index:
        inter_mean = ping_rtt_groups.loc[rtt_range, ("mean", "inter")] if ("mean", "inter") in ping_rtt_groups.columns else None
        intra_mean = ping_rtt_groups.loc[rtt_range, ("mean", "intra")] if ("mean", "intra") in ping_rtt_groups.columns else None
        inter_count = ping_rtt_groups.loc[rtt_range, ("count", "inter")] if ("count", "inter") in ping_rtt_groups.columns else 0
        intra_count = ping_rtt_groups.loc[rtt_range, ("count", "intra")] if ("count", "intra") in ping_rtt_groups.columns else 0

        def fmt_mean(val):
            if pd.isna(val):
                return "—"
            return f"{val:+.2f} ms" if abs(val) >= 0.01 else "~0.00 ms"

        impact_rows.append([
            f"{str(rtt_range).replace('[', '').replace(')', '').replace(',', '–')} ms",
            fmt_mean(inter_mean),
            fmt_mean(intra_mean),
            f"{int(inter_count):,}" if not pd.isna(inter_count) else "0",
            f"{int(intra_count):,}" if not pd.isna(intra_count) else "0"
        ])

    print(tabulate(impact_rows,
                   headers=["Ping RTT Range", "Avg Diff (Inter)", "Avg Diff (Intra)", "Count (Inter)", "Count (Intra)"],
                   tablefmt="github"), file=output)

# --- Step 6: Distribution Plot ---
plt.figure(figsize=(12, 6))
palette = {"inter": "blue", "intra": "orange"}
sns.histplot(data=df, x="diff", bins=100, hue="network_type", multiple="dodge", palette=palette, kde=False)
plt.axvline(low_deviation_threshold, color='green', linestyle='--', label='+3ms Threshold')
plt.axvline(-low_deviation_threshold, color='green', linestyle='--', label='-3ms Threshold')
plt.title("Distribution of Serf RTT - Ping RTT Differences")
plt.xlabel("RTT Difference (ms)")
plt.ylabel("Count")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("rtt_difference_distribution.png")
plt.show()

print(f"✅ All analysis results saved to: {output_file}")
print("✅ Distribution plot saved as: rtt_difference_distribution.png")

print(df.groupby("network_type")["diff"].agg(["min", "max"]))
intra_outliers = df[(df["network_type"] == "intra") & ((df["diff"] < -10) | (df["diff"] > 30))]
print(intra_outliers)
intra_outliers = df[(df["network_type"] == "inter") & ((df["diff"] < -10) | (df["diff"] > 30))]
print(intra_outliers)