#!/usr/bin/env python3
"""Train the gesture classifier and export models/model.json."""

import glob
import json
import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, ConfusionMatrixDisplay
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from features import make_windows, window_features, WINDOW, STEP, MOTION_MAX, N_FEATURES

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW = ["f1", "f2", "f3", "f4", "f5", "ax", "ay", "az", "gx", "gy", "gz"]

vocab_path = os.path.join(BASE_DIR, "vocab.json")
vocab = json.load(open(vocab_path))
classes = vocab["classes"]
cidx = {c: i for i, c in enumerate(classes)}

def load():
    X, y, g, dropped, total = [], [], [], 0, 0
    csv_pattern = os.path.join(BASE_DIR, "data", "*.csv")
    csv_files = sorted(glob.glob(csv_pattern))
    
    if not csv_files:
        raise SystemExit(f"No CSV recordings found matching {csv_pattern}")
        
    for path in csv_files:
        sess = os.path.basename(path)[:-4]
        calib_file = os.path.join(BASE_DIR, "data", f"{sess}_calib.json")
        if not os.path.exists(calib_file):
            print(f"Skipping {path}: calibration file {calib_file} missing.")
            continue
        calib = json.load(open(calib_file))
        df = pd.read_csv(path)
        
        for (label, take), part in df.groupby(["label", "take"]):
            if label not in cidx:
                continue
            for feat, motion in make_windows(part[RAW].values, calib):
                total += 1
                if motion > MOTION_MAX:
                    dropped += 1   # Motion gate: hand was transitioning, not static pose
                    continue
                X.append(feat)
                y.append(cidx[label])
                g.append(f"{sess}-{take}")
                
    print(f"Windows extracted: {total}, Dropped for excess motion: {dropped}")
    return np.array(X, np.float32), np.array(y), np.array(g)

def make_rf():
    return RandomForestClassifier(
        n_estimators=60, 
        max_depth=10, 
        min_samples_leaf=3,
        class_weight="balanced", 
        random_state=42, 
        n_jobs=-1
    )

def export(rf, X, calib_example, path):
    trees = []
    for est in rf.estimators_:
        t = est.tree_
        val = t.value[:, 0, :]
        val = val / val.sum(axis=1, keepdims=True)
        trees.append({
            "left": t.children_left.tolist(),
            "right": t.children_right.tolist(),
            "feature": t.feature.tolist(),
            "threshold": [round(float(v), 6) for v in t.threshold],
            "value": [[round(float(p), 4) for p in val[i]] if t.children_left[i] == -1 else []
                      for i in range(t.node_count)],
        })

    # Embedded test vector so independent runtime (e.g. mobile/web/C++) can verify exact parity
    rng = np.random.default_rng(1)
    fracs = [0.5, 0.2, 0.2, 0.2, 0.2]
    row = [calib_example["open"][i] + fracs[i] * (calib_example["fist"][i] - calib_example["open"][i]) for i in range(5)]
    base = np.array([row + [0.05, -0.02, 0.98, 1.0, -2.0, 0.5]] * WINDOW)
    win = np.round(base + rng.normal(0, 0.01, base.shape) * np.abs(base).clip(0.1), 3)
    feat, motion = window_features(win, calib_example)
    proba = rf.predict_proba(feat.reshape(1, -1).astype(np.float32))[0]

    model = {
        "version": 1,
        "classes": classes,
        "phrases": vocab["phrases"],
        "category": vocab.get("category", {}),
        "window": WINDOW,
        "step": STEP,
        "motion_max": MOTION_MAX,
        "n_features": N_FEATURES,
        "trees": trees,
        "test_vector": {
            "window": win.tolist(),
            "calib": calib_example,
            "features": [round(float(v), 6) for v in feat],
            "proba": [round(float(p), 6) for p in proba]
        }
    }
    
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(model, f, separators=(",", ":"))
    print(f"Exported {path} ({os.path.getsize(path) / 1024:.0f} KB, {len(trees)} trees)")

def main():
    X, y, g = load()
    if len(X) == 0:
        raise SystemExit("No valid data found in data/*.csv")
        
    print("Class sample counts:", {classes[i]: int((y == i).sum()) for i in range(len(classes))})

    # 1) Hold out whole takes (prevents optimistic leak between overlapping/adjacent windows)
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=7).split(X, y, g))
    rf = make_rf().fit(X[tr], y[tr])
    pred = rf.predict(X[te])
    acc = accuracy_score(y[te], pred)
    print(f"\nHELD-OUT-TAKE ACCURACY: {acc * 100:.1f}% (target: 85% or more)")
    
    present = sorted(set(y[te]) | set(pred))
    print(classification_report(y[te], pred, labels=present, target_names=[classes[i] for i in present], zero_division=0))

    # 2) Grouped cross-validation
    n_groups = len(set(g))
    if n_groups >= 4:
        scores = []
        for a, b in GroupKFold(n_splits=min(5, n_groups)).split(X, y, g):
            scores.append(accuracy_score(y[b], make_rf().fit(X[a], y[a]).predict(X[b])))
        print(f"GROUPED CV ACCURACY: {np.mean(scores) * 100:.1f}% +/- {np.std(scores) * 100:.1f}")

    models_dir = os.path.join(BASE_DIR, "models")
    os.makedirs(models_dir, exist_ok=True)

    cm = confusion_matrix(y[te], pred, labels=range(len(classes)))
    np.savetxt(os.path.join(models_dir, "confusion_matrix.csv"), cm, fmt="%d", delimiter=",")

    fig, ax = plt.subplots(figsize=(8, 7))
    ConfusionMatrixDisplay(cm, display_labels=classes).plot(ax=ax, xticks_rotation=45, colorbar=False)
    plt.tight_layout()
    plt.savefig(os.path.join(models_dir, "confusion_matrix.png"), dpi=150)
    plt.close()

    off = cm.copy()
    np.fill_diagonal(off, 0)
    worst = np.dstack(np.unravel_index(np.argsort(-off.ravel())[:3], off.shape))[0]
    for i, j in worst:
        if off[i, j] > 0:
            print(f"Confused: {classes[i]} predicted as {classes[j]} x{off[i, j]}")

    imp = sorted(zip(["f1", "f2", "f3", "f4", "f5", "ax", "ay", "az"], rf.feature_importances_), key=lambda t: -t[1])
    print("Feature importance:", [(n, round(float(v), 3)) for n, v in imp])

    # 3) Final model on ALL data, exported with latest calibration
    final = make_rf().fit(X, y)
    calib_files = sorted(glob.glob(os.path.join(BASE_DIR, "data", "*_calib.json")))
    last_calib = json.load(open(calib_files[-1]))
    export(final, X, last_calib, os.path.join(models_dir, "model.json"))

if __name__ == "__main__":
    main()

