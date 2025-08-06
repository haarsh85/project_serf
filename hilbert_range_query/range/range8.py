import json
import csv
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve
from tqdm import tqdm
from bisect import bisect_left, bisect_right

# === CONFIG ===
INPUT_JSON = "cluster-status-2025-07-05T12_24_59.json"
OUTPUT_CSV = "range8-result.csv"

DIMENSIONS = 5  # Working with Vec of length 5
HILBERT_ORDERS = [2, 4, 6, 8, 10]
THRESHOLDS = list(range(5, 65, 5))
PERCENTILE = 95  # percentile for radius calculation

# --- UTILITIES ---

def load_data(json_path):
    """Load JSON data and extract node info and Vec coordinates."""
    with open(json_path, "r") as f:
        data = json.load(f)
    nodes = []
    for entry in data:
        name = entry["name"]
        vec = entry["coordinate"]["Vec"]
        rtts = entry.get("rtts", {})
        nodes.append({"name": name, "vec": np.array(vec), "rtts": rtts})
    return nodes

def normalize_coords(nodes):
    """Normalize Vec coords globally per dimension to [0,1]."""
    all_vecs = np.array([node["vec"] for node in nodes])
    mins = all_vecs.min(axis=0)
    maxs = all_vecs.max(axis=0)
    ranges = maxs - mins
    # Avoid div by zero if any dimension has zero range:
    ranges[ranges == 0] = 1.0
    for node in nodes:
        node["vec_norm"] = (node["vec"] - mins) / ranges
    return mins, maxs, ranges

def compute_ground_truth(nodes, threshold):
    """
    Compute ground truth neighbors per query node for given RTT threshold.
    Returns dict: {query_node_name: set of neighbor names within RTT threshold}.
    """
    gt = {}
    # For efficient lookup, create a map name->node
    name_to_node = {n["name"]: n for n in nodes}
    for qnode in nodes:
        qname = qnode["name"]
        neighbors = set()
        for target_name, rtt_val in qnode["rtts"].items():
            if rtt_val <= threshold:
                neighbors.add(target_name)
        gt[qname] = neighbors
    return gt

def compute_hilbert_keys(nodes, order):
    """Compute Hilbert keys of normalized Vec coords for all nodes."""
    hilbert = HilbertCurve(p=order, n=DIMENSIONS)
    max_val = 2 ** order - 1
    for node in nodes:
        # Scale normalized coordinates to integer grid [0, max_val]
        coords_int = [min(max(int(round(x * max_val)), 0), max_val) for x in node["vec_norm"]]
        node["hilbert_key"] = hilbert.distance_from_point(coords_int)
    # Sort nodes by hilbert_key for efficient querying
    nodes_sorted = sorted(nodes, key=lambda x: x["hilbert_key"])
    return nodes_sorted, hilbert, max_val

def compute_query_region_radius(qnode, neighbors, percentile=PERCENTILE):
    """
    Compute 5D radius vector for query node qnode and neighbors:
    percentile of absolute differences per dimension in normalized Vec space.
    """
    if not neighbors:
        # No neighbors, return zero radius
        return np.zeros(DIMENSIONS)
    diffs = []
    qvec = qnode["vec_norm"]
    for n in neighbors:
        diff = np.abs(n["vec_norm"] - qvec)
        diffs.append(diff)
    diffs = np.array(diffs)
    radius = np.percentile(diffs, percentile, axis=0)
    return radius

def query_hilbert_range(nodes_sorted, hilbert, qnode, radius, max_val):
    """
    Given query node and radius in normalized Vec space, build query hyperrectangle,
    compute hilbert key interval [low, high] for corners, 
    and find nodes within that interval.
    """
    qvec = qnode["vec_norm"]
    # Clip query bounds to [0,1]
    low_corner = np.clip(qvec - radius, 0, 1)
    high_corner = np.clip(qvec + radius, 0, 1)

    # Convert to integer coords for hilbert
    low_coords = [min(max(int(round(x * max_val)), 0), max_val) for x in low_corner]
    high_coords = [min(max(int(round(x * max_val)), 0), max_val) for x in high_corner]

    low_key = hilbert.distance_from_point(low_coords)
    high_key = hilbert.distance_from_point(high_coords)

    # Ensure low_key <= high_key
    low_key, high_key = min(low_key, high_key), max(low_key, high_key)

    # Binary search in nodes_sorted for interval
    keys = [n["hilbert_key"] for n in nodes_sorted]
    left = bisect_left(keys, low_key)
    right = bisect_right(keys, high_key)

    found_nodes = set()
    for i in range(left, right):
        found_nodes.add(nodes_sorted[i]["name"])

    return found_nodes

def evaluate(gt_set, found_set):
    """Compute evaluation metrics given ground truth and found sets."""
    tp = len(gt_set & found_set)
    fp = len(found_set - gt_set)
    fn = len(gt_set - found_set)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    jaccard = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
    return len(gt_set), len(found_set), tp, fp, fn, precision, recall, jaccard

# === MAIN PROCESS ===

def main():
    print("[INFO] Loading data...")
    nodes = load_data(INPUT_JSON)

    print("[INFO] Normalizing coordinates globally...")
    mins, maxs, ranges = normalize_coords(nodes)

    # For quick name -> node lookup
    name_to_node = {n["name"]: n for n in nodes}

    with open(OUTPUT_CSV, "w", newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["hilbert_order", "q_node", "t", "gt", "found", "tp", "fp", "fn", "precision", "recall", "jaccard"])

        for order in HILBERT_ORDERS:
            print(f"[PROCESSING] Order {order}")
            # Compute hilbert keys and sorted nodes
            nodes_sorted, hilbert, max_val = compute_hilbert_keys(nodes, order)

            for qnode in tqdm(nodes, desc=f"Order {order}", unit="nodes"):
                qname = qnode["name"]

                # Precompute RTT-based ground truth neighbors for all thresholds (cache)
                # For efficiency, do it once per node outside threshold loop
                # But thresholds differ, so do per threshold below

                for t in THRESHOLDS:
                    # Compute ground truth neighbors within RTT <= t
                    gt_neighbors_names = set()
                    for nb_name, rtt_val in qnode["rtts"].items():
                        if rtt_val <= t:
                            gt_neighbors_names.add(nb_name)
                    # Map to node objects, exclude missing
                    gt_neighbors = [name_to_node[n] for n in gt_neighbors_names if n in name_to_node]

                    # Compute query region radius using 95th percentile
                    radius = compute_query_region_radius(qnode, gt_neighbors, percentile=PERCENTILE)

                    # Query hilbert curve for candidate nodes
                    found_names = query_hilbert_range(nodes_sorted, hilbert, qnode, radius, max_val)

                    # Evaluate results
                    gt_set = gt_neighbors_names
                    found_set = found_names

                    gt_count, found_count, tp, fp, fn, prec, rec, jac = evaluate(gt_set, found_set)

                    writer.writerow([order, qname, t, gt_count, found_count, tp, fp, fn, prec, rec, jac])

    print("[DONE] Results saved to", OUTPUT_CSV)


if __name__ == "__main__":
    main()
