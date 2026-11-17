#!/usr/bin/env python3
"""
live_monitor.py
Real-time console dashboard for ESP32 Sign Language Glove.
Shows exact ADC raw counts, bend percentage, IMU pitch/roll, and Wi-Fi link.
"""

import socket
import time
import sys

UDP_PORT = 4210
ESP_PORT = 4211
ESP_IP = "192.168.1.25"

def main():
    s_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s_recv.bind(("0.0.0.0", UDP_PORT))
    s_recv.settimeout(1.0)
    
    s_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print("=" * 75)
    print("  ESP32 SIGN LANGUAGE GLOVE -- LIVE HARDWARE MONITOR")
    print(f"  ESP32 Target: {ESP_IP}:{ESP_PORT} | Listening on port {UDP_PORT}")
    print("=" * 75)
    print("Press Ctrl+C to exit.\n")
    
    last_ping = 0
    
    while True:
        now = time.time()
        # Keep handshake active
        if now - last_ping > 2.0:
            last_ping = now
            try:
                s_send.sendto(b"PING", (ESP_IP, ESP_PORT))
                s_send.sendto(b"PING", ("255.255.255.255", ESP_PORT))
            except Exception:
                pass
                
        try:
            data, addr = s_recv.recvfrom(512)
        except socket.timeout:
            print("[WAITING] No UDP packet received yet. Retrying handshake...", end="\r")
            continue
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break
            
        line = data.decode(errors="ignore").strip()
        p = line.split(",")
        
        if p[0] == "P" and len(p) >= 3:
            print(f"\n{'*'*70}")
            print(f"  >>> [SPEECH TRIGGERED]: '{p[2]}' (Track {p[1]}) <<<")
            print(f"{'*'*70}\n")
            continue
            
        if p[0] == "F" and len(p) == 14:
            try:
                seq = int(p[1])
                ms = int(p[2])
                f = [float(x) for x in p[3:8]]
                acc = [float(x) for x in p[8:11]]
                gyro = [float(x) for x in p[11:14]]
                
                # Check status of each finger
                def fmt(v):
                    if v < 120:
                        return " DISC"
                    return f"{v:4.0f}"
                        
                sys.stdout.write(
                    f"\r[SEQ {seq:5d}] Th:{fmt(f[0])} | In:{fmt(f[1])} | Mid:{fmt(f[2])} | Rng:{fmt(f[3])} | Pnk:{fmt(f[4])} "
                    f"| Acc:[{acc[0]:+4.1f},{acc[1]:+4.1f},{acc[2]:+4.1f}]"
                )
                sys.stdout.flush()
            except ValueError:
                pass

if __name__ == "__main__":
    main()
