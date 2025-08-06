import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import os

# === Load Data ===
df = pd.read_csv("range4-result.csv")

# === Ensure numeric types ===
numeric_cols = ['t', 'gt', 'found', 'tp', 'fp', 'fn', 'precision', 'recall', 'jaccard', 'hilbert_order']
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce')

assert 'hilbert_order' in df.columns, "Missing 'hilbert_order' column in input CSV"
os.makedirs("plots/range4/", exist_ok=True)

# === Summary Table: Avg metrics per hilbert_order and threshold (t) ===
summary = df.groupby(['hilbert_order', 't']).agg({
    'gt': 'mean',
    'found': 'mean',
    'tp': 'mean',
    'fp': 'mean',
    'fn': 'mean',
    'precision': 'mean',
    'recall': 'mean',
    'jaccard': 'mean'
}).round(4).reset_index()
summary.to_csv("range4-summary.csv", index=False)

# === Aggregate Across All RTT Thresholds (per Hilbert Order) ===
agg = df.groupby('hilbert_order').agg({
    'gt': 'mean',
    'found': 'mean',
    'tp': 'mean',
    'fp': 'mean',
    'fn': 'mean',
    'precision': 'mean',
    'recall': 'mean',
    'jaccard': 'mean'
}).reset_index()

# === Plot 1: Jaccard vs Hilbert Order ===
# plt.figure(figsize=(8, 5))
# sns.lineplot(data=agg, x="hilbert_order", y="jaccard", marker="o", color='purple')
# plt.title("Average Jaccard vs Hilbert Order")
# plt.xlabel("Hilbert Order (p)")
# plt.ylabel("Jaccard Index (avg across RTT thresholds)")
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("plots/range4/jaccard_vs_hilbert_order.png")
# plt.close()

# === Plot 2: Precision vs Hilbert Order ===
# plt.figure(figsize=(8, 5))
# sns.lineplot(data=agg, x="hilbert_order", y="precision", marker="o", color='blue')
# plt.title("Average Precision vs Hilbert Order")
# plt.xlabel("Hilbert Order (p)")
# plt.ylabel("Precision (avg across RTT thresholds)")
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("plots/range4/precision_vs_hilbert_order.png")
# plt.close()

# === Plot 3: Recall vs Hilbert Order ===
# plt.figure(figsize=(8, 5))
# sns.lineplot(data=agg, x="hilbert_order", y="recall", marker="o", color='green')
# plt.title("Average Recall vs Hilbert Order")
# plt.xlabel("Hilbert Order (p)")
# plt.ylabel("Recall (avg across RTT thresholds)")
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("plots/range4/recall_vs_hilbert_order.png")
# plt.close()

# === Plot 4: False Positives & False Negatives vs Hilbert Order ===
# plt.figure(figsize=(9, 6))
# sns.lineplot(data=agg, x="hilbert_order", y="fp", label="False Positives", marker="o", color='red')
# sns.lineplot(data=agg, x="hilbert_order", y="fn", label="False Negatives", marker="s", color='orange')
# plt.title("False Positives & False Negatives vs Hilbert Order")
# plt.xlabel("Hilbert Order (p)")
# plt.ylabel("Count (avg across thresholds)")
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("plots/range4/fp_fn_vs_hilbert_order.png")
# plt.close()

# === Plot 5: Found vs GT (colored by Hilbert Order) ===
# plt.figure(figsize=(8, 6))
# sns.scatterplot(data=df, x="gt", y="found", hue="hilbert_order", palette="Spectral", alpha=0.7)
# plt.plot([0, df['gt'].max()], [0, df['gt'].max()], 'k--', label='Ideal (Found = GT)')
# plt.title("Found vs Ground Truth (all data)")
# plt.xlabel("Ground Truth Count (GT)")
# plt.ylabel("Found Count")
# plt.legend(title="Hilbert Order", bbox_to_anchor=(1.05, 1), loc='upper left')
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("plots/range4/found_vs_gt_colored_by_order.png")
# plt.close()

# === Plot 6: Combined TP, FP, FN vs Hilbert Order ===
# === Melt summary to long-form for TP/FP/FN/GT ===
melted = summary.melt(
    id_vars=['hilbert_order', 't'],
    value_vars=['gt', 'tp', 'fp', 'fn'],
    var_name='metric',
    value_name='count'
)

# Create hue_label: 'gt' stays 'gt', others use hilbert_order
melted['hue_label'] = melted.apply(
    lambda row: 'gt' if row['metric'] == 'gt' else str(row['hilbert_order']),
    axis=1
)

# Color palette: 'gt' is black, rest are by hilbert_order
palette = {
    'gt': 'black',
    '2': "#1f77b4",
    '4': "#ff7f0e",
    '6': "#2ca02c",
    '8': "#d62728",
    '10': "#9467bd"
}

# Metric-based marker and style
style_order = ['gt', 'tp', 'fp', 'fn']
markers = {
    'gt': 'o',
    'tp': 's',
    'fp': '^',
    'fn': 'X'
}

# Plot
plt.figure(figsize=(10, 6))
sns.lineplot(
    data=melted,
    x='t',
    y='count',
    hue='hue_label',
    style='metric',
    markers=markers,
    style_order=style_order,
    dashes=True,
    palette=palette
)

plt.title("GT, TP, FP, FN vs RTT Threshold per Hilbert Order")
plt.xlabel("RTT Threshold (ms)")
plt.ylabel("Count")
plt.legend(title="Hilbert Order / Metric", bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True)
plt.tight_layout()
plt.savefig("plots/range4/gt_tp_fp_fn_vs_threshold.png")
plt.close()


print("✅ All plots generated successfully in 'plots/' folder.")
