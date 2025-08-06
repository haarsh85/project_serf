import json
import numpy as np
from math import sqrt
from hilbertcurve.hilbertcurve import HilbertCurve
from collections import defaultdict
import statistics
import csv


class ImprovedHilbertQuerySystem:
    def __init__(self, json_path, p=2):
        self.p = p
        self.n = 5
        self.nodes = {}
        self.coordinates = []
        self.rtt_matrix = defaultdict(dict)
        self.curves = []
        self.indices = []
        self.min_coords = None
        self.max_coords = None
        self.rtt_percentiles = {}
        
        self.load_data(json_path)
        self.normalize_coordinates()
        self.calculate_rtt_statistics()
        self.build_radius_map()
        self.generate_curves()
        self.build_indices()

    def load_data(self, json_path):
        with open(json_path, 'r') as f:
            data = json.load(f)
        for node_data in data:
            name = node_data['name']
            coord = node_data['coordinate']['Vec']
            self.nodes[name] = {'coord': coord, 'norm_coord': None}
            self.coordinates.append(coord)
            for other, rtt in node_data['rtts'].items():
                self.rtt_matrix[name][other] = rtt

    def calculate_rtt_statistics(self):
        all_rtts = []
        for node, rtts in self.rtt_matrix.items():
            all_rtts.extend(rtts.values())
        self.rtt_percentiles = {
            'min': min(all_rtts),
            '25': np.percentile(all_rtts, 25),
            '50': np.median(all_rtts),
            '75': np.percentile(all_rtts, 75),
            'max': max(all_rtts)
        }

    def normalize_coordinates(self):
        self.coordinates = np.array(self.coordinates)
        self.min_coords = self.coordinates.min(axis=0)
        self.max_coords = self.coordinates.max(axis=0)
        range_vals = self.max_coords - self.min_coords
        range_vals[range_vals == 0] = 1
        for name, data in self.nodes.items():
            orig_coord = np.array(data['coord'])
            norm_coord = (orig_coord - self.min_coords) / range_vals
            self.nodes[name]['norm_coord'] = norm_coord

    def generate_curves(self):
        for rot in range(5):
            self.curves.append(('rotation', rot, HilbertCurve(self.p, self.n)))
        self.curves.append(('shift', 0, HilbertCurve(self.p, self.n)))

    def transform_coordinate(self, coord, curve_type, param):
        if curve_type == 'rotation':
            return np.roll(coord, -param)
        elif curve_type == 'shift':
            return (coord + 0.5) % 1.0
        return coord

    def coord_to_int(self, coord):
        return (coord * (2**self.p - 1)).astype(int)

    def build_indices(self):
        for curve_type, param, hc in self.curves:
            curve_index = []
            for name, data in self.nodes.items():
                trans_coord = self.transform_coordinate(data['norm_coord'], curve_type, param)
                int_coord = self.coord_to_int(trans_coord)
                dist = hc.distance_from_point(int_coord)
                #print(f"Node {name}: Hilbert distance at p={self.p} is {dist}")
                curve_index.append((dist, name))
            curve_index.sort(key=lambda x: x[0])
            self.indices.append({
                'type': curve_type,
                'param': param,
                'curve': hc,
                'index': curve_index
            })

    def compute_D_q(self, query_node, rtt_threshold):
        q_coord = np.array(self.nodes[query_node]['norm_coord'])
        max_dist = 0
        for i_name, i_data in self.nodes.items():
            if query_node == i_name:
                continue
            rtt = self.rtt_matrix[query_node].get(i_name)
            if rtt is not None and rtt <= rtt_threshold:
                i_coord = np.array(i_data['norm_coord'])
                dist = np.linalg.norm(q_coord - i_coord)
                if dist > max_dist:
                    max_dist = dist
        return max_dist

    def get_adaptive_factor(self, rtt_threshold):
        if rtt_threshold < self.rtt_percentiles['25']:
            return 1.3
        elif rtt_threshold < self.rtt_percentiles['50']:
            return 1.2
        elif rtt_threshold < self.rtt_percentiles['75']:
            return 1.1
        else:
            return 1.05

    def in_adaptive_hypercube(self, point, center, D_q, rtt_threshold):
        adaptive_factor = self.get_adaptive_factor(rtt_threshold)
        size = 2 * D_q / sqrt(self.n) * adaptive_factor
        half_size = size / 2
        low_bounds = center - half_size
        high_bounds = center + half_size
        for i in range(self.n):
            if not (low_bounds[i] <= point[i] <= high_bounds[i]):
                return False
        return True
    
    def build_radius_map(self):
        self.radius_map = defaultdict(dict)
        for query_node in self.nodes:
            for threshold in range(5, 65, 5):  # Or match your `thresholds` list
                D_q = self.compute_D_q(query_node, threshold)
                hilbert_radius = int(D_q * (2 ** (self.p * self.n) - 1))  
                self.radius_map[query_node][threshold] = hilbert_radius

                #print(query_node, "RTT Threshold:", threshold, "D_q:", D_q, "Hilbert Radius:", hilbert_radius)


    def range_query(self, query_node, rtt_threshold):
        q_coord = np.array(self.nodes[query_node]['norm_coord'])
        q_index_map = {}

        # Precompute Hilbert index of query for each curve
        for curve_data in self.indices:
            curve = curve_data['curve']
            curve_type = curve_data['type']
            param = curve_data['param']
            trans_coord = self.transform_coordinate(q_coord, curve_type, param)
            int_coord = self.coord_to_int(trans_coord)
            q_index_map[(curve_type, param)] = curve.distance_from_point(int_coord)

        hilbert_radius = self.radius_map[query_node][rtt_threshold]  # Make sure this is defined elsewhere
       
        best_nodes = []
        min_segment_size = float('inf')

        for curve_data in self.indices:
            curve_type = curve_data['type']
            param = curve_data['param']
            q_index = q_index_map[(curve_type, param)]

            candidates = []
            for h_index, node_name in curve_data['index']:
                if abs(h_index - q_index) <= hilbert_radius:
                    candidates.append(node_name)

            if len(candidates) < min_segment_size:
                min_segment_size = len(candidates)
                best_nodes = candidates

        return best_nodes


    def get_precision_recall_jaccard(self, query_node, rtt_threshold):
        ground_truth = {node for node, rtt in self.rtt_matrix[query_node].items() if rtt <= rtt_threshold and node != query_node}
        results = set(self.range_query(query_node, rtt_threshold)) - {query_node}
        TP = len(results & ground_truth)
        FP = len(results - ground_truth)
        FN = len(ground_truth - results)

        precision = TP / (TP + FP) if (TP + FP) > 0 else (1.0 if TP + FP + FN == 0 else 0.0)
        recall    = TP / (TP + FN) if (TP + FN) > 0 else (1.0 if TP + FP + FN == 0 else 0.0)
        jaccard   = TP / (TP + FP + FN) if (TP + FP + FN) > 0 else 1.0
        return precision, recall, jaccard, TP, FP, FN, len(ground_truth), len(results)


# === MULTI-ORDER EVALUATION ===
if __name__ == "__main__":
    json_path = "cluster-status-2025-07-05T12_24_59.json"
    hilbert_orders = [2, 4, 6, 8, 10, 12, 14, 16]
    thresholds = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
    query_nodes = ["clab-nebula-serf1"] #+ [f"clab-nebula-serf{i}" for i in range(5, 161, 5)]

    output_csv = "lawder162-5.csv"
    with open(output_csv, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["hilbert_order", "q_node", "threshold", "gt", "found", "tp", "fp", "fn", "precision", "recall", "jaccard"])

        for p in hilbert_orders:
            print(f"\n==== Evaluating Hilbert Order: p={p} ====")
            query_system = ImprovedHilbertQuerySystem(json_path, p=p)

            for threshold in thresholds:
                for node in query_nodes:
                    precision, recall, jaccard, tp, fp, fn, gt, found = query_system.get_precision_recall_jaccard(node, threshold)

                    # Print console output in the exact desired format:
                    print(f"  Threshold {threshold:2}ms | GT={gt:3} Found={found:3} TP={tp:3} FP={fp:3} FN={fn:3} | "
                        f"Prec={precision:.3f} Rec={recall:.3f} Jaccard={jaccard:.3f}")

    #         for node in query_nodes:
    #             for threshold in thresholds:
    #                 precision, recall, jaccard, tp, fp, fn, gt, found = query_system.get_precision_recall_jaccard(node, threshold)
    #                 writer.writerow([p, node, threshold, gt, found, tp, fp, fn, f"{precision:.4f}", f"{recall:.4f}", f"{jaccard:.4f}"])

    # print(f"\nAll results written to '{output_csv}'")
