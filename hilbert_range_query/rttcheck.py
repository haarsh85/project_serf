import json
import csv
import numpy as np

# Load nodes JSON
with open("cluster-status-2025-07-05T12_24_59.json", "r") as f:
    nodes = json.load(f)

# Dictionary for fast lookup by node name
node_dict = {node["name"]: node for node in nodes}

# RTT prediction function
def serf_rtt_prediction(coord_a, coord_b, use_height=True, use_adjustment=True):
    vec_a = np.array(coord_a["Vec"])
    vec_b = np.array(coord_b["Vec"])

    height_a = coord_a.get("Height", 0) if use_height else 0
    height_b = coord_b.get("Height", 0) if use_height else 0

    adjust_a = coord_a.get("Adjustment", 0) if use_adjustment else 0
    adjust_b = coord_b.get("Adjustment", 0) if use_adjustment else 0

    euclidean = np.linalg.norm(vec_a - vec_b)
    rtt = euclidean + height_a + height_b

    adjusted = rtt + adjust_a + adjust_b
    if adjusted > 0:
        rtt = adjusted

    return rtt * 1000  # convert to milliseconds

# Configurations for different modes
configs = [
    {"height": False, "adjustment": False, "filename": "serf_rtt_predic_rtt_vec.csv"},
    {"height": True,  "adjustment": False, "filename": "serf_rtt_predic_rtt_vec_height.csv"},
    {"height": True,  "adjustment": True,  "filename": "serf_rtt_predic_rtt_vec_height_adj.csv"},
]

# Common header for all CSVs
header = [("From", "To", "RTT_actual_A_to_B", "RTT_predicted")]

# Process each config
for config in configs:
    output_rows = [header[0]]
    print(f"\n--- Computing RTTs with Height={config['height']} Adjustment={config['adjustment']} ---")

    for from_node in nodes:
        from_name = from_node["name"]
        coord_a = from_node["coordinate"]
        rtts = from_node.get("rtts", {})

        for to_name, measured_rtt in rtts.items():
            if to_name not in node_dict:
                continue

            coord_b = node_dict[to_name]["coordinate"]
            predicted_rtt = serf_rtt_prediction(coord_a, coord_b,
                                                use_height=config["height"],
                                                use_adjustment=config["adjustment"])

            output_rows.append((from_name, to_name, measured_rtt, round(predicted_rtt, 3)))

    # Write to CSV
    with open(config["filename"], "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(output_rows)

    print(f"Saved results to {config['filename']}")
