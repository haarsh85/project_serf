import json
import numpy as np
from hilbertcurve.hilbertcurve import HilbertCurve
import bisect
from itertools import product
import csv
import time
import os

class VivaldiNode:
    __slots__ = ('name', 'vec', 'height', 'adjustment', 'rtts', 'hilbert_key')
    def __init__(self, name, vec, height, adjustment, rtts):
        self.name = name
        self.vec = np.array(vec, dtype=np.float64)  # 5D coordinates (seconds)
        self.height = float(height)                  # Network latency (seconds)
        self.adjustment = float(adjustment)          # Dynamic correction (seconds)
        self.rtts = rtts                            # Measured RTTs to other nodes (ms)
        self.hilbert_key = 0                         # Hilbert index to be computed

class HilbertSystem:
    def __init__(self, nodes, hilbert_order):
        self.nodes = nodes
        self.hilbert_order = hilbert_order
        self.n_dim = 5
        self.hilbert_curve = HilbertCurve(hilbert_order, self.n_dim)
        self.min_vec = np.zeros(self.n_dim)
        self.max_vec = np.zeros(self.n_dim)
        self.min_height = 0.0
        self.max_height = 0.0
        self.min_adj = 0.0
        self.max_adj = 0.0
        self._initialize()
    
    def _initialize(self):
        """Compute global bounds and Hilbert keys for all nodes"""
        # Initialize bounds with extreme values
        self.min_vec = np.full(self.n_dim, np.inf)
        self.max_vec = np.full(self.n_dim, -np.inf)
        self.min_height = np.inf
        self.max_height = -np.inf
        self.min_adj = np.inf
        self.max_adj = -np.inf
        
        # Compute global bounds
        for node in self.nodes:
            self.min_vec = np.minimum(self.min_vec, node.vec)
            self.max_vec = np.maximum(self.max_vec, node.vec)
            self.min_height = min(self.min_height, node.height)
            self.max_height = max(self.max_height, node.height)
            self.min_adj = min(self.min_adj, node.adjustment)
            self.max_adj = max(self.max_adj, node.adjustment)
        
        # Avoid division by zero
        vec_range = self.max_vec - self.min_vec
        vec_range[vec_range == 0] = 1e-15
        
        # Compute Hilbert keys
        for node in self.nodes:
            node.hilbert_key = self._vector_to_hilbert(node.vec)
        
        # Sort nodes by Hilbert key
        self.nodes.sort(key=lambda x: x.hilbert_key)
    
    def _vector_to_hilbert(self, vec):
        """Convert 5D vector to Hilbert index"""
        # Normalize to [0, 1] range
        normalized = (vec - self.min_vec) / (self.max_vec - self.min_vec)
        
        # Convert to integer grid coordinates [0, 2^p - 1]
        grid_coords = (normalized * (2**self.hilbert_order - 1)).astype(int)
        grid_coords = np.clip(grid_coords, 0, 2**self.hilbert_order - 1)
        
        # Compute Hilbert index
        return self.hilbert_curve.distance_from_point(grid_coords.tolist())
    
    def _generate_hypercube_corners(self, lower, upper):
        """Generate all corners of hyper-rectangle"""
        bounds = list(zip(lower, upper))
        return list(product(*bounds))
    
    def find_nodes_within_rtt(self, query_node, max_rtt_ms):
        """Find nodes within max RTT using Hilbert indexing"""
        # Convert to seconds
        max_rtt_seconds = max_rtt_ms / 1000.0
        
        # Calculate maximum possible contributions from height and adjustment
        max_height_contrib = query_node.height + self.max_height
        max_adj_contrib = max(0, query_node.adjustment + self.max_adj)
        
        # Calculate safe bound for Euclidean distance
        max_vec_distance = max_rtt_seconds - max_height_contrib - max_adj_contrib
        
        # Early exit if no matches possible
        if max_vec_distance < 0:
            return []
        
        # Create hyper-rectangle bounds
        lower_bounds = query_node.vec - max_vec_distance
        upper_bounds = query_node.vec + max_vec_distance
        
        # Generate hyper-rectangle corners
        corners = self._generate_hypercube_corners(lower_bounds, upper_bounds)
        
        # Compute Hilbert keys for all corners
        corner_keys = [self._vector_to_hilbert(np.array(c)) for c in corners]
        min_key = min(corner_keys)
        max_key = max(corner_keys)
        
        # Binary search for candidates
        keys = [n.hilbert_key for n in self.nodes]
        start_idx = bisect.bisect_left(keys, min_key)
        end_idx = bisect.bisect_right(keys, max_key)
        candidate_nodes = self.nodes[start_idx:end_idx]
        
        # Filter by hyper-rectangle (vector space only)
        results = []
        for node in candidate_nodes:
            if node.name == query_node.name:
                continue  # Skip query node itself
            if np.all(node.vec >= lower_bounds) and np.all(node.vec <= upper_bounds):
                results.append(node)
                
        return results

def load_data(file_path):
    """Load JSON data and create VivaldiNode objects"""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    nodes = []
    for item in data:
        # Extract RTTs (convert to float if stored as string)
        rtts = {}
        for target, rtt in item.get('rtts', {}).items():
            rtts[target] = float(rtt) if isinstance(rtt, str) else rtt
        
        # Create node
        coord = item['coordinate']
        node = VivaldiNode(
            name=item['name'],
            vec=coord['Vec'],
            height=coord['Height'],
            adjustment=coord['Adjustment'],
            rtts=rtts
        )
        nodes.append(node)
    
    return nodes

def compute_ground_truth(query_node, max_rtt_ms):
    """Compute ground truth using actual RTT measurements"""
    gt_nodes = set()
    for target, rtt in query_node.rtts.items():
        if rtt <= max_rtt_ms and target != query_node.name:
            gt_nodes.add(target)
    return gt_nodes

def compute_metrics(gt_set, result_nodes):
    """Compute evaluation metrics"""
    # Convert to sets of node names
    result_names = {node.name for node in result_nodes}
    
    # Calculate metrics
    tp = len(gt_set & result_names)      # True positives
    fp = len(result_names - gt_set)       # False positives
    fn = len(gt_set - result_names)       # False negatives
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    jaccard = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0
    
    return {
        'gt': len(gt_set),
        'found': tp,
        'fp': fp,
        'fn': fn,
        'precision': precision,
        'recall': recall,
        'jaccard': jaccard
    }

def run_experiment(data_file, output_csv):
    """Run full experiment with multiple parameters"""
    # Load and prepare data
    all_nodes = load_data(data_file)
    print(f"Loaded {len(all_nodes)} nodes from {data_file}")
    
    # Create name to node mapping
    node_map = {node.name: node for node in all_nodes}
    
    # Experiment parameters
    hilbert_orders = [2, 4, 6, 8, 10, 12, 14, 16]
    thresholds = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
    query_nodes = ["clab-nebula-serf1"] + [f"clab-nebula-serf{i}" for i in range(5, 161, 5)]
    
    # Prepare output file
    with open(output_csv, 'w', newline='') as csvfile:
        fieldnames = ['node', 'threshold', 'gt', 'found', 'fp', 'fn', 
                     'precision', 'recall', 'jaccard', 'hilbert_order']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        total_combinations = len(hilbert_orders) * len(thresholds) * len(query_nodes)
        processed = 0
        start_time = time.time()
        
        for order in hilbert_orders:
            print(f"\n{'='*40}")
            print(f"Processing Hilbert order {order}")
            print(f"{'='*40}")
            
            # Initialize Hilbert system for current order
            system = HilbertSystem(all_nodes.copy(), order)
            
            for threshold in thresholds:
                print(f"  Testing threshold: {threshold}ms")
                
                for qname in query_nodes:
                    # Get query node
                    query_node = node_map.get(qname)
                    if not query_node:
                        print(f"    ! Query node {qname} not found, skipping")
                        continue
                    
                    # Compute ground truth
                    gt_set = compute_ground_truth(query_node, threshold)
                    
                    # Run Hilbert-based query
                    result_nodes = system.find_nodes_within_rtt(query_node, threshold)
                    
                    # Compute metrics
                    metrics = compute_metrics(gt_set, result_nodes)
                    
                    # Write results
                    writer.writerow({
                        'node': qname,
                        'threshold': threshold,
                        'hilbert_order': order,
                        **metrics
                    })
                    
                    # Progress tracking
                    processed += 1
                    if processed % 100 == 0:
                        elapsed = time.time() - start_time
                        remaining = (total_combinations - processed) * (elapsed / processed)
                        print(f"    Progress: {processed}/{total_combinations} "
                              f"({processed/total_combinations:.1%}) "
                              f"ETA: {remaining/60:.1f} min")
    
    print(f"\nExperiment complete! Results saved to {output_csv}")

if __name__ == "__main__":
    # Configuration
    DATA_FILE = "cluster-status-2025-07-05T12_24_59.json"
    OUTPUT_CSV = "deepseek.csv"
    
    # Run the full experiment
    run_experiment(DATA_FILE, OUTPUT_CSV)