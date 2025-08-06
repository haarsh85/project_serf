import json
import math
from hilbertcurve.hilbertcurve import HilbertCurve

# Constants
DIMENSIONS = 5
BITS = 1  # controls granularity
LOG_FILE = "lawder162-3.txt"

# === Configurable Parameters ===
QUERY_NODE_NAME = "clab-nebula-serf1"
RTT_THRESHOLD_MS = 60
JSON_FILE = "cluster-status-2025-07-05T12_24_59.json"

# Logging function
def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")

# Load and parse nodes from Serf JSON
def load_nodes_from_json(filename):
    with open(filename, 'r') as f:
        data = json.load(f)
    nodes = []
    for node in data:
        vec = node["coordinate"]["Vec"]
        nodes.append({
            "name": node["name"],
            "vec": vec,
            "height": node["coordinate"].get("Height", 0),
            "adjustment": node["coordinate"].get("Adjustment", 0),
            "rtts": node.get("rtts", {})
        })
    return nodes

# Compute bounding box in each dimension
def compute_bounds(nodes):
    mins = [float('inf')] * DIMENSIONS
    maxs = [float('-inf')] * DIMENSIONS
    for node in nodes:
        for i in range(DIMENSIONS):
            v = node['vec'][i]
            mins[i] = min(mins[i], v)
            maxs[i] = max(maxs[i], v)
    log("Bounding box for 5D coordinates:")
    for i in range(DIMENSIONS):
        log(f"  Dimension {i}: min = {mins[i]:.6f}, max = {maxs[i]:.6f}")
    return list(zip(mins, maxs))

# Normalize a single coordinate to integer [0, 2^BITS)
def normalize_vec(vec, bounds):
    norm = []
    for i in range(DIMENSIONS):
        min_val, max_val = bounds[i]
        span = max_val - min_val
        if span == 0:
            norm.append(0)
        else:
            norm_val = int(((vec[i] - min_val) / span) * ((1 << BITS) - 1))
            norm.append(norm_val)
    return norm

# Compute Hilbert index for a node's vector
def compute_hilbert_index(vec, bounds, hilbert):
    norm_vec = normalize_vec(vec, bounds)
    return hilbert.distance_from_point(norm_vec), norm_vec

# Euclidean distance in 5D
def euclidean(a, b):
    return math.sqrt(sum((a[i] - b[i])**2 for i in range(DIMENSIONS)))

# Map RTT to coordinate radius by empirical sampling
def calibrate_rtt_to_radius(nodes, query_node, rtt_values):
    mapping = {}
    qvec = query_node['vec']
    for rtt in rtt_values:
        coords_within_rtt = []
        for n in nodes:
            target_rtt = query_node["rtts"].get(n["name"], float('inf'))
            if target_rtt <= rtt:
                coords_within_rtt.append(n["vec"])
        if not coords_within_rtt:
            mapping[rtt] = 0
        else:
            dists = [euclidean(qvec, vec) for vec in coords_within_rtt]
            max_dist = max(dists)
            mapping[rtt] = max_dist
        log(f"Calibrated RTT {rtt}ms -> max Euclidean distance {mapping[rtt]:.6f}")
    return mapping

# Recursively find Hilbert indices within bounding cube around query node
def query_within_rtt(query_node, rtt_threshold, nodes, bounds, hilbert, radius_map):
    qvec = query_node["vec"]
    q_index, q_norm = compute_hilbert_index(qvec, bounds, hilbert)
    radius = radius_map.get(rtt_threshold, 0)

    results = []
    log(f"\n=== Hilbert-based query for RTT <= {rtt_threshold}ms ===")
    log(f"Query Node: {query_node['name']}")
    log(f"Query Vec: {qvec}")
    log(f"Normalized Vec: {q_norm}")
    log(f"Hilbert Index: {q_index}")
    log(f"Radius (coord space): {radius:.6f}")

    for node in nodes:
        if node["name"] == query_node["name"]:
            continue
        dist = euclidean(qvec, node["vec"])
        if dist <= radius:
            results.append(node["name"])

    log(f"Hilbert Query Result: {len(results)} nodes within {rtt_threshold}ms")
    for name in results:
        log(f"  -> {name}")
    return results

# Ground truth based on RTT table
def get_true_neighbors(query_node, nodes, rtt_threshold):
    true_matches = []
    for node in nodes:
        if node["name"] == query_node["name"]:
            continue
        actual_rtt = query_node["rtts"].get(node["name"], float('inf'))
        if actual_rtt <= rtt_threshold:
            true_matches.append(node["name"])
    log(f"\nGround Truth (RTT <= {rtt_threshold}ms): {len(true_matches)} nodes")
    for name in true_matches:
        log(f" {name}")
    return true_matches

def accuracy_metrics(query_node_name, rtt_threshold_ms, hilbert_matches, true_matches, log_file_path):
    hilbert_set = set(hilbert_matches)
    true_set = set(true_matches)
    intersection = hilbert_set & true_set

    precision = len(intersection) / len(hilbert_set) if hilbert_set else 0.0
    recall = len(intersection) / len(true_set) if true_set else 0.0
    jaccard = len(intersection) / len(hilbert_set | true_set) if (hilbert_set | true_set) else 0.0

    false_positives = hilbert_set - true_set
    false_negatives = true_set - hilbert_set

    # Print to console
    print(f"\n--- Accuracy Test for {query_node_name} (RTT <= {rtt_threshold_ms}ms) ---")
    print(f"Hilbert: {len(hilbert_set)} nodes | RTT True: {len(true_set)} nodes")
    print(f"Match: {len(intersection)} | Precision: {precision:.2f} | Recall: {recall:.2f} | Jaccard: {jaccard:.2f}")
    print(f"False Positives ({len(false_positives)}): {sorted(false_positives)}")
    print(f"False Negatives ({len(false_negatives)}): {sorted(false_negatives)}")

    # Log to file
    with open(log_file_path, "a") as logf:
        logf.write(f"\n--- Accuracy Test for {query_node_name} (RTT <= {rtt_threshold_ms}ms) ---\n")
        logf.write(f"Hilbert: {len(hilbert_set)} nodes | RTT True: {len(true_set)} nodes\n")
        logf.write(f"Match: {len(intersection)} | Precision: {precision:.2f} | Recall: {recall:.2f} | Jaccard: {jaccard:.2f}\n")
        logf.write(f"False Positives ({len(false_positives)}): {sorted(false_positives)}\n")
        logf.write(f"False Negatives ({len(false_negatives)}): {sorted(false_negatives)}\n")

    return {
        "threshold": rtt_threshold_ms,
        "precision": precision,
        "recall": recall,
        "jaccard": jaccard,
        "false_positives": sorted(false_positives),
        "false_negatives": sorted(false_negatives)
    }

# Entry point
if __name__ == "__main__":
    with open(LOG_FILE, "w") as f:
        f.write("=== Debug log for 5D Serf Hilbert RTT Range Query ===\n")

    all_nodes = load_nodes_from_json(JSON_FILE)
    log(f"Loaded {len(all_nodes)} nodes from {JSON_FILE}")

    query_node = next((n for n in all_nodes if n["name"] == QUERY_NODE_NAME), None)
    if query_node is None:
        log(f"ERROR: Query node '{QUERY_NODE_NAME}' not found.")
        raise SystemExit(1)
    else:
        log(f"Selected query node: {QUERY_NODE_NAME}")

    bounds = compute_bounds(all_nodes)
    hilbert = HilbertCurve(p=BITS, n=DIMENSIONS)

    rtt_set = sorted(set([RTT_THRESHOLD_MS, 2, 5, 10, 20, 40, 80]))
    radius_map = calibrate_rtt_to_radius(all_nodes, query_node, rtt_set)

    # Run the Hilbert-based range query
    hilbert_matches = query_within_rtt(query_node, RTT_THRESHOLD_MS, all_nodes, bounds, hilbert, radius_map)

    # Compare with RTT ground truth
    true_matches = get_true_neighbors(query_node, all_nodes, RTT_THRESHOLD_MS)

    # Call the accuracy function after the query completes
    accuracy_metrics(QUERY_NODE_NAME, RTT_THRESHOLD_MS, hilbert_matches, true_matches, LOG_FILE)   

    log("\n=== Execution complete ===")
    print(f"✅ Execution finished. See '{LOG_FILE}' for full trace and results.")

    # # === NEW SECTION: Accuracy Metrics ===
    # query_node_name = QUERY_NODE_NAME
    # rtt_threshold_ms = RTT_THRESHOLD_MS

    # hilbert_set = set(hilbert_matches)
    # true_set = set(true_matches)
    # intersection = hilbert_set & true_set

    # precision = len(intersection) / len(hilbert_set) if hilbert_set else 0.0
    # recall = len(intersection) / len(true_set) if true_set else 0.0
    # jaccard = len(intersection) / len(hilbert_set | true_set) if (hilbert_set | true_set) else 0.0

    
    # print(f"\n--- Accuracy Test for {query_node_name} (RTT ≤ {rtt_threshold_ms}ms) ---")
    # print(f"Hilbert: {len(hilbert_set)} nodes | RTT True: {len(true_set)} nodes")
    # print(f"Match: {len(intersection)} | Precision: {precision:.2f} | Recall: {recall:.2f} | Jaccard: {jaccard:.2f}")