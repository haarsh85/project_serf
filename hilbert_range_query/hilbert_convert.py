import json
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve

# -------------------------------
# PARAMETERS
p = 2  # number of bits of precision per dimension
n = 4   # number of dimensions (from Vivaldi Vec)
input_file = "rttsfor80nodes.json"
# -------------------------------

# Load JSON data
with open(input_file, "r") as f:
    data = json.load(f)

# Extract all Vivaldi Vec coordinates
vectors = [node["coordinate"]["Vec"] for node in data]
vec_array = np.array(vectors)

# Calculate min/max per dimension
min_vals = vec_array.min(axis=0)
max_vals = vec_array.max(axis=0)

# Normalization function
def normalize_vec(vec, min_vals, max_vals, p):
    scale = (2 ** p - 1)
    return [
        int((v - min_v) / (max_v - min_v) * scale) if max_v > min_v else 0
        for v, min_v, max_v in zip(vec, min_vals, max_vals)
    ]

# Normalize all vectors
normalized_vectors = [normalize_vec(vec, min_vals, max_vals, p) for vec in vectors]

# Setup Hilbert curve
hilbert = HilbertCurve(p, n)

# Convert to Hilbert indices
hilbert_indices = hilbert.distances_from_points(normalized_vectors)

# Map node name to Hilbert index
node_to_index = {node["name"]: idx for node, idx in zip(data, hilbert_indices)}

# Output: Print first 10 for verification
for i, (name, index) in enumerate(node_to_index.items()):
    print(f"{i+1:02}. {name}: {index}")
