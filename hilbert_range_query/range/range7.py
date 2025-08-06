import json
import csv
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve
from bisect import bisect_left
import tqdm

INPUT_FILE = "cluster-status-2025-07-05T12_24_59.json"
OUTPUT_CSV = "range7-result.csv"
thresh_ms = list(range(5, 65, 5))

def load_nodes(filepath):
    with open(filepath) as f:
        nodes = json.load(f)
    return {n['name']: n for n in nodes}

def normalize_fn_6d(nodes):
    vecs = []
    for node in nodes.values():
        coord = node['coordinate']
        vec = coord['Vec'] + [coord['Height']]
        vecs.append(vec)
    vecs = np.array(vecs)
    min_vals = vecs.min(axis=0)
    max_vals = vecs.max(axis=0)
    ranges = max_vals - min_vals
    ranges[ranges == 0] = 1e-9  # Avoid division by zero
    
    def norm(v):
        v_arr = np.array(v)
        normalized = (v_arr - min_vals) / ranges
        return np.clip(normalized, 0, 1)
    
    return norm

def compute_global_distance_model(nodes, norm_fn, dimensions):
    pairs = []
    node_items = list(nodes.items())
    
    for name, node in tqdm.tqdm(node_items, desc="Building distance model"):
        v1 = norm_fn(node['coordinate']['Vec'] + [node['coordinate']['Height']])
        for neighbor, rtt in node['rtts'].items():
            if neighbor in nodes:
                n_node = nodes[neighbor]
                v2 = norm_fn(n_node['coordinate']['Vec'] + [n_node['coordinate']['Height']])
                dist = np.linalg.norm(v1 - v2)
                pairs.append((dist, rtt))
    
    d_max_model = {}
    for T in thresh_ms:
        valid_dists = [dist for dist, rtt in pairs if rtt <= T]
        if not valid_dists:
            d_max_model[T] = 0.0
        else:
            d_max_model[T] = np.percentile(valid_dists, 95)
    return d_max_model

def get_ground_truth(node, T):
    return {n for n, rtt in node['rtts'].items() if rtt <= T}

def key_within_bounds(key_point, bounds):
    return all(bounds[d][0] <= key_point[d] <= bounds[d][1] for d in range(len(bounds)))

def hilbert_query(query_key, bounds, curve, sorted_keys_map):
    found = set()
    p = 2 ** curve.p
    keys = [k for _, k, _ in sorted_keys_map]
    pos = bisect_left(keys, query_key)
    
    # Search left (lower keys)
    for i in range(pos - 1, -1, -1):
        name, key, int_point = sorted_keys_map[i]
        norm_point = [x / (p - 1) for x in int_point]
        if not key_within_bounds(norm_point, bounds):
            break
        found.add(name)
    
    # Search right (higher keys)
    for i in range(pos, len(sorted_keys_map)):
        name, key, int_point = sorted_keys_map[i]
        norm_point = [x / (p - 1) for x in int_point]
        if not key_within_bounds(norm_point, bounds):
            break
        found.add(name)
    
    return found

def run_6d():
    nodes = load_nodes(INPUT_FILE)
    norm_fn = normalize_fn_6d(nodes)
    d_max_model = compute_global_distance_model(nodes, norm_fn, 6)
    hilbert_orders = [2, 4, 6, 8, 10]
    
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["hilbert_order", "q_node", "t", "gt", "found", "tp", "fp", "fn", "precision", "recall", "jaccard"])
        
        for order in hilbert_orders:
            curve = HilbertCurve(order, 6)
            p = 2 ** order
            sorted_keys_map = []
            
            for name, node in nodes.items():
                vec_6d = node['coordinate']['Vec'] + [node['coordinate']['Height']]
                norm_vec = norm_fn(vec_6d)
                int_point = [int(x * (p - 1)) for x in norm_vec]
                key = curve.distance_from_point(int_point)
                sorted_keys_map.append((name, key, int_point))
            
            sorted_keys_map.sort(key=lambda x: x[1])
            
            for q_name in tqdm.tqdm(nodes.keys(), desc=f"Order {order}"):
                q_node = nodes[q_name]
                q_vec_6d = q_node['coordinate']['Vec'] + [q_node['coordinate']['Height']]
                q_norm = norm_fn(q_vec_6d)
                q_int = [int(x * (p - 1)) for x in q_norm]
                q_key = curve.distance_from_point(q_int)
                
                for T in thresh_ms:
                    gt = get_ground_truth(q_node, T)
                    gt.discard(q_name)
                    
                    if not gt:
                        writer.writerow([order, q_name, T, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0])
                        continue
                    
                    d_max = d_max_model[T]
                    bounds = [
                        (max(0, q_norm[d] - d_max), 
                        (min(1, q_norm[d] + d_max)
                    )) for d in range(6)
                    ]
                    
                    found = hilbert_query(q_key, bounds, curve, sorted_keys_map)
                    found.discard(q_name)
                    
                    tp = len(gt & found)
                    fp = len(found - gt)
                    fn = len(gt - found)
                    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
                    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
                    jac = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0
                    writer.writerow([order, q_name, T, len(gt), len(found), tp, fp, fn, prec, rec, jac])
    
    print(f"[✓] Results written to {OUTPUT_CSV}")

if __name__ == "__main__":
    run_6d()