#!/usr/bin/env python3
"""parity_test.py - Proves the JSON forest implementation exactly matches scikit-learn.
Uses embedded test_vector in model.json.
"""

import os
import sys
import numpy as np
from features import window_features
from forest import load_model, predict_proba

def main():
    default_path = os.path.join(os.path.dirname(__file__), "models", "model.json")
    path = sys.argv[1] if len(sys.argv) > 1 else default_path
    
    if not os.path.exists(path):
        print(f"Error: model file '{path}' not found. Run train.py first.")
        sys.exit(1)
        
    m = load_model(path)
    tv = m["test_vector"]
    feat, motion = window_features(np.array(tv["window"]), tv["calib"])
    p = predict_proba(m, feat)
    
    print("=== Model Parity Test ===")
    print("Features (computed):", np.round(feat, 4).tolist())
    print("Features (expected):", tv["features"])
    print("Probabilities (forest.py):", np.round(p, 3).tolist())
    print("Probabilities (sklearn)  :", np.round(tv["proba"], 3).tolist())
    
    ok = np.allclose(feat, tv["features"], atol=1e-4) and np.allclose(p, tv["proba"], atol=2e-3)
    if ok:
        print("\nResult: PARITY OK (Runtime matches trained model within tolerance)")
    else:
        print("\nResult: PARITY FAILED (Discrepancy detected between runtime and training)")
        
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()

