# ---------------------------------------------------------------------
# Hilbert Range Query Description:
#
# Given a query node and an RTT threshold T (e.g., 10 ms), we first use
# the known ground-truth RTTs to identify the true neighbors of the query
# node that lie within T milliseconds. We then compute the absolute
# Hilbert index differences between the query node and each of its true
# neighbors (based on 5D Vec only). From these differences, we take the
# 95th percentile to determine a radius — the maximum Hilbert distance
# that still captures most (95%) of the true neighbors within T.
#
# Using this radius, the actual range query returns all nodes whose
# Hilbert indices lie within ±radius of the query node’s Hilbert index.
# No RTT-based post-filtering is allowed. The result is then evaluated
# against the RTT-based ground truth for precision, recall, and Jaccard.
# ---------------------------------------------------------------------

import json
import csv
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve
from tqdm import tqdm
from collections import defaultdict
from bisect import bisect_left, bisect_right
from math import sqrt
import sys
sys.stdout = open("range1-debug-log.txt", "w")

# ===== CONFIGURATION =====
INPUT_FILE = "cluster-status-2025-07-05T12_24_59.json"
OUTPUT_CSV = "range1-result.csv"
hilbert_orders = [2, 4, 6, 8, 10]
thresholds = list(range(5, 65, 5))  # 5 to 60 ms
dimensions = 5  # Vec is 5D

# ===== FUNCTIONALITY =====

def load_data(filepath):
    with open(filepath, 'r') as f:
        raw_nodes = json.load(f)
    nodes = {node["name"]: node for node in raw_nodes}
    print(f"[DEBUG] Loaded {len(nodes)} nodes from {filepath}")
    return nodes

def normalize_vecs(nodes):
    vecs = [node["coordinate"]["Vec"] for node in nodes.values()]
    vecs_np = np.array(vecs)
    min_vals = vecs_np.min(axis=0)
    max_vals = vecs_np.max(axis=0)
    def norm_fn(vec):  # Normalize to [0, 2^bits_per_dimension - 1]
        return ((np.array(vec) - min_vals) / (max_vals - min_vals + 1e-9)).clip(0, 1)
    print(f"[DEBUG] Normalization complete for {len(vecs)} vectors.")
    return norm_fn

def build_hilbert_indices(nodes, order, norm_fn):
    p = 2 ** order
    hc = HilbertCurve(order, dimensions)
    hilbert_indices = {}
    for i, (name, node) in enumerate(nodes.items()):
        vec = norm_fn(node["coordinate"]["Vec"])
        int_point = [int(x * (p - 1)) for x in vec]
        hilbert_indices[name] = hc.distance_from_point(int_point)
        if i % 10 == 0:
            print(f"[DEBUG] Mapped {i+1}/{len(nodes)} nodes to Hilbert index (order {order})")
        
    return hilbert_indices

def compute_ground_truth(node_data, T):
    return {target for target, rtt in node_data["rtts"].items() if rtt <= T}

def compute_radius_95(query_name, T, nodes, hilbert_indices):
    gt = compute_ground_truth(nodes[query_name], T)
    if not gt:
        print(f"[DEBUG] No GT neighbors for {query_name} at threshold {T}ms")
        return 0  # No neighbors within T
    q_idx = hilbert_indices[query_name]
    diffs = [abs(hilbert_indices[nb] - q_idx) for nb in gt if nb in hilbert_indices]
    if not diffs:
        return 0
    radius = int(np.percentile(diffs, 95))
    print(f"[DEBUG] Radius for {query_name} @ {T}ms = {radius}")
    return radius

def hilbert_range_query(query_idx, radius, sorted_items, indices_only):
    low = query_idx - radius
    high = query_idx + radius
    left = bisect_left(indices_only, low)
    right = bisect_right(indices_only, high)
    return {name for name, idx in sorted_items[left:right]}

def evaluate(gt, found):
    tp = len(gt & found)
    fp = len(found - gt)
    fn = len(gt - found)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    jaccard = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0
    return len(gt), len(found), tp, fp, fn, precision, recall, jaccard

def run_all_queries(input_file, output_csv):
    nodes = load_data(input_file)
    print("[DEBUG] type(nodes):", type(nodes))
    norm_fn = normalize_vecs(nodes)

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["hilbert_order", "q_node", "t", "gt", "found", "tp", "fp", "fn", "precision", "recall", "jaccard"])

        for order in hilbert_orders:
            hilbert_indices = build_hilbert_indices(nodes, order, norm_fn)
            sorted_items = sorted(hilbert_indices.items(), key=lambda x: x[1])  # [(name, idx)]
            indices_only = [idx for _, idx in sorted_items]
            print(f"[DEBUG] Sample sorted indices (order {order}): {sorted_items[:5]}")

            for query_name in tqdm(nodes.keys(), desc=f"Hilbert Order {order}"):
                print(f"\n[DEBUG] Querying node: {query_name}")
                q_idx = hilbert_indices[query_name]

                for T in thresholds:
                    gt_set = compute_ground_truth(nodes[query_name], T)
                    radius = compute_radius_95(query_name, T, nodes, hilbert_indices)
                    found_set = hilbert_range_query(q_idx, radius, sorted_items, indices_only)
                    found_set = found_set - {query_name}
                    metrics = evaluate(gt_set, found_set)
                    print(f"[DEBUG] T={T}ms | GT={len(gt_set)} Found={len(found_set)} TP={metrics[2]} FP={metrics[3]} FN={metrics[4]}")
                    row = [order, query_name, T] + list(metrics)
                    writer.writerow(row)

    print(f"\nResults written to {output_csv}")

# ===== RUN MAIN =====
if __name__ == "__main__":
    run_all_queries(INPUT_FILE, OUTPUT_CSV)
