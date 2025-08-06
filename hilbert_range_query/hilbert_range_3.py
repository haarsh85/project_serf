import json
from hilbertcurve.hilbertcurve import HilbertCurve
import sys

# === REDIRECT PRINT OUTPUT TO FILE ===
sys.stdout = open("no-rtt-hr-3.txt", "w")

# === CONFIGURATION ===
BITS = 7  # Hilbert precision: number of bits per dimension (2^BITS discrete steps)
DIMENSIONS = 5  # Number of dimensions of the Vivaldi coordinate system
INPUT_FILE = "cluster-status-2025-07-05T12_24_59.json"  # JSON input file with node data

# === LOAD SERF NODE DATA ===
print("Loading input data...")
with open(INPUT_FILE, "r") as f:
    serf_data = json.load(f)

# Extract Vivaldi Vec coordinates from each node
vecs = [node["coordinate"]["Vec"] for node in serf_data]

# ✅ Extract RTT values from "rtts" dict inside each node
rtt_values = []
for node in serf_data:
    rtt_values.extend(node.get("rtts", {}).values())

# ✅ Use max RTT across all pairwise RTTs
max_rtt_in_dataset = max(rtt_values) if rtt_values else 500  # fallback only if empty
print(f"\n=== Max RTT found in dataset: {max_rtt_in_dataset:.4f} ms ===")

# === Step 1: Normalize Vivaldi Coordinates ===
min_vals = [min(dim) for dim in zip(*vecs)]
max_vals = [max(dim) for dim in zip(*vecs)]

print("\n=== Step 1: Normalization Range per Dimension ===")
for i in range(DIMENSIONS):
    print(f"Dimension {i}: min = {min_vals[i]:.4f}, max = {max_vals[i]:.4f}")

def normalize_vec(vec):
    """Normalize a vector into integer coordinates [0, 2^BITS -1] per dimension."""
    scale = (2 ** BITS - 1)
    return [
        int((v - min_v) / (max_v - min_v) * scale) if max_v > min_v else 0
        for v, min_v, max_v in zip(vec, min_vals, max_vals)
    ]

# === Step 2: Build Hilbert Index Map ===
print("\n=== Step 2: Building Hilbert Index Map ===")
hilbert = HilbertCurve(p=BITS, n=DIMENSIONS)
hilbert_index_map = {}  # node_name -> hilbert index
norm_vec_map = {}       # node_name -> normalized vector

for node in serf_data:
    name = node["name"]
    vec = node["coordinate"]["Vec"]
    norm_vec = normalize_vec(vec)
    h_index = hilbert.distance_from_point(norm_vec)

    hilbert_index_map[name] = h_index
    norm_vec_map[name] = norm_vec
    print(f"[Hilbert] {name} -> Vec: {vec}, NormVec: {norm_vec}, Index: {h_index}")

# === Step 3: RTT -> Coordinate Threshold ===
def rtt_to_coord_threshold(rtt_threshold_ms):
    """Map RTT threshold to coordinate threshold (0..max_coord scale)."""
    max_coord = (2 ** BITS) - 1
    coord_threshold = int((rtt_threshold_ms / max_rtt_in_dataset) * max_coord)
    print(f"\n[Mapping RTT to Coord] RTT threshold {rtt_threshold_ms} ms -> Coord threshold {coord_threshold}")
    return coord_threshold

# === Step 4: Bounding Box Around Query Node ===
def build_bounding_box(norm_vec, coord_threshold):
    bbox = [
        (
            max(0, int(v - coord_threshold)),
            min((2 ** BITS) - 1, int(v + coord_threshold))
        )
        for v in norm_vec
    ]
    print(f"\n[Bounding Box] Around normalized vector {norm_vec} with threshold {coord_threshold}:")
    for i, (low, high) in enumerate(bbox):
        print(f"  Dim {i}: {low} to {high}")
    return bbox

# === Step 5: Recursive Hilbert Interval Computation ===
def bounding_box_to_intervals(hilbert, bbox, depth=BITS):
    intervals = []

    def recurse(region_min, region_max, level):
        if level == depth:
            coord = [int((a + b) / 2) for a, b in zip(region_min, region_max)]
            h = hilbert.distance_from_point(coord)
            intervals.append((h, h))
            return

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

            intersect = True
            for d in range(DIMENSIONS):
                bmin, bmax = bbox[d]
                if child_max[d] < bmin or child_min[d] > bmax:
                    intersect = False
                    break

            if intersect:
                recurse(child_min, child_max, level + 1)

    print("\n[Hilbert Interval Search] Recursing to compute intervals...")
    recurse([0] * DIMENSIONS, [(2 ** BITS) - 1] * DIMENSIONS, 0)
    return merge_intervals(intervals)

# === Step 6: Merge Overlapping Intervals ===
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
    print(f"\n[Intervals] {len(merged)} merged intervals from {len(intervals)} raw intervals.")
    return merged

# === Step 7: Range Query ===
def range_query(query_node, rtt_threshold_ms):
    print(f"\n=== Step 3: Running Range Query from '{query_node}' with RTT threshold {rtt_threshold_ms} ms ===")
    norm_vec = norm_vec_map[query_node]

    coord_threshold = rtt_to_coord_threshold(rtt_threshold_ms)
    bbox = build_bounding_box(norm_vec, coord_threshold)
    intervals = bounding_box_to_intervals(hilbert, bbox)

    print("\n[Intervals Used]")
    for start, end in intervals:
        print(f"  Interval: [{start}, {end}]")

    result = []
    for name, hval in hilbert_index_map.items():
        for start, end in intervals:
            if start <= hval <= end:
                result.append(name)
                break

    print(f"\n[Query Result] Found {len(result)} matching nodes.")
    print(f"\nNodes within approx. {rtt_threshold_ms:.4f} ms RTT of '{query_node}':")
    for node in sorted(result):
        print(f"- {node}")

    # === ADDED: True RTT Matches and FPs/FNs ===
    node_map = {n["name"]: n for n in serf_data}
    query_rtts = node_map[query_node].get("rtts", {})
    true_matches = {name for name, rtt in query_rtts.items() if rtt <= rtt_threshold_ms}

    print(f"\n[True RTT Matches for {query_node} <= {rtt_threshold_ms} ms]")
    print(f"Count: {len(true_matches)}")
    print(f"Nodes: {sorted(true_matches)}")

    predicted = set(result)
    false_positives = predicted - true_matches - {query_node}
    false_negatives = true_matches - predicted - {query_node}

    print(f"\nFalse Positives ({len(false_positives)}):")
    for name in sorted(false_positives):
        print(name)

    print(f"\nFalse Negatives ({len(false_negatives)}):")
    for name in sorted(false_negatives):
        print(name)

# === TEST RANGE QUERY ===
print("\n=== Step 4: Range Query Test ===")
test_rtt_threshold = 10  # in milliseconds
query_node = "clab-nebula-serf1"
range_query(query_node, rtt_threshold_ms=test_rtt_threshold)
