#!/usr/bin/env python3
"""
message_listener.py
Real-time listener for Sign Language Glove speech events.
Captures recognized phrases over both Direct UDP (0ms local) and Firebase RTDB (cloud sync).
Displays glowing formatted terminal messages and speaks them aloud via PC audio.
"""

import socket
import threading
import time
import json
import urllib.request
import ssl
import sys
import subprocess
import os

UDP_PORT = 4210
ESP_CMD_PORT = 4211
ESP_IP = "192.168.1.25"
FIREBASE_URL = "https://shopping-e284c-default-rtdb.firebaseio.com/records.json"

RF_PHRASES = [
    "",
    "HELLO",
    "THANK YOU",
    "YES",
    "NO",
    "PLEASE",
    "WATER",
    "FOOD",
    "I NEED HELP",
    "WHERE IS THE TOILET"
]

RF_CATEGORIES = [
    "",
    "Daily needs",
    "Daily needs",
    "Daily needs",
    "Daily needs",
    "Daily needs",
    "Daily needs",
    "Daily needs",
    "Emergency",
    "Daily needs"
]

# Track announced phrases to avoid duplicate voice announcements
recent_announcements = []
announcements_lock = threading.Lock()

def speak_phrase(text):
    """Speaks phrase aloud using native Windows TTS in a background thread."""
    def _speak():
        try:
            # Try Windows PowerShell SAPI voice
            cmd = f'powershell -c "(New-Object -ComObject SAPI.SpVoice).Speak(\'{text}\')"'
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    threading.Thread(target=_speak, daemon=True).start()

def display_message(phrase, track=None, category=None, source="Direct UDP"):
    """Displays a prominent, color-coded ASCII message box in console."""
    with announcements_lock:
        now_ts = time.time()
        # Clean old history
        recent = [x for x in recent_announcements if now_ts - x["time"] < 4.0]
        recent_announcements.clear()
        recent_announcements.extend(recent)
        
        # Check if already displayed in last 3 seconds
        for item in recent_announcements:
            if item["phrase"] == phrase:
                return # Skip duplicate from dual UDP/Firebase arrival
        recent_announcements.append({"phrase": phrase, "time": now_ts})

    time_str = time.strftime("%H:%M:%S")
    is_emergency = "HELP" in phrase.upper() or category == "Emergency"

    if is_emergency:
        border = "!" * 72
        tag = "[EMERGENCY ALERT]"
    else:
        border = "=" * 72
        tag = "[SPOKEN PHRASE]"

    cat_str = f" • Category: {category}" if category else ""
    trk_str = f" • Track #{track}" if track else ""

    print(f"\n{border}")
    print(f"  📢  {tag}  >>>  \"{phrase}\"  <<<")
    print(f"  🕒  Time: {time_str}{trk_str}{cat_str}")
    print(f"  📡  Source: {source}")
    print(f"{border}\n")

    # Speak aloud
    speak_phrase(phrase)

def udp_listener_worker():
    """Listens on UDP port 4210 for real-time 'P,track,phrase' packets."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", UDP_PORT))
    except Exception as e:
        print(f"[UDP Warning] Could not bind to port {UDP_PORT}: {e}")
        return

    while True:
        try:
            data, addr = s.recvfrom(512)
            line = data.decode(errors="ignore").strip()
            p = line.split(",")
            if p[0] == "P" and len(p) >= 3:
                track = int(p[1]) if p[1].isdigit() else None
                phrase = p[2]
                cat = RF_CATEGORIES[track] if (track and track < len(RF_CATEGORIES)) else "General"
                display_message(phrase, track=track, category=cat, source=f"Direct UDP ({addr[0]})")
        except Exception:
            continue

def handshake_worker():
    """Pings ESP32 on port 4211 so it knows our PC's IP and streams telemetry."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    targets = [(ESP_IP, ESP_CMD_PORT), ("255.255.255.255", ESP_CMD_PORT), ("192.168.1.255", ESP_CMD_PORT)]
    while True:
        for ip, port in targets:
            try:
                s.sendto(b"PING", (ip, port))
            except Exception:
                pass
        time.sleep(2.5)

def firebase_poller_worker():
    """Polls Firebase RTDB /records.json every 2.0s to catch cloud uploads."""
    ctx = ssl.create_default_context()
    seen_ids = set()
    initial_loaded = False

    while True:
        try:
            req = urllib.request.Request(FIREBASE_URL, headers={"User-Agent": "SignGloveListener/1.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=3.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8")) or {}
                    if not initial_loaded:
                        # Load initial existing IDs without re-announcing them all
                        seen_ids.update(data.keys())
                        initial_loaded = True
                    else:
                        for rec_id, val in data.items():
                            if rec_id not in seen_ids and isinstance(val, dict):
                                seen_ids.add(rec_id)
                                phrase = val.get("text", "")
                                if phrase:
                                    cat = val.get("category", "Daily needs")
                                    trk = val.get("track")
                                    display_message(phrase, track=trk, category=cat, source="Firebase Cloud RTDB")
        except Exception:
            pass
        time.sleep(2.0)

def main():
    print("=" * 72)
    print("  🧤  SIGN LANGUAGE GLOVE -- REAL-TIME MESSAGE LISTENER")
    print("=" * 72)
    print(f"  • Listening on UDP Port:     {UDP_PORT} (Direct zero-latency stream)")
    print(f"  • Polling Firebase Cloud:    {FIREBASE_URL}")
    print(f"  • Target ESP32 IP:           {ESP_IP}:{ESP_CMD_PORT}")
    print(f"  • PC Voice Output:           Enabled (Native TTS)")
    print("=" * 72)
    print("  Controls:")
    print("    - Press '1'..'9' + Enter to remotely trigger test phrases on the glove")
    print("    - Press Ctrl+C to exit")
    print("------------------------------------------------------------------------\n")
    print("[STATUS] Listener active! Waiting for sign language gestures...\n")

    # Start background threads
    t_udp = threading.Thread(target=udp_listener_worker, daemon=True)
    t_udp.start()

    t_ping = threading.Thread(target=handshake_worker, daemon=True)
    t_ping.start()

    t_fb = threading.Thread(target=firebase_poller_worker, daemon=True)
    t_fb.start()

    s_cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Main interactive console loop
    while True:
        try:
            cmd = input().strip()
            if not cmd:
                continue
            if cmd.isdigit() and 1 <= int(cmd) <= 9:
                trk = int(cmd)
                phrase = RF_PHRASES[trk]
                print(f"[TEST TRIGGER] Sending remote trigger for Phrase #{trk} ('{phrase}')...")
                s_cmd.sendto(f"PLAY,{trk}".encode(), (ESP_IP, ESP_CMD_PORT))
            elif cmd.lower() in ["t", "tare"]:
                print("[CALIBRATION] Sending TARE command to zero hand...")
                s_cmd.sendto(b"TARE", (ESP_IP, ESP_CMD_PORT))
            elif cmd.lower() in ["q", "exit", "quit"]:
                break
        except (KeyboardInterrupt, EOFError):
            print("\nShutting down listener.")
            break

if __name__ == "__main__":
    main()
