#!/usr/bin/env python3
"""Make synthetic recordings so you can validate train.py, parity_test.py, and replay.py
before physical glove assembly and real data collection.

Note: Delete data/fake* before real training so the final model doesn't train on synthetic data.
"""

import json
import os
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

rng = np.random.default_rng(0)
OPEN, FIST = 1170.0, 480.0   # Typical ADC counts with 10k divider (higher voltage when flat)

# Finger bend (0.0=open, 0.5=half, 1.0=bent) for [thumb, index, middle, ring, little],
# plus expected gravity vector (ax, ay, az)
G = {
    "neutral":   ([0.0, 0.0, 0.0, 0.0, 0.0], (0.0, 0.0, 1.0)),
    "hello":     ([0.0, 0.0, 0.0, 0.0, 0.0], (1.0, 0.0, 0.1)),
    "thank_you": ([0.0, 0.0, 0.0, 0.0, 0.0], (0.0, 0.0, -1.0)),
    "yes":       ([1.0, 1.0, 1.0, 1.0, 1.0], (0.0, 0.0, 1.0)),
    "no":        ([1.0, 0.0, 0.0, 1.0, 1.0], (0.0, 0.0, 1.0)),
    "please":    ([0.0, 1.0, 1.0, 1.0, 1.0], (0.0, 0.0, 1.0)),
    "water":     ([1.0, 0.0, 0.0, 0.0, 1.0], (0.9, 0.0, 0.3)),
    "food":      ([0.5, 0.5, 0.5, 0.5, 0.5], (0.7, 0.0, 0.7)),
    "need_help": ([0.0, 1.0, 1.0, 1.0, 0.0], (1.0, 0.0, 0.1)),
    "toilet":    ([1.0, 0.0, 1.0, 1.0, 0.0], (0.0, 0.0, 1.0)),
}

def main():
    vocab_path = os.path.join(BASE_DIR, "vocab.json")
    vocab = json.load(open(vocab_path))

    for sess, drift in [("fake1", 0.0), ("fake2", 40.0)]:
        open_v = OPEN + drift
        fist_v = FIST + drift
        calib = {"open": [open_v] * 5, "fist": [fist_v] * 5}
        
        calib_file = os.path.join(DATA_DIR, f"{sess}_calib.json")
        with open(calib_file, "w") as f:
            json.dump(calib, f, indent=2)

        rows = ["session,label,take,ms,f1,f2,f3,f4,f5,ax,ay,az,gx,gy,gz"]
        for take in (1, 2, 3):
            for cls in vocab["classes"]:
                bend, grav = G[cls]
                for k in range(140):
                    f = [open_v + b * (fist_v - open_v) + rng.normal(0, 18) 
                         for b in np.array(bend) + rng.normal(0, 0.06, 5)]
                    a = np.array(grav) + rng.normal(0, 0.06, 3)
                    gy = rng.normal(0, 6, 3)
                    
                    row_vals = [sess, cls, take, k * 50] + \
                               [round(v, 1) for v in f] + \
                               [round(v, 3) for v in a] + \
                               [round(v, 1) for v in gy]
                    rows.append(",".join(map(str, row_vals)))

        csv_file = os.path.join(DATA_DIR, f"{sess}.csv")
        with open(csv_file, "w") as f:
            f.write("\n".join(rows))
            
    print("Synthetic data generated successfully:")
    print(f" - {os.path.join(DATA_DIR, 'fake1.csv')}")
    print(f" - {os.path.join(DATA_DIR, 'fake2.csv')}")

if __name__ == "__main__":
    main()

