import json
import math
import csv
import numpy as np
from tqdm import tqdm
from bisect import bisect_left, bisect_right
from hilbertcurve.hilbertcurve import HilbertCurve
from functools import lru_cache

class HilbertRangeQueryEvaluator:
    def __init__(self, json_file):
        self.json_file = json_file
        self.nodes = self.load_data()
        self.dimensions = 5
        self.min_vals, self.max_vals = self.get_min_max_vec()
        self.min_height = min(n['coordinate']['Height'] for n in self.nodes)

    def load_data(self):
        with open(self.json_file) as f:
            return json.load(f)

    def get_min_max_vec(self):
        min_vals = [float('inf')] * self.dimensions
        max_vals = [float('-inf')] * self.dimensions
        for node in self.nodes:
            vec = node['coordinate']['Vec']
            for i, val in enumerate(vec):
                min_vals[i] = min(min_vals[i], val)
                max_vals[i] = max(max_vals[i], val)
        return min_vals, max_vals

    def normalize(self, vec):
        return [
            (vec[i] - self.min_vals[i]) / (self.max_vals[i] - self.min_vals[i])
            for i in range(self.dimensions)
        ]

    def preprocess_nodes(self, order):
        curve = HilbertCurve(order, self.dimensions)
        max_val = 2 ** order - 1
        processed = []
        for node in self.nodes:
            norm = self.normalize(node['coordinate']['Vec'])
            scaled = [int(coord * max_val) for coord in norm]
            key = curve.distance_from_point(scaled)
            processed.append({
                'name': node['name'],
                'normalized_vec': norm,
                'hilbert_key': key,
                'coordinate': node['coordinate'],
                'rtts': node.get('rtts', {})
            })
        return sorted(processed, key=lambda x: x['hilbert_key'])

    def get_ground_truth(self, query_node, threshold):
        return {
            name for name, rtt in query_node['rtts'].items()
            if rtt <= threshold
        }

    def calculate_query_bounds(self, query_node, threshold):
        threshold_sec = threshold / 1000.0
        query_height = query_node['coordinate']['Height']
        D_max = threshold_sec - query_height - self.min_height
        if D_max < 0:
            return None

        bounds = []
        norm_vec = self.normalize(query_node['coordinate']['Vec'])
        for i in range(self.dimensions):
            range_size = self.max_vals[i] - self.min_vals[i]
            offset = D_max / range_size
            low = max(0.0, norm_vec[i] - offset)
            high = min(1.0, norm_vec[i] + offset)
            bounds.append((low, high))
        return bounds

    def merge_intervals(self, intervals):
        if not intervals:
            return []
        intervals.sort()
        merged = [intervals[0]]
        for current in intervals[1:]:
            prev = merged[-1]
            if current[0] <= prev[1] + 1:
                merged[-1] = (prev[0], max(prev[1], current[1]))
            else:
                merged.append(current)
        return merged

    def region_to_intervals(self, curve, bounds, order, max_depth=3):
        max_val = 2 ** order - 1
        intervals = []

        stack = [(0, 0, 2**(self.dimensions*order)-1, [0]*self.dimensions, [max_val]*self.dimensions)]

        while stack:
            depth, low_key, high_key, min_corner, max_corner = stack.pop()
            min_norm = [c / max_val for c in min_corner]
            max_norm = [c / max_val for c in max_corner]

            overlap = all(not (max_norm[i] < bounds[i][0] or min_norm[i] > bounds[i][1]) for i in range(self.dimensions))
            if not overlap:
                continue

            full_contain = all(bounds[i][0] <= min_norm[i] and max_norm[i] <= bounds[i][1] for i in range(self.dimensions))
            if full_contain or depth >= max_depth:
                intervals.append((low_key, high_key))
                continue

            sub_cube_size = (max_corner[0] - min_corner[0] + 1) // 2
            for idx in range(2 ** self.dimensions):
                bits = [(idx >> i) & 1 for i in range(self.dimensions)]
                sub_min = min_corner.copy()
                sub_max = max_corner.copy()
                for d in range(self.dimensions):
                    if bits[d]:
                        sub_min[d] = min_corner[d] + sub_cube_size
                    else:
                        sub_max[d] = min_corner[d] + sub_cube_size - 1
                sub_low_key = curve.distance_from_point(sub_min)
                sub_high_key = curve.distance_from_point(sub_max)
                stack.append((depth + 1, sub_low_key, sub_high_key, sub_min, sub_max))

        return self.merge_intervals(intervals)

    def evaluate_query(self, order, query_node, threshold, processed):
        gt = self.get_ground_truth(query_node, threshold)
        bounds = self.calculate_query_bounds(query_node, threshold)
        if bounds is None:
            return (len(gt), 0, 0, 0, len(gt), 0, 0, 0)

        curve = HilbertCurve(order, self.dimensions)
        intervals = self.region_to_intervals(curve, bounds, order)

        keys = [n['hilbert_key'] for n in processed]
        found = set()
        for lo, hi in intervals:
            l = bisect_left(keys, lo)
            r = bisect_right(keys, hi)
            for i in range(l, r):
                node = processed[i]
                if node['name'] != query_node['name']:
                    found.add(node['name'])

        tp = len(gt & found)
        fp = len(found - gt)
        fn = len(gt - found)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        jac = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0

        return len(gt), len(found), tp, fp, fn, prec, rec, jac

    def run_evaluation(self, output_csv, query_names=None):
        hilbert_orders = [2, 4, 6, 8, 10]
        thresholds = list(range(5, 65, 5))

        with open(output_csv, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=[
                "hilbert_order", "q_node", "t", "gt", "found",
                "tp", "fp", "fn", "precision", "recall", "jaccard"
            ])
            writer.writeheader()

            for order in hilbert_orders:
                print(f"[INFO] Processing Hilbert order {order}")
                processed_nodes = self.preprocess_nodes(order)
                for query_node in tqdm(self.nodes, desc=f"Order {order}"):
                    if 'rtts' not in query_node:
                        continue
                    if query_names and query_node['name'] not in query_names:
                        continue
                    for t in thresholds:
                        gt, found, tp, fp, fn, p, r, j = self.evaluate_query(
                            order, query_node, t, processed_nodes
                        )
                        writer.writerow({
                            "hilbert_order": order,
                            "q_node": query_node['name'],
                            "t": t,
                            "gt": gt,
                            "found": found,
                            "tp": tp,
                            "fp": fp,
                            "fn": fn,
                            "precision": p,
                            "recall": r,
                            "jaccard": j
                        })

if __name__ == "__main__":
    evaluator = HilbertRangeQueryEvaluator("cluster-status-2025-07-05T12_24_59.json")
    evaluator.run_evaluation("range3-result.csv") 
    print("\n[COMPLETE] Results saved to range3-result.csv")

    ##
    # Run for a single node:
    # evaluator.run_evaluation("range3-single.csv", query_names=["clab-nebula-serf131"])
    # Run for a list of nodes:
    #query_list = ["clab-nebula-serf131", "clab-nebula-serf022"]
    #evaluator.run_evaluation("range3-subset.csv", query_names=query_list)   