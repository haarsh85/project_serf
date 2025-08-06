import json
from z import EmpiricalHilbertRangeQuery  # Replace with your actual class file
from collections import defaultdict

# === Config ===
json_path = "cluster-status-2025-07-05T12_24_59.json"       # your JSON dataset path
query_node = "clab-nebula-serf90"        # query node to test
thresholds = [5, 10, 15, 20, 25, 30, 35, 40]  # RTT thresholds to evaluate
hilbert_orders = [2, 4, 6, 8, 10, 12, 16]        # p values to compare

# === Ground Truth ===
with open(json_path, "r") as f:
    data = json.load(f)
nodes_by_name = {node["name"]: node for node in data}

def get_ground_truth(query_node, threshold):
    return {target for target, rtt in nodes_by_name[query_node]["rtts"].items() if rtt <= threshold}

# === Run Experiments ===
results = defaultdict(list)  # p → list of (threshold, precision, recall, GT, FP, FN, jaccard)

for p in hilbert_orders:
    print(f"\n==== Running for p = {p} ====")
    system = EmpiricalHilbertRangeQuery(json_path=json_path, p=p)
    
    for threshold in thresholds:
        found = set(system.query(query_node, threshold))
        truth = get_ground_truth(query_node, threshold)

        TP = len(found & truth)
        FP = len(found - truth)
        FN = len(truth - found)
        GT = len(truth)
        precision = TP / (TP + FP) if TP + FP > 0 else 0.0
        recall = TP / (TP + FN) if TP + FN > 0 else 0.0
        jaccard = TP / (TP + FP + FN) if TP + FP + FN > 0 else 0.0

        results[p].append((threshold, precision, recall, GT, FP, FN, jaccard))

# === Print Summary Table ===
print("\n===== Comparison Summary =====")
print(" p | Thresh |  GT | Found | FP | FN | Prec | Recall | Jacc")
print("-------------------------------------------------------------")
for p in hilbert_orders:
    for (threshold, precision, recall, GT, FP, FN, jaccard) in results[p]:
        found = GT + FP - FN  # derived from TP + FP
        print(f"{p:2} | {threshold:6} | {GT:3} |"
              f" {found:5} | {FP:2} | {FN:2} |"
              f" {precision:5.3f} | {recall:6.3f} | {jaccard:5.3f}")


