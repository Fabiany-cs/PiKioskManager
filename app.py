#!/usr/bin/env python3
# =============================================================
# app.py — Kiosk Web UI backend
# Flask app that serves index.html and provides an API to
# read and write kiosk.json (the URL list).
# Runs on port 5000, accessible from any device on the network.
# =============================================================

from flask import Flask, jsonify, request, send_from_directory
import json, os, subprocess, signal

app    = Flask(__name__)
CONFIG = "/opt/kiosk/kiosk.json"
STATE  = "/opt/kiosk/state.json"
DEFAULT = {"urls": [{"url": "https://example.com", "duration": 30, "enabled": True}]}

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

def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}

def write_state(data):
    current = load_state()
    current.update(data)
    with open(STATE, "w") as f:
        json.dump(current, f)

def get_kiosk_user():
    """Find the user who owns the kiosk process — needed to relaunch correctly."""
    try:
        result = subprocess.run(
            ["ps", "-eo", "user,command"],
            capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "kiosk.py" in line:
                return line.split()[0]
    except Exception:
        pass
    return "monitor"

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

@app.route("/api/state", methods=["GET"])
def get_state():
    """Returns current kiosk state — active index, paused flag, running flag."""
    return jsonify(load_state())

@app.route("/api/pause", methods=["POST"])
def pause():
    """
    Pause or resume the kiosk cycle.
    POST body: {"paused": true, "pinned_index": 2}
               {"paused": false}
    """
    data = request.get_json(force=True)
    paused = data.get("paused", False)
    update = {"paused": paused}
    if paused and "pinned_index" in data:
        update["pinned_index"] = data["pinned_index"]
    write_state(update)
    return jsonify({"ok": True, "paused": paused})

@app.route("/api/restart", methods=["POST"])
def restart():
    """
    Kill kiosk.py and relaunch it under the correct user with DISPLAY=:0.
    The kiosk-ui service runs as the kiosk user so we can call subprocess directly.
    """
    try:
        # Kill existing kiosk.py process
        result = subprocess.run(
            ["pkill", "-f", "kiosk.py"],
            capture_output=True)

        # Small delay to let the process fully exit
        import time
        time.sleep(1)

        # Clear paused state on restart
        write_state({"paused": False, "index": -1, "url": ""})

        # Relaunch kiosk.py with the correct environment
        # We use the same user that's running this Flask process
        kiosk_user = get_kiosk_user()
        home = f"/home/{kiosk_user}"

        subprocess.Popen(
            ["python3", "/opt/kiosk/kiosk.py"],
            env={
                "DISPLAY": ":0",
                "XAUTHORITY": f"{home}/.Xauthority",
                "HOME": home,
                "USER": kiosk_user,
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
