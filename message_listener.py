#!/usr/bin/env python3
"""
Root launcher for the Sign Language Glove Message Listener.
Usage:
    python message_listener.py
"""
import os
import sys

target = os.path.join(os.path.dirname(__file__), "firmware", "tools", "message_listener.py")
if __name__ == "__main__":
    if os.path.exists(target):
        import runpy
        runpy.run_path(target, run_name="__main__")
    else:
        print(f"Error: {target} not found")
