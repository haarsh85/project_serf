import json
from hilbertcurve.hilbertcurve import HilbertCurve

# === CONFIG ===
BITS = 7
DIMENSIONS = 4
INPUT_FILE = "rttsfor80nodes.txt"

# === LOAD DATA ===
with open(INPUT_FILE, "r") as f:
    serf_data = json.load(f)

vecs = [node["coordinate"]["Vec"] for node in serf_data]

# === NORMALIZATION RANGES ===
min_vals = [min(dim) for dim in zip(*vecs)]
max_vals = [max(dim) for dim in zip(*vecs)]

def normalize_vec(vec):
    scale = (2 ** BITS - 1)
    return [
        int((v - min_v) / (max_v - min_v) * scale) if max_v > min_v else 0
        for v, min_v, max_v in zip(vec, min_vals, max_vals)
    ]

def denormalize_vec(norm_vec):
    scale = (2 ** BITS - 1)
    return [
        (v / scale) * (max_v - min_v) + min_v
        for v, min_v, max_v in zip(norm_vec, min_vals, max_vals)
    ]

# === INIT HILBERT CURVE ===
hilbert = HilbertCurve(p=BITS, n=DIMENSIONS)

# === ROUND-TRIP VERBOSE CHECK ===
failures = 0
for node in serf_data:
    name = node["name"]
    original_vec = node["coordinate"]["Vec"]
    norm_vec = normalize_vec(original_vec)
    hilbert_index = hilbert.distance_from_point(norm_vec)
    decoded_vec = hilbert.point_from_distance(hilbert_index)
    decoded_floats = denormalize_vec(decoded_vec)

    print(f"\n=== {name} ===")
    print(f"Original Vec      : {original_vec}")
    print(f"Normalized Vec    : {norm_vec}")
    print(f"Hilbert Index     : {hilbert_index}")
    print(f"Decoded Vec       : {decoded_vec}")
    print(f"Denormalized Vec  : {decoded_floats}")

    if norm_vec != decoded_vec:
        failures += 1
        print("❌ MISMATCH in normalized space")

if failures == 0:
    print("\n✅ All vectors round-trip correctly through Hilbert encoding/decoding.")
else:
    print(f"\n❌ {failures} mismatches found in Hilbert round-trip.")
