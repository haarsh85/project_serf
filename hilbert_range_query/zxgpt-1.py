import csv
from collections import defaultdict

INPUT_CSV = "a.csv"  # Replace with your CSV filename

# Data structure: {(hilbert_order, threshold): {"TP":0, "FP":0, "FN":0}}
agg_data = defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0})

with open(INPUT_CSV, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = (int(row["hilbert_order"]), int(row["threshold"]))
        agg_data[key]["TP"] += int(row["tp"])
        agg_data[key]["FP"] += int(row["fp"])
        agg_data[key]["FN"] += int(row["fn"])

print(f"{'Hilbert Order':>12} {'Threshold(ms)':>14} {'Precision':>10} {'Recall':>10} {'Jaccard':>10}")
for (p, T), counts in sorted(agg_data.items()):
    TP, FP, FN = counts["TP"], counts["FP"], counts["FN"]
    precision = TP / (TP + FP) if (TP + FP) > 0 else (1.0 if TP + FP + FN == 0 else 0.0)
    recall    = TP / (TP + FN) if (TP + FN) > 0 else (1.0 if TP + FP + FN == 0 else 0.0)
    jaccard   = TP / (TP + FP + FN) if (TP + FP + FN) > 0 else 1.0

    print(f"{p:12d} {T:14d} {precision:10.4f} {recall:10.4f} {jaccard:10.4f}")
