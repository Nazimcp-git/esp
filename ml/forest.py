"""forest.py - evaluates exported model.json.
Provides pure NumPy tree traversal matching scikit-learn Random Forest output.
"""

import json
import os
import numpy as np

def load_model(path=None):
    if path is None:
        default_path = os.path.join(os.path.dirname(__file__), "models", "model.json")
        path = default_path if os.path.exists(default_path) else "models/model.json"
    with open(path, "r") as f:
        return json.load(f)

def _tree_proba(t, x):
    n = 0
    while t["left"][n] != -1:
        go_left = np.float32(x[t["feature"][n]]) <= np.float32(t["threshold"][n])
        n = t["left"][n] if go_left else t["right"][n]
    return np.array(t["value"][n])

def predict_proba(model, x):
    """Average of the leaf probabilities of all trees (identical to scikit-learn)."""
    return np.mean([_tree_proba(t, x) for t in model["trees"]], axis=0)

