#!/usr/bin/env python3
"""udp_3d_server.py -- Ultra-low-latency 3D Glove Visualizer Bridge.

Listens for ESP32 UDP telemetry packets on port 4210 (identical to udp_listen.py)
and streams them directly to an interactive 3D WebGL visualizer in your browser.

- Latency: < 15 ms (Direct Local UDP -> WebGL 60 FPS)
- Zero dependencies: Uses 100% standard Python library (no extra pip install needed).
- Automatically opens http://localhost:8080 in your default browser.

Usage:
  1. Ensure ESP32 glove is sending to your computer's IP (TARGET_IP_OVERRIDE).
  2. Run: python udp_3d_server.py
"""

import http.server
import json
import os
import socket
import threading
import time
import webbrowser

UDP_PORT = 4210
HTTP_PORT = 8080
HTML_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glove_3d_viewer.html")

# Thread-safe list of active SSE client response streams
clients_lock = threading.Lock()
active_clients = []

# Latest frame cache
last_frame_json = None

def parse_udp_frame(data):
    """Parses 'F,seq,ms,f1..f5,ax,ay,az,gx,gy,gz' or 'P,track,phrase'."""
    p = data.decode(errors="ignore").strip().split(",")
    if not p:
        return None
        
    # Speech phrase event: P,track,phrase
    if p[0] == "P" and len(p) >= 3:
        try:
            return {
                "type": "phrase",
                "track": int(p[1]),
                "phrase": p[2]
            }
        except ValueError:
            return None

    # Telemetry frame: F,seq,ms,f1..f5,ax,ay,az,gx,gy,gz
    if len(p) != 14 or p[0] != "F":
        return None
    try:
        return {
            "type": "frame",
            "seq": int(p[1]),
            "ms": int(p[2]),
            "f1": float(p[3]),
            "f2": float(p[4]),
            "f3": float(p[5]),
            "f4": float(p[6]),
            "f5": float(p[7]),
            "ax": float(p[8]),
            "ay": float(p[9]),
            "az": float(p[10]),
            "gx": float(p[11]),
            "gy": float(p[12]),
            "gz": float(p[13])
        }
    except ValueError:
        return None

def broadcast_frame(frame_dict):
    """Broadcasts frame to all connected 3D WebGL browser sessions."""
    global last_frame_json
    payload = json.dumps(frame_dict)
    last_frame_json = payload
    msg = f"data: {payload}\n\n".encode("utf-8")
    
    with clients_lock:
        to_remove = []
        for wfile in active_clients:
            try:
                wfile.write(msg)
                wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                to_remove.append(wfile)
        for dead in to_remove:
            active_clients.remove(dead)

def udp_receiver_worker():
    """Listens on UDP port 4210 and broadcasts to web visualizer."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", UDP_PORT))
    
    print(f"[UDP] Listening for ESP32 glove on port {UDP_PORT}...")
    
    fps_count = 0
    t0 = time.time()
    last_seq = None
    lost = 0
    
    while True:
        try:
            data, addr = sock.recvfrom(512)
        except Exception as e:
            continue
            
        frame = parse_udp_frame(data)
        if not frame:
            continue

        # Handle speech event immediately
        if frame.get("type") == "phrase":
            print(f"\n[SPEECH EVENT] *** GESTURE RECOGNIZED: '{frame['phrase']}' (Speaking aloud on 3D viewer) ***\n")
            broadcast_frame(frame)
            continue
            
        seq = frame["seq"]
        if last_seq is not None and seq > last_seq + 1:
            lost += (seq - last_seq - 1)
        last_seq = seq
        fps_count += 1
        
        # Broadcast to 3D viewer
        broadcast_frame(frame)
        
        now = time.time()
        if now - t0 >= 1.0:
            fps = fps_count / (now - t0)
            print(f"[3D Stream] {fps:4.1f} FPS | Lost: {lost} | From: {addr[0]} | F1..F5: [{frame['f1']:.0f}, {frame['f2']:.0f}, {frame['f3']:.0f}, {frame['f4']:.0f}, {frame['f5']:.0f}]")
            fps_count = 0
            t0 = now

class VisualizerHTTPHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            if not os.path.exists(HTML_FILE_PATH):
                self.send_error(404, "glove_3d_viewer.html not found")
                return
            with open(HTML_FILE_PATH, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            
        elif self.path == "/events":
            # Server-Sent Events (SSE) stream for ultra-low latency browser updates
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            with clients_lock:
                active_clients.append(self.wfile)
                print(f"[HTTP] 3D Viewer client connected (Total active: {len(active_clients)})")
                
            # Send initial state if available
            if last_frame_json:
                try:
                    self.wfile.write(f"data: {last_frame_json}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except OSError:
                    pass
                    
            # Keep stream connection open
            try:
                while True:
                    time.sleep(1)
            except (ConnectionResetError, BrokenPipeError, KeyboardInterrupt):
                pass
            finally:
                with clients_lock:
                    if self.wfile in active_clients:
                        active_clients.remove(self.wfile)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        # Suppress standard HTTP request spam to keep terminal clean
        pass

def udp_handshake_worker():
    """Periodically sends handshake packets so the ESP32 knows where to stream telemetry."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    targets = [("255.255.255.255", 4211), ("192.168.1.255", 4211), ("192.168.1.25", 4211)]
    while True:
        for ip, port in targets:
            try:
                sock.sendto(b"PING", (ip, port))
            except Exception:
                pass
        time.sleep(2.0)

def main():
    # 1. Start UDP receiver thread and handshake pinger
    t_udp = threading.Thread(target=udp_receiver_worker, daemon=True)
    t_udp.start()
    t_ping = threading.Thread(target=udp_handshake_worker, daemon=True)
    t_ping.start()
    
    # 2. Start HTTP server
    server = http.server.ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), VisualizerHTTPHandler)
    print(f"\n=======================================================")
    print(f"  3D GLOVE LIVE VISUALIZER RUNNING AT:")
    print(f"  --> http://localhost:{HTTP_PORT}")
    print(f"=======================================================\n")
    
    # 3. Open browser automatically
    def open_browser():
        time.sleep(0.8)
        webbrowser.open(f"http://localhost:{HTTP_PORT}")
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down 3D visualizer server.")
        server.server_close()

if __name__ == "__main__":
    main()
