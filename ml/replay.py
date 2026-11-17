#!/usr/bin/env python3
"""replay.py - Feed recorded frames through the accept/lock state machine.
Simulates neutral -> gesture sequence for every phrase and measures recognition speed and false-positive rates.

Usage:
  python replay.py <session_name>    (e.g., python replay.py day1)
"""

import json
import os
import sys
import numpy as np
import pandas as pd
from features import make_windows, WINDOW, STEP
from forest import load_model, predict_proba
from recognizer import Recognizer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW = ["f1", "f2", "f3", "f4", "f5", "ax", "ay", "az", "gx", "gy", "gz"]
FPS = 20.0

def main():
    if len(sys.argv) < 2:
        print("Usage: python replay.py <session_name>")
        print("Example: python replay.py fake1")
        sys.exit(1)

    sess = sys.argv[1]
    model_path = os.path.join(BASE_DIR, "models", "model.json")
    if not os.path.exists(model_path):
        print(f"Error: model file {model_path} not found. Run train.py first.")
        sys.exit(1)

    model = load_model(model_path)
    classes = model["classes"]
    
    calib_path = os.path.join(BASE_DIR, "data", f"{sess}_calib.json")
    csv_path = os.path.join(BASE_DIR, "data", f"{sess}.csv")
    
    if not os.path.exists(calib_path) or not os.path.exists(csv_path):
        print(f"Error: Session files not found in data/ for '{sess}'")
        sys.exit(1)

    calib = json.load(open(calib_path))
    df = pd.read_csv(csv_path)
    last_take = df["take"].max()
    
    frames = {c: df[(df["label"] == c) & (df["take"] == last_take)][RAW].values for c in classes}
    rec = Recognizer(classes)
    
    ok = 0
    false_fires = 0

    print(f"\nReplaying session '{sess}' (Take {last_take})...\n")
    print(f"{'Gesture':<12}{'Fired':<14}{'After (s)':<12}{'Result'}")
    print("-" * 46)

    for c in classes:
        if c == "neutral":
            continue
        if c not in frames or len(frames[c]) == 0:
            print(f"{c:<12}{'-':<14}{'-':<12}NO DATA")
            continue

        fired = []
        for seg_name, seg in (("neutral", frames.get("neutral", np.zeros((60, 11)))[:60]), (c, frames[c][:80])):
            for i, (feat, motion) in enumerate(make_windows(seg, calib)):
                k = rec.update(predict_proba(model, feat), motion > model["motion_max"])
                if k is not None:
                    t = (i * STEP + WINDOW) / FPS
                    fired.append((classes[k], seg_name, t))

        good = [f for f in fired if f[1] == c and f[0] == c]
        bad = [f for f in fired if f[1] != c or f[0] != c]
        false_fires += len(bad)

        is_success = (len(good) == 1 and len(bad) == 0)
        if is_success:
            ok += 1

        t_txt = f"{good[0][2]:.2f}" if good else "-"
        fired_txt = fired[0][0] if fired else "-"
        status = "OK" if is_success else "CHECK"
        print(f"{c:<12}{fired_txt:<14}{t_txt:<12}{status}")

    n = len(classes) - 1
    print("-" * 46)
    print(f"Correct single fires: {ok}/{n} | False or repeated fires: {false_fires}\n")

if __name__ == "__main__":
    main()

