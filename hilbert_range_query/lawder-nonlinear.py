import json
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline

# === CONFIGURATION ===
BITS = 7
DIMENSIONS = 4
RTT_THRESHOLD_MS = 20
QUERY_NODE_NAME = "clab-century-serf1"
INPUT_FILE = "rttsfor80nodes.txt"
DEBUG_LOG = "lawder-nonlinear-poly.txt"

def debug_log(*args):
    with open(DEBUG_LOG, "a") as f:
        print(*args, file=f)

# === PREP ===
open(DEBUG_LOG, "w").close()  # Clear log

# === Load Input ===
with open(INPUT_FILE, "r") as f:
    node_data = json.load(f)

node_map = {n["name"]: n for n in node_data}
vecs = [n["coordinate"]["Vec"] for n in node_data]

# === Compute Min/Max for Normalization ===
min_vals = np.min(vecs, axis=0)
max_vals = np.max(vecs, axis=0)

def normalize_vec(vec):
    scale = (2**BITS - 1)
    return [
        int((v - min_v) / (max_v - min_v) * scale) if max_v > min_v else 0
        for v, min_v, max_v in zip(vec, min_vals, max_vals)
    ]

hilbert = HilbertCurve(p=BITS, n=DIMENSIONS)

norm_vec_map = {}
hilbert_index_map = {}
for n in node_data:
    name = n["name"]
    vec = n["coordinate"]["Vec"]
    norm_vec = normalize_vec(vec)
    h_index = hilbert.distance_from_point(norm_vec)
    norm_vec_map[name] = norm_vec
    hilbert_index_map[name] = h_index

# === Get True RTT Matches ===
query_node = node_map[QUERY_NODE_NAME]
true_matches = {
    name for name, rtt in query_node.get("rtts", {}).items()
    if rtt <= RTT_THRESHOLD_MS
}

# === Euclidean Distances and RTTs for Regression ===
query_vec = np.array(query_node["coordinate"]["Vec"])
eucl_dists, rtts = [], []

for name, rtt in query_node.get("rtts", {}).items():
    if name in node_map:
        other_vec = np.array(node_map[name]["coordinate"]["Vec"])
        dist = np.linalg.norm(query_vec - other_vec)
        eucl_dists.append(dist)
        rtts.append(rtt)

# === Polynomial Regression: RTT ≈ a*x^2 + b*x + c ===
use_poly = True
if len(eucl_dists) >= 3:
    X = np.array(eucl_dists).reshape(-1, 1)
    y = np.array(rtts)

    # Use degree-2 polynomial regression
    model = make_pipeline(PolynomialFeatures(degree=2), LinearRegression())
    model.fit(X, y)

    # Predict coordinate distance for target RTT threshold
    pred = model.named_steps["linearregression"]
    poly = model.named_steps["polynomialfeatures"]
    coeffs = pred.coef_
    intercept = pred.intercept_

    debug_log("[Polynomial Regression Coefficients]")
    debug_log(f"Intercept = {intercept}")
    debug_log(f"Coefs = {coeffs.tolist()}")

    # Solve a·x² + b·x + c = RTT_THRESHOLD_MS
    a = coeffs[2] if len(coeffs) > 2 else 0
    b = coeffs[1] if len(coeffs) > 1 else 0
    c = intercept - RTT_THRESHOLD_MS

    roots = np.roots([a, b, c]) if a != 0 else [-c / b]
    coord_dist = max([r.real for r in roots if r.imag == 0 and r.real >= 0], default=0)
else:
    debug_log("[Fallback to linear mapping]")
    coord_dist = RTT_THRESHOLD_MS / max(rtts) * np.linalg.norm(max_vals - min_vals)

debug_log(f"Predicted max Euclidean distance for RTT ≤ {RTT_THRESHOLD_MS} ms: {coord_dist}")

# === Convert to Coordinate Threshold (Normalized) ===
max_coord_dist = np.linalg.norm(max_vals - min_vals)
coord_threshold = int((coord_dist / max_coord_dist) * ((2**BITS) - 1))
debug_log(f"Final coord_threshold = {coord_threshold}")

# === Build Bounding Box ===
query_norm_vec = norm_vec_map[QUERY_NODE_NAME]
bbox = []
for v in query_norm_vec:
    low = max(0, v - coord_threshold)
    high = min((2**BITS) - 1, v + coord_threshold)
    bbox.append((low, high))
    debug_log(f"Dim range: {low} to {high}")

# === Recursive Hilbert Range Search ===
intervals = []

def merge_intervals(intervals):
    if not intervals:
        return []
    intervals.sort()
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e + 1:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))
    return merged

def is_inside(min_r, max_r, bbox):
    return all(min_r[d] >= bbox[d][0] and max_r[d] <= bbox[d][1] for d in range(DIMENSIONS))

def is_outside(min_r, max_r, bbox):
    return any(max_r[d] < bbox[d][0] or min_r[d] > bbox[d][1] for d in range(DIMENSIONS))

def hilbert_recurse(min_r, max_r, level):
    if is_outside(min_r, max_r, bbox):
        return
    if is_inside(min_r, max_r, bbox):
        h1 = hilbert.distance_from_point(min_r)
        h2 = hilbert.distance_from_point(max_r)
        intervals.append((min(h1, h2), max(h1, h2)))
        return
    if level == BITS:
        mid = [(a + b) // 2 for a, b in zip(min_r, max_r)]
        h = hilbert.distance_from_point(mid)
        intervals.append((h, h))
        return

    mid = [(a + b) // 2 for a, b in zip(min_r, max_r)]
    for i in range(2**DIMENSIONS):
        child_min = []
        child_max = []
        for d in range(DIMENSIONS):
            if (i >> d) & 1:
                child_min.append(mid[d] + 1)
                child_max.append(max_r[d])
            else:
                child_min.append(min_r[d])
                child_max.append(mid[d])
        hilbert_recurse(child_min, child_max, level + 1)

hilbert_recurse([0]*DIMENSIONS, [(2**BITS)-1]*DIMENSIONS, 0)
intervals = merge_intervals(intervals)

# === Candidate Nodes by Hilbert Index Range ===
candidates = set()
for name, h_index in hilbert_index_map.items():
    for s, e in intervals:
        if s <= h_index <= e:
            candidates.add(name)
            break

# === Evaluate Results ===
fp = (candidates - true_matches) - {QUERY_NODE_NAME}
fn = (true_matches - candidates) - {QUERY_NODE_NAME}

print(f"\n[Query Result] Nodes found: {len(candidates)}")
print(f"False Positives ({len(fp)}): {sorted(fp)}")
print(f"False Negatives ({len(fn)}): {sorted(fn)}")
