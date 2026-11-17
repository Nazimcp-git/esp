#!/usr/bin/env python3
"""
web_server.py
Dedicated local web server and real-time bridge for the Sign Language Glove.
Serves the web portal on http://localhost:5000, connects to ESP32 UDP telemetry,
and bridges live speech events to connected web browsers via Server-Sent Events (SSE).
"""

import http.server
import json
import os
import socket
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

PORT = 5000
UDP_PORT = 4210
ESP_CMD_PORT = 4211
ESP_IP = "192.168.1.25"
FIREBASE_URL = "https://shopping-e284c-default-rtdb.firebaseio.com/records.json"
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "public")

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

# SSE active browser clients
sse_clients = []
sse_lock = threading.Lock()

# Recent message cache
recent_messages = []
cache_lock = threading.Lock()

def broadcast_sse(event_type, data):
    """Sends a Server-Sent Event to all open browser tabs."""
    payload = json.dumps({"type": event_type, **data})
    msg = f"data: {payload}\n\n".encode("utf-8")
    with sse_lock:
        dead = []
        for wfile in sse_clients:
            try:
                wfile.write(msg)
                wfile.flush()
            except Exception:
                dead.append(wfile)
        for d in dead:
            if d in sse_clients:
                sse_clients.remove(d)

def handle_incoming_phrase(phrase, track=None, category=None, source="Direct UDP"):
    """Records phrase and notifies all open web pages."""
    with cache_lock:
        now_ts = time.time()
        # Deduplicate if received within 3.0s
        for item in recent_messages[-10:]:
            if item["text"] == phrase and (now_ts - item["time"]) < 3.0:
                return
        msg_obj = {
            "id": f"msg-{int(now_ts*1000)}",
            "text": phrase,
            "track": track,
            "category": category or "Daily needs",
            "source": source,
            "confidence": 0.95,
            "status": "approved",
            "time": now_ts,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        recent_messages.append(msg_obj)
        if len(recent_messages) > 100:
            recent_messages.pop(0)

    print(f"\n[WEB EVENT] >>> Spoken Message: \"{phrase}\" ({source}) -> Broadcasting to web clients...")
    broadcast_sse("phrase", msg_obj)

def udp_worker():
    """Listens on UDP 4210 for ESP32 glove events and telemetry."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", UDP_PORT))
    except Exception as e:
        print(f"[UDP Warning] Could not bind port {UDP_PORT}: {e}")
        return

    print(f"[UDP Bridge] Listening on port {UDP_PORT}...")
    while True:
        try:
            data, addr = s.recvfrom(512)
            line = data.decode(errors="ignore").strip()
            p = line.split(",")
            # Speech event: P,track,phrase
            if p[0] == "P" and len(p) >= 3:
                track = int(p[1]) if p[1].isdigit() else None
                phrase = p[2]
                cat = RF_CATEGORIES[track] if (track and track < len(RF_CATEGORIES)) else "General"
                handle_incoming_phrase(phrase, track=track, category=cat, source=f"Direct UDP ({addr[0]})")
            # Telemetry frame: F,seq,ms,f1..f5,ax..gz
            elif p[0] == "F" and len(p) == 14:
                try:
                    f = [float(x) for x in p[3:8]]
                    acc = [float(x) for x in p[8:11]]
                    broadcast_sse("telemetry", {"f": f, "acc": acc, "rssi": -65})
                except Exception:
                    pass
        except Exception:
            continue

def handshake_worker():
    """Sends handshake PING to ESP32 every 2.5s so telemetry flows to PC."""
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

def firebase_poller():
    """Polls Firebase RTDB for cloud phrase updates."""
    ctx = ssl.create_default_context()
    seen_keys = set()
    first_pass = True

    while True:
        try:
            req = urllib.request.Request(FIREBASE_URL, headers={"User-Agent": "SignGloveServer/1.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=3.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8")) or {}
                    if first_pass:
                        seen_keys.update(data.keys())
                        first_pass = False
                    else:
                        for k, v in data.items():
                            if k not in seen_keys and isinstance(v, dict):
                                seen_keys.add(k)
                                text = v.get("text", "")
                                if text:
                                    cat = v.get("category", "Daily needs")
                                    trk = v.get("track")
                                    handle_incoming_phrase(text, track=trk, category=cat, source="Firebase Cloud RTDB")
        except Exception:
            pass
        time.sleep(2.0)

class GloveHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        # Suppress routine static asset HTTP GET logs
        if self.path.startswith("/api/"):
            super().log_message(format, *args)

    def do_GET(self):
        url_parts = urllib.parse.urlparse(self.path)
        path = url_parts.path

        # 1. Server-Sent Events Endpoint
        if path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            with sse_lock:
                sse_clients.append(self.wfile)

            # Send initial message history
            with cache_lock:
                init_data = json.dumps({"type": "history", "messages": recent_messages})
            try:
                self.wfile.write(f"data: {init_data}\n\n".encode("utf-8"))
                self.wfile.flush()
                while True:
                    time.sleep(15)
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                with sse_lock:
                    if self.wfile in sse_clients:
                        sse_clients.remove(self.wfile)
            return

        # 2. Remote Trigger API
        if path == "/api/trigger":
            query = urllib.parse.parse_qs(url_parts.query)
            track = query.get("track", [None])[0] or query.get("phrase", [None])[0]
            if track and track.isdigit():
                t = int(track)
                if 1 <= t <= 9:
                    phrase = RF_PHRASES[t]
                    cat = RF_CATEGORIES[t]
                    # Trigger ESP32 over UDP
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.sendto(f"PLAY,{t}".encode(), (ESP_IP, ESP_CMD_PORT))
                        sock.close()
                    except Exception:
                        pass
                    # Broadcast to web UI
                    handle_incoming_phrase(phrase, track=t, category=cat, source="Web Remote Trigger")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "phrase": phrase}).encode("utf-8"))
                    return

            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "Invalid track number"}')
            return

        # 3. Default: Serve static files from web/public/
        if path == "/" or path == "":
            self.path = "/index.html"
        return super().do_GET()

def main():
    print("=" * 72)
    print("  🧤  SIGN LANGUAGE GLOVE -- WEB PORTAL & LIVE SPEECH BRIDGE")
    print("=" * 72)
    print(f"  • Web UI URL:          http://localhost:{PORT}")
    print(f"  • UDP Listener:        Port {UDP_PORT}")
    print(f"  • ESP32 Target:        {ESP_IP}:{ESP_CMD_PORT}")
    print(f"  • Web Directory:       {WEB_DIR}")
    print("=" * 72)

    # Start UDP listener
    t_udp = threading.Thread(target=udp_worker, daemon=True)
    t_udp.start()

    # Start ESP32 handshake pinger
    t_ping = threading.Thread(target=handshake_worker, daemon=True)
    t_ping.start()

    # Start Firebase cloud sync poller
    t_fb = threading.Thread(target=firebase_poller, daemon=True)
    t_fb.start()

    # Start HTTP server
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), GloveHTTPHandler)
    print(f"[STATUS] Web server running at http://localhost:{PORT}")
    print("Press Ctrl+C to shut down.\n")

    # Open browser automatically after 1s
    def _open():
        time.sleep(1.0)
        webbrowser.open(f"http://localhost:{PORT}")
    threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down web server.")
        server.server_close()

if __name__ == "__main__":
    main()
