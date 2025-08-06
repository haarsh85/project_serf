import json
import csv
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve
from tqdm import tqdm

# ==== CONFIGURATION ====
INPUT_FILE = "cluster-status-2025-07-05T12_24_59.json"
OUTPUT_CSV = "zxgpt.csv"
hilbert_orders = [2, 4, 6, 8, 10, 12, 14, 16]  # Configurable Hilbert curve orders (resolution)
thresholds = list(range(5, 65, 5))  # RTT thresholds in ms
query_nodes = ["clab-nebula-serf1"] + [f"clab-nebula-serf{i}" for i in range(5, 161, 5)]  # None to include all nodes

# ==== Load and preprocess data ====
with open(INPUT_FILE) as f:
    nodes = json.load(f)

node_map = {node["name"]: node for node in nodes}
all_names = list(node_map.keys())

if query_nodes is None:
    query_nodes = all_names

vecs = np.array([node["coordinate"]["Vec"] for node in nodes])
dim = vecs.shape[1]
min_vec = vecs.min(axis=0)
max_vec = vecs.max(axis=0)

# Determine worst-case (Height + Adjustment) across all nodes (in seconds)
max_hplusa = max(
    node["coordinate"].get("Height", 0) + node["coordinate"].get("Adjustment", 0)
    for node in nodes
)

def normalize_vec(vec, p):
    """
    Normalize a vector to integer coordinates in [0, 2^p -1]^dim.
    This scales the original Vec coordinates into discrete integer grid.
    """
    max_val = (2 ** p) - 1
    vec = np.array(vec)
    normed = (vec - min_vec) / (max_vec - min_vec + 1e-9)
    return np.round(normed * max_val).astype(int).tolist()

results = []

for p in hilbert_orders:
    hilbert = HilbertCurve(p, dim)

    # Precompute Hilbert indices for all nodes at this order
    name_to_hindex = {}
    for node in nodes:
        vec_int = normalize_vec(node["coordinate"]["Vec"], p)
        hindex = hilbert.distance_from_point(vec_int)
        name_to_hindex[node["name"]] = hindex

    max_hilbert_index = 2 ** (p * dim) - 1  # Max Hilbert index at order p

    for qname in tqdm(query_nodes, desc=f"Order p={p}"):
        qnode = node_map[qname]
        qcoord = qnode["coordinate"]
        hq = name_to_hindex[qname]

        # Ground-truth RTT distances from qnode to all others
        rtt_map = {}
        for other_name in all_names:
            if other_name == qname:
                continue
            measured_rtt = qnode.get("rtts", {}).get(other_name, None)
            if measured_rtt is None:
                measured_rtt = float('inf')
            rtt_map[other_name] = measured_rtt


        for T in thresholds:
            ground_truth = {n for n, rtt in rtt_map.items() if rtt <= T}
            gt_count = len(ground_truth)

            # Step 1: Compute Euclidean radius R in Vec-space (seconds),
            # adjusted by query node's Height/Adjustment and worst-case max_hplusa
            R = max((T / 1000.0) - qcoord.get("Height", 0) - qcoord.get("Adjustment", 0) - max_hplusa, 0)

            # Step 2: Normalize R to [0,1] scale in coordinate space by max_vec-min_vec
            # because normalize_vec scales coordinates into [0, max_val].
            # This converts a radius in Vec units into normalized unit cube scale
            normalized_radii = R / (max_vec - min_vec + 1e-9)  # per dimension vector

            # Step 3: Approximate Hilbert index radius:
            # Hilbert curve maps a point in dim-dimensional space to 1D, but
            # distance on the Hilbert curve is not Euclidean distance.
            # We approximate radius in Hilbert index space by considering max norm dimension,
            # multiplied by the maximum Hilbert index in one dimension.

            # Convert normalized radius vector to max dimension component:
            r_norm = np.linalg.norm(normalized_radii)  # worst dimension normalized radius

            # Convert normalized radius to Hilbert index radius:
            # max coordinate in one dimension = 2^p -1
            hilbert_radius = int(np.ceil(r_norm * max_hilbert_index))

            # Step 4: Query nodes by Hilbert distance within hilbert_radius of hq.
            # Naive linear scan: compute Hilbert distance from hq to each node's hindex
            # and select those with distance ≤ hilbert_radius.
            # This avoids Euclidean distance filtering altogether, so Hilbert index is primary.

            found_set = set()
            for name, hidx in name_to_hindex.items():
                if name == qname:
                    continue
                dist = abs(hidx - hq)  # Hilbert distance is 1D absolute difference
                if dist <= hilbert_radius:
                    found_set.add(name)

            TP = len(found_set & ground_truth)
            FP = len(found_set - ground_truth)
            FN = len(ground_truth - found_set)

            precision = TP / (TP + FP) if (TP + FP) > 0 else (1.0 if TP + FP + FN == 0 else 0.0)
            recall    = TP / (TP + FN) if (TP + FN) > 0 else (1.0 if TP + FP + FN == 0 else 0.0)
            jaccard   = TP / (TP + FP + FN) if (TP + FP + FN) > 0 else 1.0

            results.append([
                p, qname, T, gt_count, len(found_set), TP, FP, FN,
                f"{precision:.4f}", f"{recall:.4f}", f"{jaccard:.4f}"
            ])

            print(f"[ORDER={p}] Node={qname} Threshold={T}ms → GT={gt_count} Found={len(found_set)} "
                  f"TP={TP} FP={FP} FN={FN} Precision={precision:.4f} Recall={recall:.4f} Jaccard={jaccard:.4f}")

# Write results to CSV
header = ["hilbert_order", "q_node", "threshold", "gt", "found", "tp", "fp", "fn", "precision", "recall", "jaccard"]
with open(OUTPUT_CSV, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(results)

print(f"\nSaved results to: {OUTPUT_CSV}")
