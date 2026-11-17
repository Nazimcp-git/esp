#!/usr/bin/env python3
"""
udp_listen.py  --  Bench test listener for ESP32 UDP telemetry.
Runs on a laptop/PC connected to the same phone hotspot or Wi-Fi network.
Listens on UDP port 4210, prints frames per second (FPS), packet loss, and sensor telemetry.

Usage:
  1. Find your computer's local IP (e.g. ipconfig on Windows, ifconfig on Linux).
  2. Set TARGET_IP_OVERRIDE in glove_esp32.ino to this IP during bench testing.
  3. Run: python udp_listen.py
"""

import socket
import time

PORT = 4210

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT))
    s.settimeout(2.0)
    
    print(f"Listening for ESP32 glove telemetry on UDP port {PORT}...")
    print("Press Ctrl+C to stop.\n")
    
    n = 0
    t0 = time.time()
    last_seq = None
    lost = 0
    
    while True:
        try:
            data, addr = s.recvfrom(256)
        except socket.timeout:
            print("No data received: check TARGET_IP_OVERRIDE in firmware, firewall rules, and Wi-Fi connection.")
            continue
        except KeyboardInterrupt:
            print("\nStopped.")
            break
            
        p = data.decode(errors="ignore").strip().split(",")
        if p[0] == "P" and len(p) >= 3:
            print(f"\n>>> [GESTURE RECOGNIZED]: '{p[2]}' (Track {p[1]}) <<<\n")
            continue
        if len(p) != 14 or p[0] != "F":
            print("Malformed frame:", data)
            continue
            
        try:
            seq = int(p[1])
            uptime_ms = int(p[2])
            flex = [float(x) for x in p[3:8]]
            acc = [float(x) for x in p[8:11]]
            gyro = [float(x) for x in p[11:14]]
        except ValueError:
            print("Failed to parse numeric fields:", data)
            continue
            
        if last_seq is not None and seq > last_seq + 1:
            lost += (seq - last_seq - 1)
        last_seq = seq
        n += 1
        
        now = time.time()
        if now - t0 >= 1.0:
            fps = n / (now - t0)
            flex_str = "[" + ", ".join(f"{v:4.0f}" for v in flex) + "]"
            acc_str = "[" + ", ".join(f"{v:5.2f}" for v in acc) + "]"
            print(f"{fps:4.1f} fps | lost={lost:3d} | seq={seq:6d} | flex={flex_str} | acc={acc_str} | from={addr[0]}")
            n = 0
            t0 = now

if __name__ == "__main__":
    main()

