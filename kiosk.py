#!/usr/bin/env python3
# =============================================================
# kiosk.py — URL cycling controller
# Controls Chromium via its remote debugging API (port 9222).
# No xdotool — uses direct HTTP calls to Chromium's own API.
# Chromium must be launched with --remote-debugging-port=9222
# =============================================================

import json, time, urllib.request, sys

CONFIG  = "/opt/kiosk/kiosk.json"
DEBUG   = "http://localhost:9222"
DEFAULT = {"urls": [{"url": "https://example.com", "duration": 30}]}

def load():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except Exception:
        return DEFAULT

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
    Most reliable method in kiosk mode — no focus or keyboard tricks needed.
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

    time.sleep(2)
    index = 0

    while True:
        cfg  = load()
        urls = cfg.get("urls", [])

        if not urls:
            time.sleep(10)
            continue

        index = index % len(urls)
        url   = urls[index].get("url", "about:blank")
        dur   = max(5, int(urls[index].get("duration", 30)))

        navigate(url)
        time.sleep(dur)
        index += 1

if __name__ == "__main__":
    main()
