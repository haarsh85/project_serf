"""
Modified Range2 code to integrate Serf's Height and Adjustment into Hilbert indexing and query radius.

Logic changes summary:
- Vec is originally 5D; we now extend coordinates to 7D by adding Height and Adjustment as two extra dimensions.
- Normalize Height and Adjustment alongside Vec, carefully handling Adjustment which can be negative.
  - Adjustment is normalized on its own range (including negatives).
- Hilbert curve indexing and hyperrectangle radius calculation use the extended 7D normalized vectors.
- The rest of the logic stays the same, ensuring the Hilbert curve captures both geometric Vec and non-Euclidean effects.
- This better approximates Serf's RTT distance model in the Hilbert space for more accurate range queries.

Note: Adjustment can be negative; normalization handles negative values properly by scaling linearly between min and max (which may be negative).
"""

import json
import csv
import numpy as np
import itertools
from hilbertcurve.hilbertcurve import HilbertCurve
from tqdm import tqdm
from bisect import bisect_left, bisect_right

# ===== CONFIGURATION =====
INPUT_FILE = "cluster-status-2025-07-05T12_24_59.json"
OUTPUT_CSV = "range4-result.csv"  # Changed output name to distinguish
hilbert_orders = [2, 4, 6, 8, 10]
thresholds = list(range(5, 65, 5))
dimensions = 7  # Changed from 5 to 7 (Vec 5D + Height + Adjustment)

# ===== FUNCTIONALITY =====

def load_data(filepath):
    with open(filepath, 'r') as f:
        raw_nodes = json.load(f)
    nodes = {node["name"]: node for node in raw_nodes}
    print(f"[DEBUG] Loaded {len(nodes)} nodes from {filepath}")
    return nodes

def normalize_vecs_with_height_adjustment(nodes):
    """
    Normalize Vec (5D) + Height + Adjustment (2D) to 7D normalized coordinates in [0,1].

    Special handling:
    - Adjustment can be negative; normalize linearly across min and max values.
    """
    vecs = [node["coordinate"]["Vec"] for node in nodes.values()]
    heights = [node["coordinate"]["Height"] for node in nodes.values()]
    adjustments = [node["coordinate"]["Adjustment"] for node in nodes.values()]

    # Convert lists to numpy arrays for vectorized operations
    vecs_np = np.array(vecs)  # shape (N,5)
    heights_np = np.array(heights).reshape(-1, 1)  # shape (N,1)
    adjustments_np = np.array(adjustments).reshape(-1, 1)  # shape (N,1)

    # Normalize Vec components independently
    vec_min = vecs_np.min(axis=0)
    vec_max = vecs_np.max(axis=0)
    norm_vecs = (vecs_np - vec_min) / (vec_max - vec_min + 1e-9)
    norm_vecs = np.clip(norm_vecs, 0, 1)

    # Normalize Height
    height_min = heights_np.min()
    height_max = heights_np.max()
    norm_heights = (heights_np - height_min) / (height_max - height_min + 1e-9)
    norm_heights = np.clip(norm_heights, 0, 1)

    # Normalize Adjustment (can be negative)
    adj_min = adjustments_np.min()
    adj_max = adjustments_np.max()
    norm_adjustments = (adjustments_np - adj_min) / (adj_max - adj_min + 1e-9)
    norm_adjustments = np.clip(norm_adjustments, 0, 1)

    # Concatenate normalized Vec + Height + Adjustment → 7D vector
    norm_all = np.hstack((norm_vecs, norm_heights, norm_adjustments))

    # Create a mapping from node name to its normalized 7D vector
    name_to_norm = {}
    for idx, node_name in enumerate(nodes.keys()):
        name_to_norm[node_name] = norm_all[idx]

    print(f"[DEBUG] Normalization complete for {len(nodes)} nodes including Height and Adjustment.")
    # Return a function that maps node_name -> normalized 7D vector
    def norm_fn_by_name(name):
        return name_to_norm[name]

    return norm_fn_by_name

def build_hilbert_indices(nodes, order, norm_fn):
    """
    Build Hilbert indices for all nodes using normalized 7D vectors (Vec + Height + Adjustment).
    """
    p = 2 ** order
    hc = HilbertCurve(order, dimensions)
    hilbert_indices = {}

    for name, node in nodes.items():
        norm_vec = norm_fn(name)  # 7D normalized vector
        int_point = [int(x * (p - 1)) for x in norm_vec]
        hilbert_indices[name] = hc.distance_from_point(int_point)

    return hilbert_indices

def compute_ground_truth(node_data, T):
    """
    Extract all neighbors with RTT <= T ms from ground truth RTTs.
    """
    return {target: rtt for target, rtt in node_data["rtts"].items() if rtt <= T}

def compute_hyperrectangle_radius(query_name, T, nodes, norm_fn, order, hilbert_indices,
                                 vec_percentile=95, hilbert_percentile=95):
    """
    Compute query radius in Hilbert space based on differences in normalized 7D vectors:
    - Use the vec_percentile percentile of absolute differences per dimension to form a hyperrectangle.
    - Map hyperrectangle corners to Hilbert indices.
    - Return hilbert_percentile percentile of distances from query's Hilbert index to corners.
    """
    gt_rtts = compute_ground_truth(nodes[query_name], T)
    if not gt_rtts:
        return 0

    query_vec = norm_fn(query_name)  # normalized 7D vector for query node

    # Collect absolute differences per dimension to all ground truth neighbors
    dim_diffs = [[] for _ in range(dimensions)]
    for nb_name in gt_rtts:
        if nb_name not in nodes:
            continue
        nb_vec = norm_fn(nb_name)
        for d in range(dimensions):
            dim_diffs[d].append(abs(query_vec[d] - nb_vec[d]))

    # Compute percentile differences per dimension for hyperrectangle radius
    R = [
        np.percentile(dim_diffs[d], vec_percentile) if dim_diffs[d] else 0
        for d in range(dimensions)
    ]

    # Define bounds of hyperrectangle in normalized space (clamped [0,1])
    low_bound = [max(0, query_vec[d] - R[d]) for d in range(dimensions)]
    high_bound = [min(1, query_vec[d] + R[d]) for d in range(dimensions)]

    # Convert bounds to integer grid coordinates for Hilbert curve
    p = 2 ** order
    low_int = [max(0, int(low_bound[d] * (p - 1))) for d in range(dimensions)]
    high_int = [min(p - 1, int(high_bound[d] * (p - 1))) for d in range(dimensions)]

    # Generate all 2^dimensions corners of the hyperrectangle
    corner_coords = itertools.product(*[(low_int[d], high_int[d]) for d in range(dimensions)])

    # Compute Hilbert distances from query point index to each corner index
    hc = HilbertCurve(order, dimensions)
    q_idx = hilbert_indices[query_name]
    distances = np.array(
        [abs(hc.distance_from_point(corner) - q_idx) for corner in corner_coords],
        dtype=np.float64
    )

    # Return percentile distance as radius for range query
    return int(np.percentile(distances, hilbert_percentile))

def hilbert_range_query(query_idx, radius, sorted_items, indices_only):
    """
    Return all nodes whose Hilbert indices are within ±radius of query_idx.
    """
    low = query_idx - radius
    high = query_idx + radius
    left = bisect_left(indices_only, low)
    right = bisect_right(indices_only, high)
    return {name for name, idx in sorted_items[left:right]}

def evaluate(gt, found):
    """
    Compute evaluation metrics: TP, FP, FN, Precision, Recall, Jaccard.
    """
    tp = len(gt & found)
    fp = len(found - gt)
    fn = len(gt - found)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    jaccard = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0
    return len(gt), len(found), tp, fp, fn, precision, recall, jaccard

def run_all_queries(input_file, output_csv):
    """
    Main driver function:
    - Load nodes
    - Normalize Vec + Height + Adjustment
    - For each Hilbert order, build indices and perform queries for each threshold
    - Write results to CSV
    """
    nodes = load_data(input_file)

    # Normalize all node coordinates to 7D vector
    global norm_fn
    norm_fn = normalize_vecs_with_height_adjustment(nodes)

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
                        vec_percentile=95, hilbert_percentile=95  # you can tune these later!
                    )
                    found_set = hilbert_range_query(q_idx, radius, sorted_items, indices_only)
                    found_set.discard(query_name)  # Remove self

                    metrics = evaluate(gt_set, found_set)
                    row = [order, query_name, T] + list(metrics)
                    writer.writerow(row)

    print(f"\n[✓] Results written to {output_csv}")

if __name__ == "__main__":
    run_all_queries(INPUT_FILE, OUTPUT_CSV)
