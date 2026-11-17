#!/usr/bin/env python3
"""Record labelled gesture data from the glove (UDP, port 4210).

Example:
  python collect.py --session day1 --seconds 8 --takes 3

Prerequisites:
  1. ESP32 glove connected to the same hotspot/network.
  2. In glove_esp32.ino, set TARGET_IP_OVERRIDE to this machine's IP.
  3. Ensure UDP port 4210 is allowed in your local firewall.
"""

import argparse
import csv
import json
import os
import random
import socket
import time
import numpy as np
from features import calib_from_frames, MIN_SPAN

PORT = 4210

def open_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT))
    s.settimeout(0.5)
    return s

def parse(data):
    """'F,seq,ms,f1..f5,ax,ay,az,gx,gy,gz' -> [ms, f1..f5, ax..gz] (12 numbers) or None"""
    p = data.decode(errors="ignore").strip().split(",")
    if len(p) != 14 or p[0] != "F":
        return None
    try:
        return [float(x) for x in p[2:]]
    except ValueError:
        return None

def flush(sock):
    sock.setblocking(False)
    try:
        while True:
            sock.recv(512)
    except (BlockingIOError, OSError):
        pass
    sock.settimeout(0.5)

def record(sock, seconds, skip=1.0):
    """Collect frames for `seconds`, dropping the first `skip` seconds (hand still settling)."""
    flush(sock)
    rows, t0 = [], time.time()
    while time.time() - t0 < seconds:
        try:
            data, _ = sock.recvfrom(512)
        except socket.timeout:
            continue
        r = parse(data)
        if r is not None and time.time() - t0 >= skip:
            rows.append(r)
    return np.array(rows, float)

def main():
    ap = argparse.ArgumentParser(description="Sign Language Glove Gesture Data Collector")
    ap.add_argument("--session", required=True, help="Session identifier (e.g. day1, day2)")
    ap.add_argument("--seconds", type=float, default=8.0, help="Recording duration per take per class")
    ap.add_argument("--takes", type=int, default=3, help="Number of takes per class")
    ap.add_argument("--only", nargs="*", help="Record only specific classes")
    a = ap.parse_args()

    vocab_path = os.path.join(os.path.dirname(__file__), "vocab.json")
    if not os.path.exists(vocab_path):
        vocab_path = "vocab.json"
    vocab = json.load(open(vocab_path))
    classes = a.only or vocab["classes"]

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    sock = open_socket()

    print("\n================ CALIBRATION ================")
    input("CALIBRATION 1/2: Hold hand OPEN and relaxed. Press Enter, then hold still for 4 s... ")
    open_rows = record(sock, 4.0)

    input("CALIBRATION 2/2: Make a tight FIST. Press Enter, then hold still for 4 s... ")
    fist_rows = record(sock, 4.0)

    if len(open_rows) < 10 or len(fist_rows) < 10:
        raise SystemExit("Error: Too few frames received. Check Wi-Fi, TARGET_IP_OVERRIDE and firewall.")

    calib = calib_from_frames(open_rows[:, 1:6], fist_rows[:, 1:6])
    spans = np.abs(np.array(calib["fist"]) - np.array(calib["open"]))
    for i, s in enumerate(spans):
        if s < 150:
            print(f"WARNING: Finger {i + 1} moved only {s:.0f} counts between open and fist. Check sensor wiring.")

    calib_file = os.path.join(data_dir, f"{a.session}_calib.json")
    with open(calib_file, "w") as f:
        json.dump(calib, f, indent=2)
    print(f"Calibration saved to {calib_file}")

    csv_path = os.path.join(data_dir, f"{a.session}.csv")
    new = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["session", "label", "take", "ms", "f1", "f2", "f3", "f4", "f5",
                        "ax", "ay", "az", "gx", "gy", "gz"])

        for take in range(1, a.takes + 1):
            order = classes[:]
            random.shuffle(order)   # Randomize sequence to prevent sequence dependency bias
            print(f"\n--- Starting Take {take}/{a.takes} ---")
            for cls in order:
                phrase = vocab["phrases"].get(cls, "(idle)")
                input(f"[{take}/{a.takes}] Pose: '{cls}' ({phrase}). Press Enter, then hold pose... ")
                rows = record(sock, a.seconds)
                if len(rows) < a.seconds * 12:
                    print(f"  Warning: Only {len(rows)} frames received. Check connection. Re-record later if needed.")
                for r in rows:
                    w.writerow([a.session, cls, take] + [f"{v:g}" for v in r])
                fh.flush()
                print(f"  Saved {len(rows)} frames for '{cls}'")

    print(f"\nDone! Session '{a.session}' saved. Record another session with --session day2.")

if __name__ == "__main__":
    main()

