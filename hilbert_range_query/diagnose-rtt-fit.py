import json
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_squared_error

BITS = 7
DIMENSIONS = 4
QUERY_NODE_NAME = "clab-century-serf1"
INPUT_FILE = "cluster-status-2025-07-05T12_24_59.json"

with open(INPUT_FILE, "r") as f:
    data = json.load(f)

query_node = next(n for n in data if n["name"] == QUERY_NODE_NAME)
vec_q = np.array(query_node["coordinate"]["Vec"])

X, y = [], []
for node in data:
    if node["name"] == QUERY_NODE_NAME:
        continue
    vec_other = np.array(node["coordinate"]["Vec"])
    dist = np.linalg.norm(vec_q - vec_other)
    rtt = query_node["rtts"].get(node["name"])
    if rtt is not None:
        X.append(dist)
        y.append(rtt)

X = np.array(X).reshape(-1, 1)
y = np.array(y)

# Linear fit
linear_model = LinearRegression().fit(X, y)
linear_pred = linear_model.predict(X)
linear_rmse = np.sqrt(mean_squared_error(y, linear_pred))

# Polynomial fit
poly_model = make_pipeline(PolynomialFeatures(2), LinearRegression())
poly_model.fit(X, y)
poly_pred = poly_model.predict(X)
poly_rmse = np.sqrt(mean_squared_error(y, poly_pred))

# Plot
plt.figure(figsize=(8, 5))
plt.scatter(X, y, label="Data", color="black")
plt.plot(X, linear_pred, label=f"Linear Fit (RMSE={linear_rmse:.2f})", color="blue")
plt.plot(X, poly_pred, label=f"Poly Fit (RMSE={poly_rmse:.2f})", color="green")
plt.title("RTT vs Euclidean Distance")
plt.xlabel("Euclidean Distance (4D)")
plt.ylabel("RTT (ms)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("rtt_vs_distance_fit.png")
plt.show()
