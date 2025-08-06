import json
import pandas as pd
import numpy as np
import re
from hilbertcurve.hilbertcurve import HilbertCurve

# === LOGGING SETUP ===
LOG_FILE = "anjumm-debug.txt"
def debug_log(*args, **kwargs):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        print(*args, file=f, **kwargs)

# === CONFIGURATION ===
BITS = 7
DIMENSIONS = 4
COORD_FILE = "rttsfor80nodes.txt"

# === LOAD DATA ===
with open(COORD_FILE, "r") as f:
    content = f.read()
    serf_data = json.loads(content)

# === Sort by serf number ===
def extract_serf_number(node_name):
    match = re.search(r"serf(\d+)", node_name)
    return int(match.group(1)) if match else float('inf')

serf_data.sort(key=lambda x: extract_serf_number(x["name"]))

# === PREPARE DataFrame with 5D coordinates ===
records = []
for node in serf_data:
    v = node["coordinate"]["Vec"]
    records.append({
        "name": node["name"],
        "x": v[0],
        "y": v[1],
        "z": v[2],
        "w": v[3],
    })
df = pd.DataFrame(records)

# === NORMALIZATION ===
def normalize(val, min_val, max_val):
    if max_val - min_val == 0:
        return 0
    return int(((val - min_val) / (max_val - min_val)) * (2**BITS - 1))

x_bounds = (df["x"].min(), df["x"].max())
y_bounds = (df["y"].min(), df["y"].max())
z_bounds = (df["z"].min(), df["z"].max())
w_bounds = (df["w"].min(), df["w"].max())

debug_log("=== Normalization Ranges ===")
debug_log(f"x: {x_bounds}, y: {y_bounds}, z: {z_bounds}, w: {w_bounds}")

hilbert = HilbertCurve(p=BITS, n=DIMENSIONS)

def encode_node(x, y, z, w):
    x_n = normalize(x, *x_bounds)
    y_n = normalize(y, *y_bounds)
    z_n = normalize(z, *z_bounds)
    w_n = normalize(w, *w_bounds)
    return hilbert.distance_from_point([x_n, y_n, z_n, w_n])

# Add Hilbert index
df["hilbert"] = df.apply(lambda row: encode_node(row["x"], row["y"], row["z"], row["w"]), axis=1)

debug_log("\n=== Hilbert Indices ===")
for row in df.itertuples():
    debug_log(f"{row.name}: Hilbert Index = {row.hilbert}")

# === RANGE QUERY SUPPORT ===
def build_latency_hilbert_mapping(df, query_node_name, serf_data, percent=95):
    query_row = df[df["name"] == query_node_name].iloc[0]
    q_index = encode_node(query_row.x, query_row.y, query_row.z, query_row.w)

    latencies, dists = [], []
    for node in df.itertuples():
        if node.name == query_node_name:
            continue
        data_idx = next(i for i, n in enumerate(serf_data) if n["name"] == node.name)
        rtt = serf_data[data_idx]["rtts"].get(query_node_name)
        if rtt is None:
            continue
        hd = abs(node.hilbert - q_index)
        latencies.append(rtt)
        dists.append(hd)

    latency_bins = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60]
    mapping = {}
    debug_log(f"\n=== RTT-Hilbert Mapping for {query_node_name} ===")
    for max_rtt in latency_bins:
        bucket = [d for r, d in zip(latencies, dists) if r <= max_rtt]
        percentile = int(np.percentile(bucket, percent)) if bucket else None
        mapping[max_rtt] = percentile
        debug_log(f"RTT ≤ {max_rtt}ms → Hilbert threshold: {percentile}")
    return mapping

def range_query(query_node_name, rtt_threshold_ms):
    thr_map = build_latency_hilbert_mapping(df, query_node_name, serf_data)
    hilbert_thr = thr_map.get(rtt_threshold_ms)
    if hilbert_thr is None:
        raise ValueError(f"No mapping for RTT≤{rtt_threshold_ms} ms")

    query_node = df[df["name"] == query_node_name].iloc[0]
    q_index = encode_node(query_node["x"], query_node["y"], query_node["z"], query_node["w"])

    df["hilbert_distance"] = np.abs(df["hilbert"] - q_index)
    df_filtered = df[df["hilbert_distance"] <= hilbert_thr]

    debug_log(f"\n=== Range Query from {query_node_name} ===")
    debug_log(f"RTT ≤ {rtt_threshold_ms}ms")
    debug_log(f"Hilbert threshold: {hilbert_thr}")
    debug_log(f"Matched nodes: {len(df_filtered)}")
    debug_log(df_filtered.sort_values("hilbert_distance")[["name", "hilbert", "hilbert_distance"]].to_string(index=False))

    # === NEW: Print True RTT matches and evaluate FPs and FNs ===
    debug_log(f"\n[True RTT Matches for {query_node_name} <= {rtt_threshold_ms} ms]")
    query_rtts = next(n["rtts"] for n in serf_data if n["name"] == query_node_name)
    true_matches = {name for name, rtt in query_rtts.items() if rtt <= rtt_threshold_ms}
    debug_log(f"Count: {len(true_matches)}")
    debug_log(f"Nodes: {sorted(true_matches)}")

    predicted_matches = set(df_filtered["name"])
    false_positives = predicted_matches - true_matches - {query_node_name}
    false_negatives = true_matches - predicted_matches - {query_node_name}

    debug_log(f"\nFalse Positives ({len(false_positives)}):")
    for name in sorted(false_positives):
        debug_log(name)

    debug_log(f"\nFalse Negatives ({len(false_negatives)}):")
    for name in sorted(false_negatives):
        debug_log(name)

# === EXAMPLE USAGE ===
if __name__ == "__main__":
    range_query("clab-century-serf1", rtt_threshold_ms=20)
