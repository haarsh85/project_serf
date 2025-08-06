import json
import csv
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve
from bisect import bisect_left, bisect_right
from tqdm import tqdm

INPUT_FILE = "cluster-status-2025-07-05T12_24_59.json"
OUTPUT_CSV = "range7-old-scaling-result.csv"
dimensions = 5
hilbert_orders = [2, 4, 6, 8, 10]
thresh_ms = list(range(5, 65, 5))

def load_nodes(filepath):
    with open(filepath) as f:
        nodes = json.load(f)
    return {n['name']: n for n in nodes}

def normalize_fn(nodes):
    vecs = np.array([n['coordinate']['Vec'] for n in nodes.values()])
    min_vals, max_vals = vecs.min(axis=0), vecs.max(axis=0)
    def norm(v):
        return ((np.array(v) - min_vals) / (max_vals - min_vals + 1e-9)).clip(0, 1)
    return norm

def get_ground_truth(node, T):
    return {n for n, rtt in node['rtts'].items() if rtt <= T}

def compute_query_bounds(norm_vec, T, vecs, norm_fn, scale=1.0):
    dim_diffs = [[] for _ in range(dimensions)]
    for v in vecs:
        v_norm = norm_fn(v)
        for d in range(dimensions):
            dim_diffs[d].append(abs(norm_vec[d] - v_norm[d]))
    radius = [np.percentile(dim_diffs[d], 99) for d in range(dimensions)]
    
    # Apply scaling factor to expand the radius
    radius = [r * scale for r in radius]

    low = np.maximum(0.0, norm_vec - radius)
    high = np.minimum(1.0, norm_vec + radius)
    bounds = list(zip(low, high))
    return bounds


def key_within_bounds(key_point, bounds):
    return all(bounds[d][0] <= key_point[d] <= bounds[d][1] for d in range(dimensions))

# def hilbert_query(query_key, bounds, curve, sorted_keys_map):
#     found = set()
#     for name, key, point in sorted_keys_map:
#         p_norm = [x / (2**curve.p - 1) for x in point]
#         if key >= query_key and key_within_bounds(p_norm, bounds):
#             found.add(name)
#     return found

def hilbert_query(query_key, bounds, curve, sorted_keys_map):
    found = set()
    max_key = 2**(curve.p * curve.n) - 1  # total number of hilbert keys
    p = 2 ** curve.p

    # Extract just the keys
    keys = [key for _, key, _ in sorted_keys_map]
    pos = bisect_left(keys, query_key)

    # === Search LEFT (lower keys) ===
    for i in range(pos - 1, -1, -1):
        name, key, int_point = sorted_keys_map[i]
        norm_point = [x / (p - 1) for x in int_point]
        if not key_within_bounds(norm_point, bounds):
            break  # stop early — no longer within bounding box
        found.add(name)

    # === Search RIGHT (higher keys) ===
    for i in range(pos, len(sorted_keys_map)):
        name, key, int_point = sorted_keys_map[i]
        norm_point = [x / (p - 1) for x in int_point]
        if not key_within_bounds(norm_point, bounds):
            break  # stop early — no longer within bounding box
        found.add(name)

    return found


def run():
    nodes = load_nodes(INPUT_FILE)
    norm_fn = normalize_fn(nodes)
    scale_values = [1.5]

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["hilbert_order", "q_node", "t", "scale", "gt", "found", "tp", "fp", "fn", "precision", "recall", "jaccard"])

        for order in hilbert_orders:
            curve = HilbertCurve(order, dimensions)
            p = 2**order
            sorted_keys_map = []

            for name, node in nodes.items():
                norm_vec = norm_fn(node['coordinate']['Vec'])
                int_point = [int(x * (p - 1)) for x in norm_vec]
                key = curve.distance_from_point(int_point)
                sorted_keys_map.append((name, key, int_point))

            sorted_keys_map.sort(key=lambda x: x[1])

            for q_name in tqdm(nodes.keys(), desc=f"Order {order}"):
                q_node = nodes[q_name]
                q_vec = norm_fn(q_node['coordinate']['Vec'])
                q_int = [int(x * (p - 1)) for x in q_vec]
                q_key = curve.distance_from_point(q_int)

                for T in thresh_ms:
                    gt = get_ground_truth(q_node, T)
                    if not gt:
                        for scale in scale_values:
                            writer.writerow([order, q_name, T, scale, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0])
                        continue

                    gt_vecs = [nodes[n]['coordinate']['Vec'] for n in gt if n in nodes]
                    for scale in scale_values:
                        bounds = compute_query_bounds(q_vec, T, gt_vecs, norm_fn, scale=scale)
                        found = hilbert_query(q_key, bounds, curve, sorted_keys_map)
                        found.discard(q_name)

                        tp = len(gt & found)
                        fp = len(found - gt)
                        fn = len(gt - found)
                        prec = tp / (tp + fp) if (tp + fp) else 0
                        rec = tp / (tp + fn) if (tp + fn) else 0
                        jac = tp / (tp + fp + fn) if (tp + fp + fn) else 0
                        writer.writerow([order, q_name, T, scale, len(gt), len(found), tp, fp, fn, prec, rec, jac])

    print(f"[✓] Results written to {OUTPUT_CSV}")

if __name__ == "__main__":
    run()
