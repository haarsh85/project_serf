import json
from hilbertcurve.hilbertcurve import HilbertCurve
from math import sqrt
import numpy as np
from bisect import bisect_left, bisect_right

# === CONFIGURATION ===
JSON_PATH = "cluster-status-2025-07-05T12_24_59.json"
hilbert_order = 10  # You can change this to test different orders
dimensions = 5
query_nodes = ["clab-nebula-serf1"] #+ [f"clab-nebula-serf{i}" for i in range(5, 161, 5)]
thresholds = list(range(5, 61, 5))  # 5,10,...60 ms

# === Load data ===
with open(JSON_PATH) as f:
    data = json.load(f)

# Build mapping node_name -> node dict
nodes = {n['name']: n for n in data}

# Normalize Vec coordinates (to integers) for Hilbert curve indexing
def normalize_vecs(nodes):
    all_vecs = [n['coordinate']['Vec'] for n in nodes.values()]
    mins = [min(coords[i] for coords in all_vecs) for i in range(dimensions)]
    maxs = [max(coords[i] for coords in all_vecs) for i in range(dimensions)]
    
    norm = {}
    for name, node in nodes.items():
        norm_coords = []
        for i in range(dimensions):
            denom = maxs[i] - mins[i]
            val = node['coordinate']['Vec'][i]
            if denom > 0:
                norm_val = (val - mins[i]) / denom
            else:
                norm_val = 0.0
            # Scale to integer grid 0..(2^hilbert_order -1)
            scaled = int(norm_val * (2**hilbert_order - 1))
            norm_coords.append(scaled)
        norm[name] = norm_coords
    return norm

norm_coords = normalize_vecs(nodes)

# Create Hilbert curve object
hilbert_curve = HilbertCurve(p=hilbert_order, n=dimensions)

# Compute Hilbert indices for all nodes
hilbert_indices = {}
for name, coords in norm_coords.items():
    hilbert_indices[name] = hilbert_curve.distance_from_point(coords)

# Build a sorted list of (hilbert_index, node_name) for binary search
sorted_nodes = sorted((idx, name) for name, idx in hilbert_indices.items())
hilbert_values = [t[0] for t in sorted_nodes]  # sorted hilbert indices only

# Euclidean distance in Vec-space
def euclidean_distance(vec1, vec2):
    return sqrt(sum((a - b) ** 2 for a, b in zip(vec1, vec2)))

# Compute empirical Vec-space radius per query node and RTT threshold
def empirical_radius(qnode_name, rtt_threshold):
    # Ground truth neighbors within RTT threshold from qnode
    qnode = nodes[qnode_name]
    neighbors = []
    for other_name, other_node in nodes.items():
        if other_name == qnode_name:
            continue
        rtt = qnode['rtts'].get(other_name, None)
        if rtt is not None and rtt <= rtt_threshold:
            neighbors.append(other_name)
    if not neighbors:
        print(f"[DEBUG] No neighbors within RTT {rtt_threshold} ms for node {qnode_name}")
        return 0.0
    # Compute max Vec-space distance among these neighbors
    qvec = qnode['coordinate']['Vec']
    max_dist = 0.0
    for nb in neighbors:
        dist = euclidean_distance(qvec, nodes[nb]['coordinate']['Vec'])
        if dist > max_dist:
            max_dist = dist
    print(f"[DEBUG] Node {qnode_name}, RTT Threshold {rtt_threshold} ms: Found {len(neighbors)} neighbors, Empirical radius = {max_dist:.6f}")
    return max_dist

# Find candidates via Hilbert index range query given radius in Vec-space
# def hilbert_range_query(qnode_name, radius):
#     if radius == 0:
#         # Only the query node itself
#         return [qnode_name]
#     qcoords = norm_coords[qnode_name]
#     qindex = hilbert_indices[qnode_name]
    
#     # To find candidate Hilbert indices, find nodes with Hilbert distance <= delta.
#     # But no direct "Hilbert distance" function, so approximate by finding nodes with hilbert indices in range:
#     # [qindex - margin, qindex + margin] where margin corresponds roughly to radius mapped to Hilbert index scale.
#     #
#     # Here we map the Vec-space radius to an approximate Hilbert index margin.
#     # Max coordinate difference corresponding to radius:
#     # Normalize radius to normalized space by normalizing max_dist / dimension range.
#     # However, we simplify: since Hilbert index space is discrete [0, 2^{p*n}-1], just choose a margin.
#     #
#     # Because this is complex, we use a simple heuristic: map radius in Vec-space proportionally to Hilbert index range:
#     margin = int(radius * (2**hilbert_order - 1) * dimensions)
#     lower = max(0, qindex - margin)
#     upper = qindex + margin
    
#     # Find left and right indices using bisect
#     left_pos = bisect_left(hilbert_values, lower)
#     right_pos = bisect_right(hilbert_values, upper)
#     candidate_names = [sorted_nodes[i][1] for i in range(left_pos, right_pos)]
#     return candidate_names

def empirical_hilbert_margin(qnode_name, rtt_threshold):
    qindex = hilbert_indices[qnode_name]
    gt_neighbors = []

    qnode = nodes[qnode_name]
    for other_name, other_node in nodes.items():
        if other_name == qnode_name:
            continue
        rtt = qnode['rtts'].get(other_name, None)
        if rtt is not None and rtt <= rtt_threshold:
            gt_neighbors.append(other_name)

    if not gt_neighbors:
        return 0

    margin = max(abs(qindex - hilbert_indices[n]) for n in gt_neighbors)
    return margin


def hilbert_range_query(qnode_name, rtt_threshold):
    qindex = hilbert_indices[qnode_name]
    margin = empirical_hilbert_margin(qnode_name, rtt_threshold)

    if margin == 0:
        return [qnode_name]

    lower = max(0, qindex - margin)
    upper = min(2**(hilbert_order * dimensions) - 1, qindex + margin)

    left_pos = bisect_left(hilbert_values, lower)
    right_pos = bisect_right(hilbert_values, upper)

    candidate_names = [sorted_nodes[i][1] for i in range(left_pos, right_pos)]

    print(f"[DEBUG] margin={margin}, qindex={qindex}, range=({lower}, {upper}), candidates={len(candidate_names)}")
    return candidate_names



# Compute TP, FP, FN and metrics
def compute_metrics(qnode_name, threshold, candidates):
    qnode = nodes[qnode_name]
    # Ground truth neighbors
    gt_set = set()
    for other_name, other_node in nodes.items():
        if other_name == qnode_name:
            continue
        rtt = qnode['rtts'].get(other_name, None)
        if rtt is not None and rtt <= threshold:
            gt_set.add(other_name)
    
    found_set = set(candidates)
    if qnode_name in found_set:
        found_set.remove(qnode_name)  # Exclude query node itself
    
    tp = len(gt_set.intersection(found_set))
    fp = len(found_set - gt_set)
    fn = len(gt_set - found_set)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    jaccard = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
    
    return tp, fp, fn, len(gt_set), len(found_set), precision, recall, jaccard

# === MAIN RUN ===
for qnode in query_nodes:
    print(f"==== Query Node {qnode} ====")
    for threshold in thresholds:
        radius = empirical_radius(qnode, threshold)
        candidates = hilbert_range_query(qnode, threshold)
        tp, fp, fn, gt, found, precision, recall, jaccard = compute_metrics(qnode, threshold, candidates)
        print(f"[RESULT] Threshold={threshold}ms | GT={gt:3d} | Found={found:3d} | FP={fp} | FN={fn} | Precision={precision:.4f} | Recall={recall:.4f} | Jaccard={jaccard:.4f}")
    print()
