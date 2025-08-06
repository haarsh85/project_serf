import json
import numpy as np
from math import sqrt
from hilbertcurve.hilbertcurve import HilbertCurve
from collections import defaultdict
import time

class HilbertRangeQuerySystem:
    def __init__(self, json_path, p=8):
        self.p = p
        self.n = 5  # 5D
        self.nodes = {}
        self.rtt_matrix = defaultdict(dict)
        self.curves = []
        self.indices = []
        self.min_coords = None
        self.max_coords = None

        self.load_data(json_path)
        self.normalize_coordinates()
        self.generate_curves()
        self.build_indices()

    def load_data(self, json_path):
        with open(json_path, 'r') as f:
            data = json.load(f)
        for node in data:
            name = node['name']
            self.nodes[name] = {
                'coord': np.array(node['coordinate']['Vec']),
                'norm_coord': None,
                'hilbert': {}
            }
            for target, rtt in node['rtts'].items():
                self.rtt_matrix[name][target] = rtt

    def normalize_coordinates(self):
        coords = np.array([node['coord'] for node in self.nodes.values()])
        self.min_coords = coords.min(axis=0)
        self.max_coords = coords.max(axis=0)
        diff = self.max_coords - self.min_coords
        diff[diff == 0] = 1  # avoid div by zero
        for node in self.nodes.values():
            norm = (node['coord'] - self.min_coords) / diff
            node['norm_coord'] = norm

    def generate_curves(self):
        self.curves = []
        # Original
        self.curves.append({
            'type': 'origin',
            'curve': HilbertCurve(self.p, self.n),
            'transform': lambda x: x
        })
        # Rotations
        for i in range(1, 4):
            self.curves.append({
                'type': f'rotation_{i}',
                'curve': HilbertCurve(self.p, self.n),
                'transform': lambda x, i=i: np.roll(x, i)
            })
        # Shift
        self.curves.append({
            'type': 'shift',
            'curve': HilbertCurve(self.p + 1, self.n),
            'transform': lambda x: (x + 0.5) % 1.0
        })

    def build_indices(self):
        self.indices = []
        for curve_data in self.curves:
            index = []
            for name, node in self.nodes.items():
                transformed = curve_data['transform'](node['norm_coord'])
                int_coord = np.round(transformed * (2**self.p - 1)).astype(int)
                hval = curve_data['curve'].distance_from_point(int_coord.tolist())
                node['hilbert'][curve_data['type']] = hval
                index.append((hval, name))
            index.sort()
            self.indices.append({
                'type': curve_data['type'],
                'index': index,
                'curve': curve_data['curve'],
                'transform': curve_data['transform']
            })

    def compute_radius(self, query_node, threshold):
        q = self.nodes[query_node]['norm_coord']
        max_dist = 0
        for target, rtt in self.rtt_matrix[query_node].items():
            if rtt <= threshold:
                dist = np.linalg.norm(q - self.nodes[target]['norm_coord'])
                max_dist = max(max_dist, dist)
        return max_dist

    def find_clusters(self, query_node, threshold, curve):
        q = self.nodes[query_node]['norm_coord']
        D = self.compute_radius(query_node, threshold)
        q_trans = curve['transform'](q)

        candidates = []
        for hval, name in curve['index']:
            if name == query_node:
                continue
            coord = self.nodes[name]['norm_coord']
            transformed = curve['transform'](coord)
            if np.all(np.abs(transformed - q_trans) <= D):
                candidates.append((hval, name))

        clusters = []
        cluster = []
        prev = -float('inf')
        for hval, name in candidates:
            if hval == prev + 1 or not cluster:
                cluster.append(name)
            else:
                clusters.append(cluster)
                cluster = [name]
            prev = hval
        if cluster:
            clusters.append(cluster)

        return clusters

    def range_query(self, query_node, threshold):
        best_clusters = []
        min_count = float('inf')
        best_type = None
        for curve in self.indices:
            clusters = self.find_clusters(query_node, threshold, curve)
            if len(clusters) < min_count:
                min_count = len(clusters)
                best_clusters = clusters
                best_type = curve['type']
        result = set()
        for cluster in best_clusters:
            result.update(cluster)
        return result, best_type, min_count

    def evaluate_query(self, query_node, threshold):
        gt = {name for name, rtt in self.rtt_matrix[query_node].items()
              if rtt <= threshold and name != query_node}
        start = time.time()
        found, curve_type, clusters = self.range_query(query_node, threshold)
        elapsed = time.time() - start
        tp = len(found & gt)
        fp = len(found - gt)
        fn = len(gt - found)
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        jaccard = tp / (tp + fp + fn) if (tp + fp + fn) else 0
        return {
            'threshold': threshold,
            'GT': len(gt),
            'Found': len(found),
            'Precision': round(prec, 2),
            'Recall': round(rec, 2),
            'Jaccard': round(jaccard, 2),
            'FP': fp,
            'FN': fn,
            'Curve': curve_type,
            'Clusters': clusters,
            'Time': round(elapsed, 4)
        }

    def evaluate_orders(self, query_node, thresholds, orders):
        all_results = {}
        for order in orders:
            self.p = order
            self.generate_curves()
            self.build_indices()
            results = []
            for t in thresholds:
                results.append(self.evaluate_query(query_node, t))
            all_results[order] = results
        return all_results

    def print_results(self, all_results):
        print(f"==== Query Node {QUERY_NODE} ====")
        for p, res_list in all_results.items():
            print(f"\n==== Hilbert Order p={p} ====")
            print(f"{'RTT':>5} | {'GT':>3} | {'Found':>5} | {'Prec':>5} | {'Recall':>6} | {'Jaccard':>7} | {'FP':>3} | {'FN':>3} | {'Curve':>8} | {'Clusters':>8} | Time")
            print("-" * 90)
            for r in res_list:
                print(f"{r['threshold']:>5} | {r['GT']:>3} | {r['Found']:>5} | {r['Precision']:>5.2f} | {r['Recall']:>6.2f} | {r['Jaccard']:>7.2f} | {r['FP']:>3} | {r['FN']:>3} | {r['Curve']:>8} | {r['Clusters']:>8} | {r['Time']:>5.2f}")


if __name__ == '__main__':
    PATH = "cluster-status-2025-07-05T12_24_59.json"
    QUERY_NODE = "clab-nebula-serf100"
    THRESHOLDS = [5, 10, 15, 20, 25, 30, 40, 50, 60]
    ORDERS = [2, 4, 6, 8, 10, 16]

    system = HilbertRangeQuerySystem(PATH, p=ORDERS[0])
    results = system.evaluate_orders(QUERY_NODE, THRESHOLDS, ORDERS)
    system.print_results(results)
