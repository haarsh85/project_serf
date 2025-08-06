import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

# === Load Data ===
plot_dir = "range7-old-scaling"
df = pd.read_csv(f"range/{plot_dir}-result.csv")

# === Ensure numeric types ===
numeric_cols = ['t', 'gt', 'found', 'tp', 'fp', 'fn', 'precision', 'recall', 'jaccard', 'hilbert_order']
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce')

assert 'hilbert_order' in df.columns, "Missing 'hilbert_order' column in input CSV"
os.makedirs(f"plots/{plot_dir}/", exist_ok=True)

# === Summary Table: SUM metrics per hilbert_order and threshold (t) ===
summary = df.groupby(['hilbert_order', 't']).agg({
    'gt': 'sum',
    'found': 'sum',
    'tp': 'sum',
    'fp': 'sum',
    'fn': 'sum'
}).reset_index()

# Recompute metrics
summary['precision'] = summary['tp'] / (summary['tp'] + summary['fp'])
summary['recall'] = summary['tp'] / (summary['tp'] + summary['fn'])
summary['jaccard'] = summary['tp'] / (summary['tp'] + summary['fp'] + summary['fn'])

summary = summary.round(4)
summary.to_csv(f"range/{plot_dir}-summary.csv", index=False)

# === Aggregate Across All RTT Thresholds (per Hilbert Order) ===
agg = summary.groupby('hilbert_order').agg({
    'gt': 'sum',
    'found': 'sum',
    'tp': 'sum',
    'fp': 'sum',
    'fn': 'sum'
}).reset_index()

# Recompute metrics from totals
agg['precision'] = agg['tp'] / (agg['tp'] + agg['fp'])
agg['recall'] = agg['tp'] / (agg['tp'] + agg['fn'])
agg['jaccard'] = agg['tp'] / (agg['tp'] + agg['fp'] + agg['fn'])


# ------------------ PLOTS ------------------

# === Plot 7: Combined Precision & Recall vs Hilbert Order ===
# """
# This plot shows how precision and recall vary across different Hilbert orders.
# - Helps to identify which Hilbert order balances between reducing false positives (precision)
#   and false negatives (recall) best.
# - Ideal Hilbert order has high precision and high recall, indicating accurate and comprehensive detection.
# """
plt.figure(figsize=(8, 5))
sns.lineplot(data=agg, x='hilbert_order', y='precision', marker='o', label='Precision', color='blue')
sns.lineplot(data=agg, x='hilbert_order', y='recall', marker='s', label='Recall', color='green')
plt.title("Precision & Recall vs Hilbert Order")
plt.xlabel("Hilbert Order (p)")
plt.ylabel("Score")
plt.ylim(0, 1)
plt.grid(True)
plt.legend(title="Metric")
plt.tight_layout()
plt.savefig(f"plots/{plot_dir}/precision_recall_vs_hilbert_order.png")
plt.close()

###############
print("\n=== Precision & Recall per Hilbert Order ===")
print(f"{'Order':<10} | {'Precision':<10} | {'Recall':<10}")
print("-" * 36)

for _, row in agg.iterrows():
    print(f"{int(row['hilbert_order']):<10} | {row['precision']:<10.4f} | {row['recall']:<10.4f}")

agg['f_avg'] = (agg['precision'] + agg['recall']) / 2
best_order = agg.loc[agg['f_avg'].idxmax()]
print("\n>>> Summary:")
print(f"- Hilbert Order {int(best_order['hilbert_order'])} achieves the best balance between precision "
      f"({best_order['precision']:.2f}) and recall ({best_order['recall']:.2f}).")


# # === Plot 8: Total TP, FP, FN vs Hilbert Order (aggregated across all thresholds) ===
# """
# This plot presents total counts of True Positives (TP), False Positives (FP), and False Negatives (FN)
# for each Hilbert order, aggregated over all RTT thresholds.
# - Useful to see the raw detection performance and errors by Hilbert order.
# - Aim for higher TP and lower FP and FN values to identify the best Hilbert order.
# """
total = df.groupby('hilbert_order').agg({
    'tp': 'sum',
    'fp': 'sum',
    'fn': 'sum'
}).reset_index()

melted_total = total.melt(id_vars='hilbert_order', value_vars=['tp', 'fp', 'fn'],
                          var_name='metric', value_name='count')

plt.figure(figsize=(8, 5))
sns.lineplot(data=melted_total, x='hilbert_order', y='count', hue='metric', style='metric',
             markers=['o', 's', '^'], dashes=False, palette=['green', 'red', 'orange'])

plt.title("Total TP, FP, FN vs Hilbert Order")
plt.xlabel("Hilbert Order (p)")
plt.ylabel("Total Count (all RTT thresholds)")
plt.grid(True)
plt.legend(title="Metric")
plt.tight_layout()
plt.savefig(f"plots/{plot_dir}/tp_fp_fn_total_vs_hilbert_order.png")
plt.close()

# # === Plot 9: TP, FP, FN vs RTT Threshold per Hilbert Order ===
# """
# Shows how TP, FP, FN counts vary with RTT threshold for each Hilbert order.
# - Helps analyze how detection accuracy and error counts change as RTT threshold is varied.
# - A robust Hilbert order maintains a favorable TP/FP/FN trade-off across thresholds.
# """
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
plt.savefig(f"plots/{plot_dir}/gt_tp_fp_fn_vs_threshold.png")
plt.close()


###########################
def categorize_rtt(t):
    if t <= 20:
        return 'Low'
    elif t <= 40:
        return 'Medium'
    else:
        return 'High'

melted = summary.melt(
    id_vars=['hilbert_order', 't'],
    value_vars=['gt', 'tp', 'fp', 'fn'],
    var_name='metric',
    value_name='count'
)

melted['hue_label'] = melted.apply(
    lambda row: 'gt' if row['metric'] == 'gt' else str(row['hilbert_order']),
    axis=1
)

palette = {
    'gt': 'black',
    '2': "#1f77b4",
    '4': "#ff7f0e",
    '6': "#2ca02c",
    '8': "#d62728",
    '10': "#9467bd"
}

style_order = ['gt', 'tp', 'fp', 'fn']
markers = {
    'gt': 'o',
    'tp': 's',
    'fp': '^',
    'fn': 'X'
}

def categorize_rtt(t):
    if t <= 20:
        return 'Low'
    elif t <= 40:
        return 'Medium'
    else:
        return 'High'

melted['rtt_range'] = melted['t'].apply(categorize_rtt)

metrics = ['tp', 'fp', 'fn']
print(f"\n{'RTT Range':<8} | {'Metric':<4} | {'Hilbert Order (Highest)':<22} | {'Count':>7}")
print("-" *  50)  # 50 chars wide separator

for rtt_cat in ['Low', 'Medium', 'High']:
    for metric in metrics:
        df_sub = melted[(melted['rtt_range'] == rtt_cat) & (melted['metric'] == metric)]
        
        # Sum counts per hilbert_order
        agg = df_sub.groupby('hue_label')['count'].sum().reset_index()
        max_row = agg.loc[agg['count'].idxmax()]
        
        print(f"{rtt_cat:<8} | {metric.upper():<6} | {max_row['hue_label']:<22} | {int(max_row['count']):>7}")

print()



# # === Plot 10: Precision & Recall vs RTT Threshold per Hilbert Order ===
# """
# Displays precision and recall trends across RTT thresholds for each Hilbert order.
# - Useful to evaluate consistency of detection quality as threshold changes.
# - Stable or improving precision and recall over thresholds indicate reliable Hilbert order.
# """
melted_pr = df.groupby(['hilbert_order', 't']).agg({
    'precision': 'mean',
    'recall': 'mean'
}).reset_index().melt(id_vars=['hilbert_order', 't'], value_vars=['precision', 'recall'],
                      var_name='metric', value_name='score')

plt.figure(figsize=(10, 6))
sns.lineplot(data=melted_pr, x='t', y='score', hue='hilbert_order', style='metric',
             markers=True, dashes=True,
             palette='tab10',
             markersize=7)

plt.title("Precision & Recall vs RTT Threshold per Hilbert Order")
plt.xlabel("RTT Threshold (ms)")
plt.ylabel("Score")
plt.ylim(0, 1)
plt.legend(title="Hilbert Order / Metric", bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True)
plt.tight_layout()
plt.savefig(f"plots/{plot_dir}/precision_recall_vs_threshold_per_order.png")
plt.close()


print("✅ All selected plots generated successfully in 'plots/'")

# === Detailed Summary: Per Order × Threshold
print("\n📊 Detailed Summary (Per Order × Threshold):\n")
print(f"{' Order':>6} {'T':>4} | {'GT':>5} | {'TP':>4} | {'FP':>4} | {'FN':>4} || {'Precision':>10} | {'Recall':>8} | {'Jaccard':>8}")
print("-" * 80)

# Group by order and threshold
detailed = df.groupby(['hilbert_order', 't']).agg({
    'gt': 'sum', 'tp': 'sum', 'fp': 'sum', 'fn': 'sum'
}).reset_index()

# Calculate metrics
# detailed['precision'] = detailed['tp'] / (detailed['tp'] + detailed['fp'])
# detailed['recall'] = detailed['tp'] / (detailed['tp'] + detailed['fn'])
# detailed['jaccard'] = detailed['tp'] / (detailed['tp'] + detailed['fp'] + detailed['fn'])

# # Handle division-by-zero
# detailed[['precision', 'recall', 'jaccard']] = detailed[['precision', 'recall', 'jaccard']].fillna(0.0)

# # Print
# for _, row in detailed.iterrows():
#     print(f"{int(row['hilbert_order']):>6} {int(row['t']):>4} | "
#           f"{int(row['gt']):>5} | {int(row['tp']):>4} | {int(row['fp']):>4} | {int(row['fn']):>4} || "
#           f"{row['precision']:>10.3f} | {row['recall']:>8.3f} | {row['jaccard']:>8.3f}")


# === Categorized Threshold Summary Using Jaccard Index ===
threshold_bins = {
    'Low': list(range(5, 21, 5)),        # 5,10,15,20
    'Medium': list(range(25, 41, 5)),    # 25,30,35,40
    'High': list(range(45, 61, 5))       # 45,50,55,60
}

print("\n📊 Aggregated Performance by Threshold Category and Hilbert Order (Jaccard-Based):\n")
best_per_category = {}

for category, t_values in threshold_bins.items():
    cat_df = df[df['t'].isin(t_values)]
    grouped = cat_df.groupby('hilbert_order').agg({
        'tp': 'sum',
        'fp': 'sum',
        'fn': 'sum'
    }).reset_index()
    
    # Compute metrics
    grouped['precision'] = grouped['tp'] / (grouped['tp'] + grouped['fp'])
    grouped['recall'] = grouped['tp'] / (grouped['tp'] + grouped['fn'])
    grouped['jaccard'] = grouped['tp'] / (grouped['tp'] + grouped['fp'] + grouped['fn'])

    # Handle NaNs (e.g., division by zero)
    grouped = grouped.fillna(0.0)
    
    print(f"--- {category.upper()} RTT Thresholds ---")
    print(f"{'Order':>6} | {'TP':>6} | {'FP':>6} | {'FN':>6} | {'Jaccard':>8} | {'Precision':>9} | {'Recall':>7}")
    print("-" * 70)
    
    best_score = -1
    best_order = None
    
    for _, row in grouped.iterrows():
        order = int(row['hilbert_order'])
        tp = int(row['tp'])
        fp = int(row['fp'])
        fn = int(row['fn'])
        jaccard = row['jaccard']
        precision = row['precision']
        recall = row['recall']
        print(f"{order:>6} | {tp:>6} | {fp:>6} | {fn:>6} | {jaccard:>8.3f} | {precision:>9.3f} | {recall:>7.3f}")
        
        if jaccard > best_score:
            best_score = jaccard
            best_order = order
    
    best_per_category[category] = best_order
    print(f"🏆 Best Hilbert Order for {category}: {best_order} (Jaccard: {best_score:.3f})\n")

# === Final Summary ===
print("📈 Overall Best Hilbert Orders by RTT Category (Jaccard-Based):")
for cat, order in best_per_category.items():
    print(f" - {cat}: Order {order}")
