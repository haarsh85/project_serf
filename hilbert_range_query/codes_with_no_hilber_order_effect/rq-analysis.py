import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import os

# === Load Data ===
df = pd.read_csv("lawder162-5.csv")

# === Ensure numeric types ===
numeric_cols = ['threshold', 'gt', 'found', 'fp', 'fn', 'precision', 'recall', 'jaccard', 'hilbert_order']
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce')

assert 'hilbert_order' in df.columns, "Missing 'hilbert_order' column in input CSV"
os.makedirs("plots", exist_ok=True)

# === Summary Table: Avg metrics per hilbert_order and threshold ===
summary = df.groupby(['hilbert_order', 'threshold']).agg({
    'gt': 'mean',
    'found': 'mean',
    'fp': 'mean',
    'fn': 'mean',
    'precision': 'mean',
    'recall': 'mean',
    'jaccard': 'mean'
}).round(4).reset_index()
summary.to_csv("summary_by_hilbert_order_zz1.csv", index=False)

# === Aggregate Across All RTT Thresholds (per Hilbert Order) ===
agg = df.groupby('hilbert_order').agg({
    'gt': 'mean',
    'found': 'mean',
    'fp': 'mean',
    'fn': 'mean',
    'precision': 'mean',
    'recall': 'mean',
    'jaccard': 'mean'
}).reset_index()

# === Plot 1: Jaccard vs Hilbert Order ===
plt.figure(figsize=(8, 5))
sns.lineplot(data=agg, x="hilbert_order", y="jaccard", marker="o", color='purple')
plt.title("Average Jaccard vs Hilbert Order")
plt.xlabel("Hilbert Order (p)")
plt.ylabel("Jaccard Index (avg across RTT thresholds)")
plt.grid(True)
plt.tight_layout()
plt.savefig("plots/jaccard_vs_hilbert_order.png")
plt.close()

# === Plot 2: Precision vs Hilbert Order ===
plt.figure(figsize=(8, 5))
sns.lineplot(data=agg, x="hilbert_order", y="precision", marker="o", color='blue')
plt.title("Average Precision vs Hilbert Order")
plt.xlabel("Hilbert Order (p)")
plt.ylabel("Precision (avg across RTT thresholds)")
plt.grid(True)
plt.tight_layout()
plt.savefig("plots/precision_vs_hilbert_order.png")
plt.close()

# === Plot 3: Recall vs Hilbert Order ===
plt.figure(figsize=(8, 5))
sns.lineplot(data=agg, x="hilbert_order", y="recall", marker="o", color='green')
plt.title("Average Recall vs Hilbert Order")
plt.xlabel("Hilbert Order (p)")
plt.ylabel("Recall (avg across RTT thresholds)")
plt.grid(True)
plt.tight_layout()
plt.savefig("plots/recall_vs_hilbert_order.png")
plt.close()

# === Plot 4: False Positives & False Negatives vs Hilbert Order ===
plt.figure(figsize=(9, 6))
sns.lineplot(data=agg, x="hilbert_order", y="fp", label="False Positives", marker="o", color='red')
sns.lineplot(data=agg, x="hilbert_order", y="fn", label="False Negatives", marker="s", color='orange')
plt.title("False Positives & False Negatives vs Hilbert Order")
plt.xlabel("Hilbert Order (p)")
plt.ylabel("Count (avg across thresholds)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("plots/fp_fn_vs_hilbert_order.png")
plt.close()

# === Plot 5: Found vs GT (colored by Hilbert Order) ===
plt.figure(figsize=(8, 6))
sns.scatterplot(data=df, x="gt", y="found", hue="hilbert_order", palette="Spectral", alpha=0.7)
plt.plot([0, df['gt'].max()], [0, df['gt'].max()], 'k--', label='Ideal (Found = GT)')
plt.title("Found vs Ground Truth (all data)")
plt.xlabel("Ground Truth Count (GT)")
plt.ylabel("Found Count")
plt.legend(title="Hilbert Order", bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True)
plt.tight_layout()
plt.savefig("plots/found_vs_gt_colored_by_order.png")
plt.close()

print("✅ All plots generated successfully in 'plots/' folder.")
