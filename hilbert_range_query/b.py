import json
from hilbertcurve.hilbertcurve import HilbertCurve
from math import sqrt
import numpy as np
from bisect import bisect_left, bisect_right

# === CONFIGURATION ===
JSON_PATH = "cluster-status-2025-07-05T12_24_59.json"
hilbert_order = 7 # You can change this to test different orders
dimensions = 5
query_nodes = ["clab-nebula-serf1"]  # Example, add more as needed
thresholds = list(range(5, 61, 5))  # RTT thresholds in ms: 5, 10, ..., 60

SEC_TO_MS = 1000.0

# === Load data ===
with open(JSON_PATH) as f:
    data = json.load(f)

nodes = {n['name']: n for n in data}

def get_overheads(qnode_name):
    qnode = nodes[qnode_name]
    q_overhead = height_adjustment_ms(qnode)
    max_other_overhead = max(
        height_adjustment_ms(n) for name, n in nodes.items() if name != qnode_name
    )
    return q_overhead, max_other_overhead

def get_overhead_percentile(qnode_name, percentile=90):
    overheads = [
        height_adjustment_ms(n) for name, n in nodes.items() if name != qnode_name
    ]
    perc_value = np.percentile(overheads, percentile)
    return perc_value

# Convert Vec from seconds to ms for distance calculations
def vec_in_ms(vec_seconds):
    return [v * SEC_TO_MS for v in vec_seconds]

# Get Height + Adjustment in ms, apply Serf's rule for Adjustment (only add if non-negative)
def height_adjustment_ms(node):
    height_ms = node['coordinate']['Height'] * SEC_TO_MS
    adj_raw = node['coordinate']['Adjustment'] * SEC_TO_MS
    adj_ms = adj_raw if adj_raw > 0 else 0.0
    return height_ms + adj_ms

# Normalize Vec coordinates for Hilbert indexing (unitless, no conversion)
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
            norm_val = (val - mins[i]) / denom if denom > 0 else 0.0
            scaled = int(norm_val * (2**hilbert_order - 1))
            norm_coords.append(scaled)
        norm[name] = norm_coords
    return norm

norm_coords = normalize_vecs(nodes)
hilbert_curve = HilbertCurve(p=hilbert_order, n=dimensions)
hilbert_indices = {name: hilbert_curve.distance_from_point(coords) for name, coords in norm_coords.items()}

sorted_nodes = sorted((idx, name) for name, idx in hilbert_indices.items())
hilbert_values = [t[0] for t in sorted_nodes]

# Euclidean distance between Vecs in ms
def euclidean_distance_ms(vec1_s, vec2_s):
    v1 = vec_in_ms(vec1_s)
    v2 = vec_in_ms(vec2_s)
    return sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))

# Serf distance estimate in ms (Vec Euclidean + Heights + Adjustments)
def serf_distance_ms(a, b):
    dist_vec = euclidean_distance_ms(a['coordinate']['Vec'], b['coordinate']['Vec'])
    ha = height_adjustment_ms(a)
    hb = height_adjustment_ms(b)
    return dist_vec + ha + hb

# Find max Height+Adjustment overhead in dataset (to conservatively estimate radius)
max_overhead = max(height_adjustment_ms(n) for n in nodes.values())

# Given RTT threshold and query node, compute adjusted Vec radius in ms:
def adjusted_vec_radius_ms(qnode_name, rtt_threshold_ms, overhead_percentile):
    q_overhead = height_adjustment_ms(nodes[qnode_name])
    radius = rtt_threshold_ms - q_overhead - overhead_percentile
    if radius < 0:
        radius = 0
    return radius

# Map adjusted radius (ms) to Hilbert index margin (integer)
def radius_to_hilbert_margin(qnode_name, radius_ms):
    # Normalize radius by max possible Euclidean distance in Vec space (in ms)
    # We'll approximate max Vec distance from min/max Vec in dataset:
    all_vecs_ms = [vec_in_ms(n['coordinate']['Vec']) for n in nodes.values()]
    mins = [min(v[i] for v in all_vecs_ms) for i in range(dimensions)]
    maxs = [max(v[i] for v in all_vecs_ms) for i in range(dimensions)]
    max_vec_dist = sqrt(sum((maxs[i] - mins[i]) ** 2 for i in range(dimensions)))
    
    if max_vec_dist == 0:
        return 0
    
    # Hilbert index max value
    max_hilbert = 2 ** (hilbert_order * dimensions) - 1
    
    # Normalize radius (0..max_vec_dist) to (0..max_hilbert)
    norm_radius = radius_ms / max_vec_dist
    margin = int(norm_radius * max_hilbert)
    return margin

# Hilbert range query using radius mapped to margin (no ground-truth needed)
def hilbert_range_query(qnode_name, adjusted_radius):
    qindex = hilbert_indices[qnode_name]
    #radius = adjusted_vec_radius_ms(qnode_name, rtt_threshold)
    radius = adjusted_radius
    margin = radius_to_hilbert_margin(qnode_name, radius)
    
    if margin == 0:
        return [qnode_name]
    
    lower = max(0, qindex - margin)
    upper = min(2 ** (hilbert_order * dimensions) - 1, qindex + margin)
    
    left_pos = bisect_left(hilbert_values, lower)
    right_pos = bisect_right(hilbert_values, upper)
    
    candidates = [sorted_nodes[i][1] for i in range(left_pos, right_pos)]
    
    print(f"[DEBUG] qnode={qnode_name} adjusted_radius={radius:.3f}ms margin={margin} candidates={len(candidates)}")
    return candidates

# Compute TP, FP, FN and metrics
def compute_metrics(qnode_name, threshold, candidates):
    qnode = nodes[qnode_name]
    gt_set = set()
    for other_name, other_node in nodes.items():
        if other_name == qnode_name:
            continue
        rtt = qnode['rtts'].get(other_name, None)
        if rtt is not None and rtt <= threshold:
            gt_set.add(other_name)
    found_set = set(candidates)
    found_set.discard(qnode_name)
    
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
        q_overhead = height_adjustment_ms(nodes[qnode])
        percentile_overhead = get_overhead_percentile(qnode, percentile=50)
        adjusted_radius = threshold - q_overhead - percentile_overhead
        if adjusted_radius < 0:
            adjusted_radius = 0.0

        percentile = 50
        print(f"[DEBUG] Threshold={threshold} ms")
        print(f"        Query overhead (Height+Adjustment): {q_overhead:.6f} ms")
        print(f"        Percentile-based other overhead: {percentile_overhead:.6f} ms ({percentile}th percentile)")
        print(f"        Adjusted radius (threshold - overheads): {adjusted_radius:.6f} ms")

        candidates = hilbert_range_query(qnode, adjusted_radius)
        tp, fp, fn, gt, found, precision, recall, jaccard = compute_metrics(qnode, threshold, candidates)
        print(f"[RESULT] Threshold={threshold}ms | GT={gt:3d} | Found={found:3d} | FP={fp} | FN={fn} | Precision={precision:.4f} | Recall={recall:.4f} | Jaccard={jaccard:.4f}")
    print()
