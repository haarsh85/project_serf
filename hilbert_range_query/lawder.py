import json
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve
from sklearn.linear_model import LinearRegression

# CONFIG
BITS = 7
DIMENSIONS = 5
RTT_THRESHOLD_MS = 15
QUERY_NODE_NAME = "clab-nebula-serf1"
INPUT_FILE = "cluster-status-2025-07-05T12_24_59.json"
DEBUG_LOG = "lawder-fixed.txt"

def debug_print(*args, **kwargs):
    with open(DEBUG_LOG, "a") as f:
        print(*args, **kwargs, file=f)

# Clear previous debug log
open(DEBUG_LOG, "w").close()

# Load data
with open(INPUT_FILE, "r") as f:
    node_data = json.load(f)

nodes = [n["name"] for n in node_data]
node_map = {n["name"]: n for n in node_data}
vecs = [n["coordinate"]["Vec"] for n in node_data]

# Normalize range computation
min_vals = np.min(vecs, axis=0)
max_vals = np.max(vecs, axis=0)
debug_print("[Min/Max per dimension]")
for i in range(DIMENSIONS):
    debug_print(f"Dim {i}: min={min_vals[i]}, max={max_vals[i]}")

def normalize_vec(vec):
    scale = (2**BITS - 1)
    norm = [
        int((v - min_v) / (max_v - min_v) * scale) if max_v > min_v else 0
        for v, min_v, max_v in zip(vec, min_vals, max_vals)
    ]
    debug_print(f"Normalize vec {vec} -> {norm}")
    return norm

hilbert = HilbertCurve(p=BITS, n=DIMENSIONS)
norm_vec_map = {}
hilbert_index_map = {}

debug_print("\n=== Building Hilbert Index Map ===")
for n in node_data:
    name = n["name"]
    vec = n["coordinate"]["Vec"]
    norm_vec = normalize_vec(vec)
    h_index = hilbert.distance_from_point(norm_vec)
    norm_vec_map[name] = norm_vec
    hilbert_index_map[name] = h_index
    debug_print(f"[Hilbert] {name} -> Vec: {vec}, NormVec: {norm_vec}, Index: {h_index}")

query_node = node_map[QUERY_NODE_NAME]
rtt_matches = {name: rtt for name, rtt in query_node.get("rtts", {}).items() if rtt <= RTT_THRESHOLD_MS}
true_match_names = set(rtt_matches.keys())

debug_print(f"\n[True RTT Matches for {QUERY_NODE_NAME} <= {RTT_THRESHOLD_MS} ms]")
debug_print(f"Count: {len(true_match_names)}")
debug_print(f"Nodes: {sorted(true_match_names)}")

# Regression: RTT vs Euclidean distance
query_vec = np.array(query_node["coordinate"]["Vec"])
eucl_dists = []
rtts = []

for other_name, rtt in query_node.get("rtts", {}).items():
    if other_name in node_map:
        other_vec = np.array(node_map[other_name]["coordinate"]["Vec"])
        dist = np.linalg.norm(other_vec - query_vec)
        eucl_dists.append(dist)
        rtts.append(rtt)

if len(eucl_dists) >= 2:
    X = np.array(eucl_dists).reshape(-1, 1)
    y = np.array(rtts)
    model = LinearRegression().fit(X, y)
    a = model.coef_[0]
    b = model.intercept_
    debug_print(f"\n[Linear Regression RTT vs Euclidean Distance]")
    debug_print(f"Slope (a): {a}")
    debug_print(f"Intercept (b): {b}")
    coord_threshold_float = (RTT_THRESHOLD_MS - b) / a if a != 0 else 0
    coord_threshold_float = max(coord_threshold_float, 0)
    max_coord_dist = np.linalg.norm(max_vals - min_vals)
    coord_threshold = int((coord_threshold_float / max_coord_dist) * ((2**BITS) - 1))
else:
    debug_print("[Warning] Not enough points for regression; fallback.")
    max_rtt = max([rtt for n in node_data for rtt in n.get("rtts", {}).values()] or [100.0])
    coord_threshold = int((RTT_THRESHOLD_MS / max_rtt) * ((2**BITS) - 1))

debug_print(f"Computed coord_threshold: {coord_threshold}")

# Bounding box
query_norm_vec = norm_vec_map[QUERY_NODE_NAME]
bbox = []
debug_print(f"\nBounding box around query node normalized vec {query_norm_vec} with coord_threshold {coord_threshold}:")
for v in query_norm_vec:
    low = max(0, v - coord_threshold)
    high = min((2**BITS) - 1, v + coord_threshold)
    bbox.append((low, high))
    debug_print(f"Dim range: {low} to {high}")

# Recursive Hilbert traversal
intervals = []

def merge_intervals(intervals):
    if not intervals:
        return []
    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged

def is_fully_inside(region_min, region_max, bbox):
    for d in range(DIMENSIONS):
        if region_min[d] < bbox[d][0] or region_max[d] > bbox[d][1]:
            return False
    return True

def is_fully_outside(region_min, region_max, bbox):
    for d in range(DIMENSIONS):
        if region_max[d] < bbox[d][0] or region_min[d] > bbox[d][1]:
            return True
    return False

def region_hilbert_interval(region_min, region_max):
    h1 = hilbert.distance_from_point(region_min)
    h2 = hilbert.distance_from_point(region_max)
    return (min(h1, h2), max(h1, h2))

def hilbert_recurse(region_min, region_max, level):
    if is_fully_outside(region_min, region_max, bbox):
        return

    if is_fully_inside(region_min, region_max, bbox):
        interval = region_hilbert_interval(region_min, region_max)
        intervals.append(interval)
        return

    if level == BITS:
        from itertools import product
        ranges = [range(region_min[d], region_max[d] + 1) for d in range(DIMENSIONS)]
        for point in product(*ranges):
            h = hilbert.distance_from_point(list(point))
            intervals.append((h, h))
        return  # ✅ Only return here

    # Subdivide region
    mid = [(a + b) // 2 for a, b in zip(region_min, region_max)]
    for i in range(2 ** DIMENSIONS):
        child_min = []
        child_max = []
        for d in range(DIMENSIONS):
            if (i >> d) & 1:
                child_min.append(mid[d] + 1)
                child_max.append(region_max[d])
            else:
                child_min.append(region_min[d])
                child_max.append(mid[d])
        hilbert_recurse(child_min, child_max, level + 1)

# Launch search
hilbert_recurse([0] * DIMENSIONS, [(2**BITS) - 1] * DIMENSIONS, 0)
intervals = merge_intervals(intervals)

debug_print(f"\nMerged intervals count: {len(intervals)}")
for start, end in intervals:
    debug_print(f"Interval: {start} to {end}")

# Match nodes
candidates = set()
for name, h_index in hilbert_index_map.items():
    for start, end in intervals:
        if start <= h_index <= end:
            candidates.add(name)
            break

print(f"Candidate nodes found: {len(candidates)}")
print(f"Candidates: {sorted(candidates)}")
debug_print(f"\nCandidate nodes found: {len(candidates)}")
debug_print(f"Candidates: {sorted(candidates)}")

# Evaluate precision
false_positives = (candidates - true_match_names) - {QUERY_NODE_NAME}
false_negatives = (true_match_names - candidates) - {QUERY_NODE_NAME}

debug_print(f"\nFalse positives (count): {len(false_positives)}")
for node in sorted(false_positives):
    debug_print(node)

debug_print(f"\nFalse negatives (count): {len(false_negatives)}")
for node in sorted(false_negatives):
    debug_print(node)

print(f"\n[Query Result] Found {len(candidates)} matching nodes.\n")
print(f"Nodes within approx. {RTT_THRESHOLD_MS} ms RTT of '{QUERY_NODE_NAME}':")
for node in sorted(candidates):
    print(node)
