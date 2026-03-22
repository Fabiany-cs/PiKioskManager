#!/usr/bin/env python3
# =============================================================
# app.py — Kiosk Web UI backend
# Flask app with session-based authentication.
# Credentials are stored in /opt/kiosk/auth.json (hashed).
# Sessions last 24 hours.
# =============================================================

from flask import (Flask, jsonify, request, send_from_directory,
                   session, redirect, url_for)
import json, os, subprocess, hashlib, secrets
from datetime import timedelta

app = Flask(__name__)

# Secret key signs the session cookie — generated once at startup.
# In production you'd persist this, but for a local Pi this is fine.
# If the Pi reboots, users just need to log in again.
app.secret_key        = secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(hours=24)

CONFIG = "/opt/kiosk/kiosk.json"
STATE  = "/opt/kiosk/state.json"
AUTH   = "/opt/kiosk/auth.json"

DEFAULT_CONFIG = {"urls": [{"url": "https://example.com", "duration": 30, "enabled": True}]}

# ── helpers ───────────────────────────────────────────────────

def hash_password(password):
    """SHA-256 hash of the password — same method used in setup-kiosk.sh."""
    return hashlib.sha256(password.encode()).hexdigest()

def load_auth():
    try:
        with open(AUTH) as f:
            return json.load(f)
    except Exception:
        return {}

def is_logged_in():
    return session.get("authenticated") is True

def load_config():
    if not os.path.exists(CONFIG):
        return DEFAULT_CONFIG
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG

def save_config(data):
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

# ── auth routes ───────────────────────────────────────────────

@app.route("/login", methods=["GET"])
def login_page():
    if is_logged_in():
        return redirect("/")
    return send_from_directory("/opt/kiosk/web", "login.html")

@app.route("/login", methods=["POST"])
def login_submit():
    data     = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "")

    auth = load_auth()

    if (username == auth.get("username") and
            hash_password(password) == auth.get("password_hash")):
        session.permanent = True
        session["authenticated"] = True
        return jsonify({"ok": True})

    return jsonify({"ok": False, "error": "Invalid username or password"}), 401

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

# ── protected routes ──────────────────────────────────────────

@app.route("/")
def index():
    if not is_logged_in():
        return redirect("/login")
    return send_from_directory("/opt/kiosk/web", "index.html")

@app.route("/api/urls", methods=["GET"])
def get_urls():
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(load_config().get("urls", []))

@app.route("/api/urls", methods=["POST"])
def post_urls():
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True)
    if not isinstance(data, list):
        return jsonify({"error": "expected a JSON array"}), 400
    cfg = load_config()
    cfg["urls"] = data
    save_config(cfg)
    return jsonify({"ok": True})

@app.route("/api/state", methods=["GET"])
def get_state():
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(load_state())

@app.route("/api/pause", methods=["POST"])
def pause():
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    data   = request.get_json(force=True)
    paused = data.get("paused", False)
    update = {"paused": paused}
    if paused and "pinned_index" in data:
        update["pinned_index"] = data["pinned_index"]
    write_state(update)
    return jsonify({"ok": True, "paused": paused})

@app.route("/api/restart", methods=["POST"])
def restart():
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    try:
        subprocess.run(["pkill", "-f", "kiosk.py"], capture_output=True)
        import time
        time.sleep(1)
        write_state({"paused": False, "index": -1, "url": ""})
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

@app.route("/api/change-password", methods=["POST"])
def change_password():
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    data         = request.get_json(force=True)
    current_pass = data.get("current_password", "")
    new_pass     = data.get("new_password", "")

    if not new_pass or len(new_pass) < 4:
        return jsonify({"error": "New password must be at least 4 characters"}), 400

    auth = load_auth()
    if hash_password(current_pass) != auth.get("password_hash"):
        return jsonify({"error": "Current password is incorrect"}), 401

    auth["password_hash"] = hash_password(new_pass)
    os.makedirs(os.path.dirname(AUTH), exist_ok=True)
    with open(AUTH, "w") as f:
        json.dump(auth, f)
    os.chmod(AUTH, 0o600)

    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
