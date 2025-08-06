# ---------------------------------------------------------------------
# Hilbert Range Query Description (Modified Approach):
#
# 1. For each query node and RTT threshold T:
#    - Identify true neighbors within T ms using ground-truth RTTs
#    - Compute absolute Vec differences (5D) between query node and each true neighbor
#    - Take **max** of differences per dimension → forms a hyperrectangle
#
# 2. Map this hyperrectangle to Hilbert space:
#    - Convert hyperrectangle boundaries to integer grid coordinates
#    - Compute Hilbert indices for all 32 corners of the hyperrectangle
#    - Take 95th percentile of Hilbert distances from query to corners → radius
#
# 3. Perform range query:
#    - Return all nodes within ±radius of query's Hilbert index
#    - Evaluate against ground truth
# ---------------------------------------------------------------------

import json
import csv
import numpy as np
import itertools
from hilbertcurve.hilbertcurve import HilbertCurve
from tqdm import tqdm
from bisect import bisect_left, bisect_right

# ===== CONFIGURATION =====
INPUT_FILE = "cluster-status-2025-07-05T12_24_59.json"
OUTPUT_CSV = "range2-result.csv"  # Changed output name
hilbert_orders = [2, 4, 6, 8, 10]
thresholds = list(range(5, 65, 5))
dimensions = 5

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
    def norm_fn(vec):
        return ((np.array(vec) - min_vals) / (max_vals - min_vals + 1e-9)).clip(0, 1)
    print(f"[DEBUG] Normalization complete for {len(vecs)} vectors.")
    return norm_fn

def build_hilbert_indices(nodes, order, norm_fn):
    p = 2 ** order
    hc = HilbertCurve(order, dimensions)
    hilbert_indices = {}
    for name, node in nodes.items():
        vec = norm_fn(node["coordinate"]["Vec"])
        int_point = [int(x * (p-1)) for x in vec]
        hilbert_indices[name] = hc.distance_from_point(int_point)
    return hilbert_indices

def compute_ground_truth(node_data, T):
    return {target: rtt for target, rtt in node_data["rtts"].items() if rtt <= T}

def compute_hyperrectangle_radius(query_name, T, nodes, norm_fn, order, hilbert_indices,  vec_percentile=90, hilbert_percentile=95):
    # Get ground truth neighbors
    gt_rtts = compute_ground_truth(nodes[query_name], T)
    if not gt_rtts:
        return 0

    # Get normalized query vector
    query_vec = norm_fn(nodes[query_name]["coordinate"]["Vec"])

    # Collect vector differences per dimension
    dim_diffs = [[] for _ in range(dimensions)]
    for nb_name in gt_rtts:
        if nb_name not in nodes:
            continue
        nb_vec = norm_fn(nodes[nb_name]["coordinate"]["Vec"])
        for d in range(dimensions):
            dim_diffs[d].append(abs(query_vec[d] - nb_vec[d]))

    # Compute percentile instead of max difference per dimension
    R = [
        np.percentile(dim_diffs[d], vec_percentile) if dim_diffs[d] else 0
        for d in range(dimensions)
    ]

    # Create hyperrectangle in normalized space
    low_bound = [max(0, query_vec[d] - R[d]) for d in range(dimensions)]
    high_bound = [min(1, query_vec[d] + R[d]) for d in range(dimensions)]

    # Convert to integer grid coordinates
    p = 2 ** order
    low_int = [max(0, int(low_bound[d] * (p-1))) for d in range(dimensions)]
    high_int = [min(p-1, int(high_bound[d] * (p-1))) for d in range(dimensions)]

    # Generate all 32 corners of the hyperrectangle
    corner_coords = itertools.product(*[(low_int[d], high_int[d]) for d in range(dimensions)])

    # Compute Hilbert distances from query to each corner
    hc = HilbertCurve(order, dimensions)
    q_idx = hilbert_indices[query_name]
    distances = [abs(hc.distance_from_point(corner) - q_idx) for corner in corner_coords]

    return int(np.percentile(distances, hilbert_percentile))

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
    norm_fn = normalize_vecs(nodes)

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["hilbert_order", "q_node", "t", "gt", "found", "tp", "fp", "fn", "precision", "recall", "jaccard"])

        for order in hilbert_orders:
            print(f"\n[PROCESSING] Hilbert order {order}")
            hilbert_indices = build_hilbert_indices(nodes, order, norm_fn)
            sorted_items = sorted(hilbert_indices.items(), key=lambda x: x[1])
            indices_only = [idx for _, idx in sorted_items]

            for query_name in tqdm(nodes.keys(), desc=f"Order {order}"):
                q_idx = hilbert_indices[query_name]

                for T in thresholds:
                    gt_set = set(compute_ground_truth(nodes[query_name], T).keys())
                    radius = compute_hyperrectangle_radius(
                        query_name, T, nodes, norm_fn, order, hilbert_indices,
                        vec_percentile=90, hilbert_percentile=100  # you can tune these later!
                    )
                    found_set = hilbert_range_query(q_idx, radius, sorted_items, indices_only)
                    found_set.discard(query_name)  # Remove self

                    metrics = evaluate(gt_set, found_set)
                    row = [order, query_name, T] + list(metrics)
                    writer.writerow(row)

    print(f"\n[✓] Results written to {output_csv}")

if __name__ == "__main__":
    run_all_queries(INPUT_FILE, OUTPUT_CSV)
