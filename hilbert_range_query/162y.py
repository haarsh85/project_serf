import json
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve
from math import sqrt
from collections import defaultdict

# === Parameters ===
json_path = "cluster-status-2025-07-05T12_24_59.json"
p = 10  # Hilbert order
dimension = 5  # 5D Vec
thresholds = [5, 10, 15, 20, 25, 30, 40, 50, 60]
query_nodes = [f"clab-nebula-serf{i}" for i in range(1, 161) if i == 1 or i % 5 == 0]

# === Load data ===
with open(json_path, "r") as f:
    data = json.load(f)

# === Normalize Vecs and Build Node Index ===
vecs = [node["coordinate"]["Vec"] for node in data]
vecs = np.array(vecs)
min_vals = vecs.min(axis=0)
max_vals = vecs.max(axis=0)
norm_vecs = (vecs - min_vals) / (max_vals - min_vals + 1e-9)
scaled_vecs = (norm_vecs * (2 ** p - 1)).astype(int)

node_dict = {}
name_to_index = {}
hilbert = HilbertCurve(p, dimension)
for i, node in enumerate(data):
    name = node["name"]
    vec = node["coordinate"]["Vec"]
    height = node["coordinate"]["Height"]
    adj = node["coordinate"]["Adjustment"]
    rtts = node["rtts"]
    norm = scaled_vecs[i]
    h_index = hilbert.distance_from_point(norm.tolist())
    node_dict[name] = {
        "Vec": np.array(vec),
        "Height": height,
        "Adjustment": adj,
        "RTTs": rtts,
        "HilbertIndex": h_index,
    }
    name_to_index[name] = i

# === Euclidean distance in Vec space ===
def vec_distance(a, b):
    return sqrt(np.sum((a - b) ** 2))

# === Main Evaluation ===
results = defaultdict(lambda: defaultdict(dict))

for qname in query_nodes:
    if qname not in node_dict:
        continue

    qnode = node_dict[qname]
    qvec = qnode["Vec"]
    qidx = qnode["HilbertIndex"]
    qheight = qnode["Height"]
    qadj = qnode["Adjustment"]
    qrtts = qnode["RTTs"]

    for T in thresholds:
        # Calculate safe Hilbert radius based on RTT threshold
        adjusted_thresholds = {}
        for name, other in node_dict.items():
            if name == qname:
                continue
            h2 = other["Height"]
            a2 = other["Adjustment"]
            budget = T - (qheight + h2 + qadj + a2)
            adjusted_thresholds[name] = budget

        # Candidate selection using Vec distance (no post-filtering)
        candidates = []
        for name, node in node_dict.items():
            if name == qname:
                continue
            budget = adjusted_thresholds[name]
            if budget < 0:
                continue
            d = vec_distance(qvec, node["Vec"])
            if d <= budget:
                candidates.append(name)

        # Ground truth: all nodes with actual RTT ≤ T
        gt = [name for name, rtt in qrtts.items() if rtt <= T]
        found = candidates

        tp = len(set(found) & set(gt))
        fp = len(set(found) - set(gt))
        fn = len(set(gt) - set(found))
        prec = tp / len(found) if found else 0.0
        recall = tp / len(gt) if gt else 0.0
        jaccard = tp / len(set(found) | set(gt)) if found or gt else 1.0

        results[qname][T] = {
            "GT": len(gt),
            "Found": len(found),
            "Precision": round(prec, 2),
            "Recall": round(recall, 2),
            "Jaccard": round(jaccard, 2),
            "FP": fp,
            "FN": fn,
        }

results.keys(), results["clab-nebula-serf1"].keys()  # Preview

# === Print Results ===
print(f"\n==== Query Results using Hilbert Order p={p} ====\n")

for qname in query_nodes:
    if qname not in results:
        continue
    print(f"==== Query Node {qname} ====")
    print(f"{'RTT':>5} | {'GT':>3} | {'Found':>5} | {'Prec':>5} | {'Recall':>6} | {'Jaccard':>7} | {'FP':>3} | {'FN':>3}")
    print("-" * 80)
    for T in thresholds:
        r = results[qname][T]
        print(f"{T:>5} | {r['GT']:>3} | {r['Found']:>5} | {r['Precision']:>5.2f} | {r['Recall']:>6.2f} | {r['Jaccard']:>7.2f} | {r['FP']:>3} | {r['FN']:>3}")
    print()

