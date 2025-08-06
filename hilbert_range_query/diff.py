import math

def parse_results(file_path):
    results = {}
    current_node = None
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("Testing thresholds for node:"):
                current_node = line.split(":")[1].strip()
                results[current_node] = {}
            elif line and line[0].isdigit():
                parts = [p.strip() for p in line.split("|")]
                threshold = int(parts[0])
                try:
                    metrics = {
                        "GT": int(parts[1]),
                        "Found": int(parts[2]),
                        "Precision": float(parts[3]) if parts[3].lower() != "nan" else float("nan"),
                        "Recall": float(parts[4]) if parts[4].lower() != "nan" else float("nan"),
                        "Jaccard": float(parts[5]) if parts[5].lower() != "nan" else float("nan"),
                        "FP": int(parts[6]),
                        "FN": int(parts[7]),
                        "RawLine": line
                    }
                except Exception as e:
                    print(f"⚠️ Error parsing line in {file_path}: {line}")
                    raise e
                results[current_node][threshold] = metrics
    return results


def compare_results(file1, file2, float_tol=1e-6):
    res1 = parse_results(file1)
    res2 = parse_results(file2)
    differences = []

    for node in res1:
        for threshold in res1[node]:
            if node not in res2 or threshold not in res2[node]:
                differences.append({
                    "node": node,
                    "threshold": threshold,
                    "metric": "Missing",
                    "file1_val": "Exists",
                    "file2_val": "Missing"
                })
                continue

            m1 = res1[node][threshold]
            m2 = res2[node][threshold]

            # Compare int metrics
            for key in ["GT", "Found", "FP", "FN"]:
                if m1[key] != m2[key]:
                    differences.append({
                        "node": node,
                        "threshold": threshold,
                        "metric": key,
                        "file1_val": m1[key],
                        "file2_val": m2[key],
                        "file1_line": m1["RawLine"],
                        "file2_line": m2["RawLine"]
                    })

            # Compare float metrics, handling NaNs correctly
            for key in ["Precision", "Recall", "Jaccard"]:
                val1 = m1[key]
                val2 = m2[key]
                if math.isnan(val1) and math.isnan(val2):
                    continue  # Both are NaN, treat as equal
                if not math.isclose(val1, val2, rel_tol=float_tol, abs_tol=float_tol):
                    differences.append({
                        "node": node,
                        "threshold": threshold,
                        "metric": key,
                        "file1_val": val1,
                        "file2_val": val2,
                        "file1_line": m1["RawLine"],
                        "file2_line": m2["RawLine"]
                    })

    return differences


# === USAGE ===
file1 = "162-5-1.txt"
file2 = "162-5-2.txt"

diffs = compare_results(file1, file2)

if not diffs:
    print("✅ All metrics are identical for all thresholds and nodes.")
else:
    print(f"❌ {len(diffs)} differences found:\n")
    for diff in diffs:
        print(f"Node: {diff['node']}, Threshold: {diff['threshold']}ms, Metric: {diff['metric']}")
        print(f"→ {file1}: {diff['metric']} = {diff['file1_val']}")
        print(f"→ {file2}: {diff['metric']} = {diff['file2_val']}")
        print(f"  Line from {file1}: {diff.get('file1_line', '-')}")
        print(f"  Line from {file2}: {diff.get('file2_line', '-')}")
        print("-" * 80)
