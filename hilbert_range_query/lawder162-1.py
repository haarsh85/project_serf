import json
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve

# === Configuration ===
BITS = 7  # Bits per dimension for Hilbert curve (total range: 0–127)
DIMENSIONS = 5  # Vivaldi coordinates are 5D
RTT_THRESHOLD_MS = 20 # Change this to test different RTT query thresholds
QUERY_NODE_NAME = "clab-nebula-serf1"
INPUT_FILE = "cluster-status-2025-07-05T12_24_59.json"
DEBUG_LOG = "lawder162-1.txt"

# === Helper: Debug print to log file ===
def debug_print(*args, **kwargs):
    with open(DEBUG_LOG, "a") as f:
        print(*args, **kwargs, file=f)

# Clear previous debug log
open(DEBUG_LOG, "w").close()

# === Load cluster node data ===
with open(INPUT_FILE, "r") as f:
    node_data = json.load(f)

nodes = [n["name"] for n in node_data]
node_map = {n["name"]: n for n in node_data}
vecs = [n["coordinate"]["Vec"] for n in node_data]

# === Compute min/max per dimension for normalization ===
min_vals = np.min(vecs, axis=0)
max_vals = np.max(vecs, axis=0)
debug_print("[Min/Max per dimension]")
for i in range(DIMENSIONS):
    debug_print(f"Dim {i}: min={min_vals[i]}, max={max_vals[i]}")

# === Normalize a vector into Hilbert space ===
def normalize_vec(vec):
    scale = (2**BITS - 1)
    norm = [
        int((v - min_v) / (max_v - min_v) * scale) if max_v > min_v else 0
        for v, min_v, max_v in zip(vec, min_vals, max_vals)
    ]
    return norm

# === Build Hilbert indices for all nodes ===
hilbert = HilbertCurve(p=BITS, n=DIMENSIONS)
norm_vec_map = {}
hilbert_index_map = {}

debug_print("\nHilbert Mappings")
for n in node_data:
    name = n["name"]
    vec = n["coordinate"]["Vec"]
    norm_vec = normalize_vec(vec)
    h_index = hilbert.distance_from_point(norm_vec)
    norm_vec_map[name] = norm_vec
    hilbert_index_map[name] = h_index
    debug_print(f"Node: {name}"+f"  Vec: {vec}"+f"  Normalized: {norm_vec}"+f"  HilbertIdx: {h_index}")

# === Get RTT ground truth matches for the query node ===
query_node = node_map[QUERY_NODE_NAME]
rtt_matches = {name: rtt for name, rtt in query_node.get("rtts", {}).items() if rtt <= RTT_THRESHOLD_MS}
true_match_names = set(rtt_matches.keys())
debug_print(f"\n[True RTT Matches for {QUERY_NODE_NAME} <= {RTT_THRESHOLD_MS} ms]")
debug_print(f"Count: {len(true_match_names)}")
debug_print(f"Nodes: {sorted(true_match_names)}")

# === Estimate coordinate threshold from RTTs ===
query_vec = np.array(query_node["coordinate"]["Vec"])
all_pairs = []
for other_name, rtt in query_node.get("rtts", {}).items():
    if other_name in node_map:
        other_vec = np.array(node_map[other_name]["coordinate"]["Vec"])
        dist = np.linalg.norm(other_vec - query_vec)
        all_pairs.append((rtt, dist))

all_pairs.sort()
closest = [dist for rtt, dist in all_pairs if rtt <= RTT_THRESHOLD_MS]

# === Handle cases with no nearby RTTs ===
skip_query = False
if not closest:
    coord_threshold = 0
    query_norm_vec = norm_vec_map[QUERY_NODE_NAME]
    bbox = [(v, v) for v in query_norm_vec]  # Box includes only query point
    skip_query = True
    debug_print("\nNo RTT matches under threshold — returning empty bounding box.")
else:
    # Use a robust threshold: 90th percentile of actual close neighbors
    coord_dist_limit = np.percentile(closest, 95)
    # coord_dist_limit = max(closest)

    # Normalize this distance into [0, 127] coordinate space
    max_coord_dist = np.linalg.norm(max_vals - min_vals)
    coord_threshold = int((coord_dist_limit / max_coord_dist) * ((2**BITS) - 1))

    debug_print(f"\n[Threshold Estimation]")
    debug_print(f"coord_dist_limit: {coord_dist_limit}")
    debug_print(f"Computed coord_threshold: {coord_threshold}")

    # === Build bounding box with padding (padding varies with RTT) ===
    if RTT_THRESHOLD_MS <= 10:
        padding_ratio = 0.25
    elif RTT_THRESHOLD_MS <= 30:
        padding_ratio = 0.15
    else:
        padding_ratio = 0.15

    PADDING = int(coord_threshold * padding_ratio)

    query_norm_vec = norm_vec_map[QUERY_NODE_NAME]
    bbox = []
    debug_print(f"\nBounding box around query node normalized vec {query_norm_vec} with coord_threshold {coord_threshold} and padding {PADDING}:")
    for i, v in enumerate(query_norm_vec):
        low = max(0, v - coord_threshold - PADDING)
        high = min((2**BITS) - 1, v + coord_threshold + PADDING)
        bbox.append((low, high))
        debug_print(f"Dim {i} range: {low} to {high}")

# === Recursive Hilbert traversal to get index intervals ===
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
    return all(region_min[d] >= bbox[d][0] and region_max[d] <= bbox[d][1] for d in range(DIMENSIONS))

def is_fully_outside(region_min, region_max, bbox):
    return any(region_max[d] < bbox[d][0] or region_min[d] > bbox[d][1] for d in range(DIMENSIONS))

def region_hilbert_interval(region_min, region_max):
    h1 = hilbert.distance_from_point(region_min)
    h2 = hilbert.distance_from_point(region_max)
    return (min(h1, h2), max(h1, h2))

def hilbert_recurse(region_min, region_max, level):
    if is_fully_outside(region_min, region_max, bbox):
        return
    if is_fully_inside(region_min, region_max, bbox):
        intervals.append(region_hilbert_interval(region_min, region_max))
        return
    if level >= BITS - 2:  # stop early to reduce complexity
        intervals.append(region_hilbert_interval(region_min, region_max))
        return

    mid = [(a + b) // 2 for a, b in zip(region_min, region_max)]
    for i in range(2 ** DIMENSIONS):
        child_min, child_max = [], []
        for d in range(DIMENSIONS):
            if (i >> d) & 1:
                child_min.append(mid[d] + 1)
                child_max.append(region_max[d])
            else:
                child_min.append(region_min[d])
                child_max.append(mid[d])
        hilbert_recurse(child_min, child_max, level + 1)

# Run query unless we know there are no matches
if not skip_query:
    hilbert_recurse([0] * DIMENSIONS, [(2**BITS) - 1] * DIMENSIONS, 0)

intervals = merge_intervals(intervals)
debug_print(f"\nMerged intervals count: {len(intervals)}")
# for start, end in intervals:
#     debug_print(f"Interval: {start} to {end}")

# === Match candidate nodes by Hilbert index ===
candidates = set()
for name, h_index in hilbert_index_map.items():
    for start, end in intervals:
        if start <= h_index <= end:
            candidates.add(name)
            break

# Remove query node from result
candidates.discard(QUERY_NODE_NAME)

# === Print results ===
print(f"\n[Query Result]")
print(f"RTT Threshold: {RTT_THRESHOLD_MS} ms")
print(f"Found {len(candidates)} candidate nodes:")
for node in sorted(candidates):
    print(node)

# Also log to file
debug_print(f"\n[Query Result]")
debug_print(f"RTT Threshold: {RTT_THRESHOLD_MS} ms")
debug_print(f"Found {len(candidates)} candidate nodes:")
for node in sorted(candidates):
    debug_print(node)

# === Evaluate precision ===
false_positives = candidates - true_match_names
false_negatives = true_match_names - candidates

debug_print(f"\nFalse Positives ({len(false_positives)}): {sorted(false_positives)}")
debug_print(f"False Negatives ({len(false_negatives)}): {sorted(false_negatives)}")

print(f"\nFalse Positives: {len(false_positives)}")
print(f"False Negatives: {len(false_negatives)}")

true_positives = len(candidates & true_match_names)
false_positives = len(candidates - true_match_names)
false_negatives = len(true_match_names - candidates)

precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else 0
recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else 0
jaccard = true_positives / (true_positives + false_positives + false_negatives) if (true_positives + false_positives + false_negatives) else 0

print(f"\n=== Evaluation Metrics ===")
print(f"Precision: {precision:.4f}")
print(f"Recall: {recall:.4f}")
print(f"Jaccard Index: {jaccard:.4f}")

debug_print(f"\n=== Evaluation Metrics ===")
debug_print(f"Precision: {precision:.4f}")
debug_print(f"Recall: {recall:.4f}")
debug_print(f"Jaccard Index: {jaccard:.4f}")
