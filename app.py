#!/usr/bin/env python3
# =============================================================
# app.py — Kiosk Web UI backend
# Flask app that serves index.html and provides an API to
# read and write kiosk.json (the URL list).
# Runs on port 5000, accessible from any device on the network.
# =============================================================

from flask import Flask, jsonify, request, send_from_directory
import json, os

app    = Flask(__name__)
CONFIG = "/opt/kiosk/kiosk.json"
DEFAULT = {"urls": [{"url": "https://example.com", "duration": 30}]}

def load():
    if not os.path.exists(CONFIG):
        return DEFAULT
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except Exception:
        return DEFAULT

def save(data):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/")
def index():
    return send_from_directory("/opt/kiosk/web", "index.html")

@app.route("/api/urls", methods=["GET"])
def get_urls():
    return jsonify(load().get("urls", []))

@app.route("/api/urls", methods=["POST"])
def post_urls():
    data = request.get_json(force=True)
    if not isinstance(data, list):
        return jsonify({"error": "expected a JSON array"}), 400
    cfg = load()
    cfg["urls"] = data
    save(cfg)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
