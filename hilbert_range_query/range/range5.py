import json
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve
from bisect import bisect_left, bisect_right
from tqdm import tqdm
import csv

# === CONFIGURATION ===
JSON_PATH = "cluster-status-2025-07-05T12_24_59.json"
OUTPUT_CSV = "range5-result.csv"
HILBERT_ORDERS = [2, 4, 6, 8, 10]
THRESHOLDS = list(range(5, 65, 5))  # RTT thresholds in ms
VEC_DIMENSIONS = 5
VEC_PERCENTILE = 95
HILBERT_PERCENTILE = 95

# === Load Node Data ===
with open(JSON_PATH) as f:
    data = json.load(f)

print(f"[DEBUG] Loaded {len(data)} nodes from {JSON_PATH}")

nodes = {n["name"]: n["coordinate"] for n in data}
rtts = {n["name"]: n["rtts"] for n in data}
all_node_names = list(nodes.keys())

# === Normalization ===
def compute_normalization_params(nodes):
    vecs = [coord["Vec"] for coord in nodes.values()]
    vecs_np = np.array(vecs)
    min_vals = vecs_np.min(axis=0)
    max_vals = vecs_np.max(axis=0)
    return min_vals, max_vals

def normalize_vec(vec, min_vals, max_vals):
    vec = np.array(vec)
    normed = (vec - min_vals) / (max_vals - min_vals + 1e-9)
    return normed.clip(0, 1).tolist()

min_vals, max_vals = compute_normalization_params(nodes)
print(f"[DEBUG] Normalization complete for {len(nodes)} vectors.")

def compute_ground_truth(query_name, T):
    if query_name not in rtts:
        return set()
    return {
        name for name, rtt_val in rtts[query_name].items()
        if rtt_val <= T and name != query_name
    }

def scale_vec(vec, order):
    normed = normalize_vec(vec, min_vals, max_vals)
    max_val = 2 ** order - 1
    return [min(max(int(v * max_val), 0), max_val) for v in normed]

def compute_hilbert_indices(order):
    hc = HilbertCurve(order, VEC_DIMENSIONS)
    return {
        name: hc.distance_from_point(scale_vec(nodes[name]["Vec"], order))
        for name in all_node_names
    }

def compute_radius(query_name, T, order, hilbert_indices, vec_percentile, hilbert_percentile):
    gt = compute_ground_truth(query_name, T)
    if not gt:
        return None, None, set()

    q_vec = normalize_vec(nodes[query_name]["Vec"], min_vals, max_vals)
    diffs_per_dim = [[] for _ in range(VEC_DIMENSIONS)]

    for nb in gt:
        nb_vec = normalize_vec(nodes[nb]["Vec"], min_vals, max_vals)
        for d in range(VEC_DIMENSIONS):
            diffs_per_dim[d].append(abs(q_vec[d] - nb_vec[d]))

    vec_radius = [np.percentile(diffs, vec_percentile) for diffs in diffs_per_dim]

    lower = [max(0, q_vec[d] - vec_radius[d]) for d in range(VEC_DIMENSIONS)]
    upper = [min(1, q_vec[d] + vec_radius[d]) for d in range(VEC_DIMENSIONS)]

    hc = HilbertCurve(order, VEC_DIMENSIONS)
    max_val = 2 ** order - 1
    low = [int(v * max_val) for v in lower]
    high = [int(v * max_val) for v in upper]

    q_idx = hilbert_indices[query_name]
    diffs = [abs(hilbert_indices[nb] - q_idx) for nb in gt if nb in hilbert_indices]
    if not diffs:
        return None, None, set()

    h_radius = np.percentile(diffs, hilbert_percentile)
    hmin = max(0, int(q_idx - h_radius))
    hmax = int(q_idx + h_radius)

    found = {name for name, idx in hilbert_indices.items() if hmin <= idx <= hmax}
    return hmin, hmax, found

# === Run Evaluation ===
results = []

for order in HILBERT_ORDERS:
    print(f"\n[PROCESSING] Hilbert order {order}")
    hilbert_indices = compute_hilbert_indices(order)
    for query_name in tqdm(all_node_names, desc=f"Order {order}"):
        for T in THRESHOLDS:
            gt_set = compute_ground_truth(query_name, T)
            hmin, hmax, found_set = compute_radius(
                query_name, T, order, hilbert_indices,
                VEC_PERCENTILE, HILBERT_PERCENTILE
            )
            if found_set is None:
                found_set = set()
            found_set.discard(query_name)
            tp = len(gt_set & found_set)
            fp = len(found_set - gt_set)
            fn = len(gt_set - found_set)
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            jaccard = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
            results.append([
                order, query_name, T, len(gt_set), len(found_set),
                tp, fp, fn, precision, recall, jaccard
            ])

# === Write CSV Output ===
with open(OUTPUT_CSV, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "hilbert_order", "q_node", "t", "gt", "found", "tp",
        "fp", "fn", "precision", "recall", "jaccard"
    ])
    writer.writerows(results)

print(f"\n[COMPLETE] Results saved to {OUTPUT_CSV}")
