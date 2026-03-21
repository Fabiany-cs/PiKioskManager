#!/usr/bin/env python3
# =============================================================
# kiosk.py — URL cycling controller
# Controls Chromium via its remote debugging API (port 9222).
# No xdotool — uses direct HTTP calls to Chromium's own API.
# Chromium must be launched with --remote-debugging-port=9222
# =============================================================

import json, time, urllib.request, sys

CONFIG  = "/opt/kiosk/kiosk.json"
STATE   = "/opt/kiosk/state.json"
DEBUG   = "http://localhost:9222"
DEFAULT = {"urls": [{"url": "https://example.com", "duration": 30, "enabled": True}]}

def load_config():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except Exception:
        return DEFAULT

def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}

def write_state(data):
    """Merge new data into existing state and write it back."""
    try:
        current = load_state()
        current.update(data)
        with open(STATE, "w") as f:
            json.dump(current, f)
    except Exception:
        pass

def wait_for_chromium():
    print("[kiosk] Waiting for Chromium debug port...")
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{DEBUG}/json", timeout=3)
            print("[kiosk] Chromium is ready.")
            return True
        except Exception:
            time.sleep(2)
    return False

def navigate(url):
    """
    Open a new tab to the URL and close the previous tab.
    Most reliable in kiosk mode — no focus or keyboard tricks needed.
    """
    try:
        with urllib.request.urlopen(f"{DEBUG}/json", timeout=5) as r:
            tabs = json.loads(r.read())

        old_tab = next((t for t in tabs if t.get("type") == "page"), None)
        old_id  = old_tab["id"] if old_tab else None

        req = urllib.request.Request(f"{DEBUG}/json/new?{url}", method="PUT")
        urllib.request.urlopen(req, timeout=5)
        time.sleep(0.5)

        if old_id:
            try:
                urllib.request.urlopen(f"{DEBUG}/json/close/{old_id}", timeout=5)
            except Exception:
                pass

        print(f"[kiosk] -> {url}")

    except Exception as e:
        print(f"[kiosk] navigate error: {e}", file=sys.stderr)

def main():
    if not wait_for_chromium():
        print("[kiosk] Chromium debug port never opened. Giving up.", file=sys.stderr)
        sys.exit(1)

    # Mark ourselves as running
    write_state({"running": True, "paused": False, "index": -1, "url": ""})
    time.sleep(2)
    index = 0

    while True:
        cfg   = load_config()
        state = load_state()
        urls  = cfg.get("urls", [])

        # Check if we're paused — if so, stay on the pinned URL
        if state.get("paused", False):
            pinned = state.get("pinned_index", -1)
            if pinned >= 0 and pinned < len(urls):
                entry = urls[pinned]
                url   = entry.get("url", "about:blank")
                navigate(url)
                write_state({"index": pinned, "url": url})
            # Sleep briefly then re-check state — allows unpausing to take effect quickly
            time.sleep(3)
            continue

        # Build list of (original_index, entry) for enabled entries only
        active = [(i, e) for i, e in enumerate(urls) if e.get("enabled", True)]

        if not active:
            write_state({"index": -1, "url": ""})
            time.sleep(10)
            continue

        index = index % len(active)
        real_index, entry = active[index]

        url = entry.get("url", "about:blank")
        dur = max(5, int(entry.get("duration", 30)))

        write_state({"index": real_index, "url": url})
        navigate(url)
        time.sleep(dur)
        index += 1

if __name__ == "__main__":
    main()
