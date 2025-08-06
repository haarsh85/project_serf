import json
import itertools
import csv
from hilbertcurve.hilbertcurve import HilbertCurve
import math
import numpy as np
from tqdm import tqdm  # For progress bars

# === Config ===
JSON_PATH = "cluster-status-2025-07-05T12_24_59.json"
OUTPUT_CSV = "range6-result.csv"
HILBERT_ORDERS = [2, 4, 6, 8, 10]
THRESHOLDS_MS = list(range(5, 65, 5))  # ms
DIMENSIONS = 5  # Vec dimension
PERCENTILE = 95  # Percentile for radius estimation

"""
This script evaluates the effectiveness of Hilbert-curve-based hypercube range queries
on Vivaldi coordinates to approximate nearest neighbors (within RTT thresholds).

For each query node and RTT threshold, the query radius is computed as the 90th percentile
of adjusted RTT distances (Vec-distance + height + adjustment) to ground-truth neighbors.
No model is trained; radius is empirically derived. The result set is then compared to
ground truth neighbors to calculate TP, FP, FN, precision, recall, and Jaccard.

Height and Adjustment are explicitly included in the adjusted distance computation,
ensuring that the query region respects RTT semantics beyond just Euclidean Vec-space.
"""

# === Load data ===
with open(JSON_PATH) as f:
    data = json.load(f)

print(f"[DEBUG] Loaded {len(data)} nodes from {JSON_PATH}")

# Build lookup for nodes: name -> raw Vec, Height, Adjustment, RTTs
nodes_raw = {}
for node in data:
    c = node['coordinate']
    nodes_raw[node['name']] = {
        'Vec': c['Vec'],
        'Height': c['Height'],
        'Adjustment': c['Adjustment'],
        'RTTs': node['rtts']
    }

all_node_names = list(nodes_raw.keys())

# === Normalize Vec coordinates dimension-wise ===
all_vecs = np.array([info['Vec'] for info in nodes_raw.values()])
vec_min = all_vecs.min(axis=0)
vec_max = all_vecs.max(axis=0)
vec_range = np.where(vec_max - vec_min == 0, 1, vec_max - vec_min)

def normalize_vec(vec):
    return [(v - vec_min[i]) / vec_range[i] for i, v in enumerate(vec)]

# Build normalized nodes dictionary
nodes = {}
for name, info in nodes_raw.items():
    norm_vec = normalize_vec(info['Vec'])
    nodes[name] = {
        'Vec': norm_vec,
        'Height': info['Height'],
        'Adjustment': info['Adjustment'],
        'RTTs': info['RTTs']
    }

print(f"[DEBUG] Normalization complete for {len(nodes)} vectors.")

# === Helper functions ===
def clamp(v, vmin=0.0, vmax=1.0):
    return max(vmin, min(v, vmax))

def get_hypercube_bounds(vec_q, r):
    low = [clamp(v - r) for v in vec_q]
    high = [clamp(v + r) for v in vec_q]
    return low, high

def hilbert_distance_interval(low, high, hilbert_curve):
    corners = list(itertools.product(*zip(low, high)))
    max_coord = 2**hilbert_curve.p - 1
    distances = []
    for corner in corners:
        scaled_point = [int(clamp(c) * max_coord) for c in corner]
        dist = hilbert_curve.distance_from_point(scaled_point)
        distances.append(dist)
    return min(distances), max(distances)

def compute_precision_recall_jaccard(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    jaccard = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
    return precision, recall, jaccard

# === Main evaluation ===
results = []

for order in HILBERT_ORDERS:
    print(f"[PROCESSING] Hilbert order {order}")
    hilbert_curve = HilbertCurve(p=order, n=DIMENSIONS)

    max_val = 2**order - 1
    # Precompute Hilbert indices for all nodes
    node_hilbert = {}
    for name, info in nodes.items():
        scaled = [int(clamp(v) * max_val) for v in info['Vec']]
        node_hilbert[name] = hilbert_curve.distance_from_point(scaled)

    for q_node in tqdm(all_node_names, desc=f"Order {order}", unit="nodes"):
        vec_q = np.array(nodes[q_node]['Vec'])
        height_q = nodes[q_node]['Height']
        adj_q = nodes[q_node]['Adjustment']
        rtts_q = nodes[q_node]['RTTs']

        for t_ms in THRESHOLDS_MS:
            gt_nodes = [n for n, rtt in rtts_q.items() if rtt <= t_ms]
            adjusted_dists = []
            for n in gt_nodes:
                vec_i = np.array(nodes[n]['Vec'])
                height_i = nodes[n]['Height']
                adj_i = nodes[n]['Adjustment']
                vec_dist = np.linalg.norm(vec_q - vec_i)
                d = vec_dist + height_q + height_i + adj_q + adj_i
                adjusted_dists.append(d)

            r = np.percentile(adjusted_dists, PERCENTILE) if adjusted_dists else 0.0
            low, high = get_hypercube_bounds(vec_q, r)
            low_dist, high_dist = hilbert_distance_interval(low, high, hilbert_curve)

            candidates = [n for n in all_node_names if low_dist <= node_hilbert[n] <= high_dist]

            tp = len(set(candidates) & set(gt_nodes))
            fp = len(set(candidates) - set(gt_nodes))
            fn = len(set(gt_nodes) - set(candidates))
            found = len(candidates)
            gt = len(gt_nodes)

            precision, recall, jaccard = compute_precision_recall_jaccard(tp, fp, fn)

            results.append({
                'hilbert_order': order,
                'q_node': q_node,
                't': t_ms,
                'gt': gt,
                'found': found,
                'tp': tp,
                'fp': fp,
                'fn': fn,
                'precision': precision,
                'recall': recall,
                'jaccard': jaccard
            })

# Write results CSV
with open(OUTPUT_CSV, 'w', newline='') as csvfile:
    fieldnames = ['hilbert_order', 'q_node', 't', 'gt', 'found', 'tp', 'fp', 'fn', 'precision', 'recall', 'jaccard']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for row in results:
        writer.writerow(row)

print(f"Done. Results saved to {OUTPUT_CSV}")
