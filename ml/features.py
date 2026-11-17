"""features.py - the ONE definition of how raw frames become model inputs.
Extracts 8 features: 5 normalized flex sensor values (0 = open, 1 = fist) 
plus 3-axis gravity vector (ax, ay, az in g). Also computes motion gate.
"""

import numpy as np

WINDOW = 8          # frames per window: 0.4 s at 20 frames/s
STEP = 2            # frames between windows: 10 windows/s
MOTION_MAX = 60.0   # deg/s: above this the hand is moving, not held still
MIN_SPAN = 30.0     # ADC counts: minimum open-to-fist span allowed in calibration
N_FEATURES = 8      # 5 flex (0..1) + gravity vector ax, ay, az (g)

# Raw frame layout: [f1..f5, ax, ay, az, gx, gy, gz] (11 values)

def calib_from_frames(open_flex, fist_flex):
    """open_flex, fist_flex: arrays (n, 5) of raw ADC counts."""
    return {
        "open": np.median(np.asarray(open_flex, float), axis=0).tolist(),
        "fist": np.median(np.asarray(fist_flex, float), axis=0).tolist(),
    }

def normalize_flex(raw5, calib):
    """0.0 = open hand, 1.0 = full fist, whatever the voltage direction."""
    o = np.asarray(calib["open"], float)
    f = np.asarray(calib["fist"], float)
    span = f - o
    span = np.where(np.abs(span) < MIN_SPAN, np.where(span < 0, -MIN_SPAN, MIN_SPAN), span)
    return np.clip((np.asarray(raw5, float) - o) / span, -0.2, 1.2)

def window_features(win, calib):
    """win: array (n, 11). Returns (features[8], motion_deg_per_s)."""
    win = np.asarray(win, float)
    flex = normalize_flex(win[:, :5].mean(axis=0), calib)
    grav = np.clip(win[:, 5:8].mean(axis=0), -1.5, 1.5)
    motion = float(np.sqrt((win[:, 8:11] ** 2).sum(axis=1)).mean())
    return np.concatenate([flex, grav]), motion

def make_windows(frames, calib):
    """frames: array (n, 11). Yields (features, motion) for sliding windows."""
    frames = np.asarray(frames, float)
    for i in range(0, len(frames) - WINDOW + 1, STEP):
        yield window_features(frames[i:i + WINDOW], calib)

