import pandas as pd
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np

# === Load and Tag CSVs ===
files = {
    "Vec-only": "serf_rtt_predic_rtt_vec.csv",
    "Vec+Height": "serf_rtt_predic_rtt_vec_height.csv",
    "Vec+Height+Adj": "serf_rtt_predic_rtt_vec_height_adj.csv"
}

dfs = []
for mode, path in files.items():
    df = pd.read_csv(path)
    df["Mode"] = mode
    dfs.append(df)

# === Combine all into one dataframe ===
combined_df = pd.concat(dfs, ignore_index=True)
combined_df.rename(columns={
    "RTT_actual_A_to_B": "RTT_actual",
    "RTT_predicted": "RTT_predicted"
}, inplace=True)

# === Metrics for each mode ===
metrics = []

for mode in combined_df["Mode"].unique():
    df = combined_df[combined_df["Mode"] == mode]

    pearson_corr, _ = pearsonr(df["RTT_actual"], df["RTT_predicted"])
    spearman_corr, _ = spearmanr(df["RTT_actual"], df["RTT_predicted"])
    mae = mean_absolute_error(df["RTT_actual"], df["RTT_predicted"])
    rmse = np.sqrt(mean_squared_error(df["RTT_actual"], df["RTT_predicted"]))

    print(f"\n=== {mode} ===")
    print(f"Pearson correlation: {pearson_corr:.4f}")
    print(f"Spearman correlation: {spearman_corr:.4f}")
    print(f"MAE: {mae:.3f} ms")
    print(f"RMSE: {rmse:.3f} ms")

    metrics.append({
        "Mode": mode,
        "Pearson": pearson_corr,
        "Spearman": spearman_corr,
        "MAE": mae,
        "RMSE": rmse
    })

output_dir = "rttcheck-1"
os.makedirs(output_dir, exist_ok=True)

# === Scatter Plot: Actual vs Predicted ===
plt.figure(figsize=(9, 7))
for mode in combined_df["Mode"].unique():
    df = combined_df[combined_df["Mode"] == mode]
    plt.scatter(df["RTT_actual"], df["RTT_predicted"], alpha=0.4, label=mode)

min_rtt = combined_df["RTT_actual"].min()
max_rtt = combined_df["RTT_actual"].max()
plt.plot([min_rtt, max_rtt], [min_rtt, max_rtt], 'k--', label="Ideal (y = x)")

plt.xlabel("Measured RTT (ms)")
plt.ylabel("Predicted RTT (ms)")
plt.title("Measured vs Predicted RTT (All Modes)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(output_dir, "scatter_all_modes.png"))
plt.close()

# === Bar Plot: MAE and RMSE ===
metric_df = pd.DataFrame(metrics)

# MAE bar
plt.figure(figsize=(8, 5))
plt.bar(metric_df["Mode"], metric_df["MAE"], color="skyblue")
plt.ylabel("MAE (ms)")
plt.title("Mean Absolute Error by Mode")
plt.grid(axis="y")
plt.tight_layout()
plt.savefig(os.path.join(output_dir, "mae_by_mode.png"))
plt.close()

# RMSE bar
plt.figure(figsize=(8, 5))
plt.bar(metric_df["Mode"], metric_df["RMSE"], color="salmon")
plt.ylabel("RMSE (ms)")
plt.title("Root Mean Squared Error by Mode")
plt.grid(axis="y")
plt.tight_layout()
plt.savefig(os.path.join(output_dir, "rmse_by_mode.png"))
plt.close()

# === Optional: Error histogram overlay ===
plt.figure(figsize=(10, 5))
for mode in combined_df["Mode"].unique():
    df = combined_df[combined_df["Mode"] == mode]
    errors = df["RTT_actual"] - df["RTT_predicted"]
    plt.hist(errors, bins=50, alpha=0.4, label=mode)

plt.xlabel("Prediction Error (ms)")
plt.ylabel("Count")
plt.title("Error Distribution Across Modes")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(output_dir, "error_histogram_overlay.png"))
plt.close()
