import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import os

# === File mapping ===
input_files = {
    # "Code 1": "range1-result.csv",
    # "Code 2": "range2-result.csv",
    # "Code 4": "range4-result.csv",
    # "Code 5": "range5-result.csv",
    "code 6": "range6-result.csv",
    "Code 7": "range7-result.csv",
}
metrics_sum = ['gt', 'found', 'tp', 'fp', 'fn']
metrics_mean = ['precision', 'recall', 'jaccard']
output_dir = "plots_range_compare"
os.makedirs(output_dir, exist_ok=True)

# === Load and prepare all CSVs ===
all_dfs = []
for code_name, path in input_files.items():
    df = pd.read_csv(path)
    df['code'] = code_name

    # Group by order + threshold, aggregate
    grouped = df.groupby(['hilbert_order', 't']).agg({
        **{m: 'sum' for m in metrics_sum},
        **{m: 'mean' for m in metrics_mean},
    }).reset_index()
    grouped['code'] = code_name
    all_dfs.append(grouped)

df_all = pd.concat(all_dfs, ignore_index=True)

# === Plot each metric ===
plot_metrics = metrics_sum + metrics_mean
sns.set(style="whitegrid")

for metric in plot_metrics:
    plt.figure(figsize=(12, 6))
    sns.lineplot(
        data=df_all,
        x='t',
        y=metric,
        hue='code',
        style='hilbert_order',
        markers=True,
        dashes=False
    )
    plt.title(f"{metric.upper()} vs RTT Threshold")
    plt.xlabel("RTT Threshold (ms)")
    plt.ylabel(metric.upper())
    plt.legend(title="Code / Order", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{metric}_vs_threshold.png"))
    plt.close()
