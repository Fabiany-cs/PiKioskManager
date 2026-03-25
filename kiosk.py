#!/usr/bin/env python3
# =============================================================
# kiosk.py — URL cycling controller
# Controls Chromium via its remote debugging API (port 9222).
# Supports per-URL zoom level via Page.setZoomFactor CDP command.
# Chromium must be launched with --remote-debugging-port=9222
# =============================================================

import json, time, urllib.request, sys, threading

CONFIG  = "/opt/kiosk/kiosk.json"
STATE   = "/opt/kiosk/state.json"
DEBUG   = "http://localhost:9222"
DEFAULT = {"urls": [{"url": "https://example.com", "duration": 30, "enabled": True, "zoom": 100}]}

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

def get_page_tab():
    """Get the current page tab from Chromium debug API."""
    try:
        with urllib.request.urlopen(f"{DEBUG}/json", timeout=5) as r:
            tabs = json.loads(r.read())
        return next((t for t in tabs if t.get("type") == "page"), None)
    except Exception:
        return None

def set_zoom(zoom_percent):
    """
    Set the zoom level on the current tab using the Page.setZoomFactor
    CDP command via WebSocket. zoom_percent is an integer like 75 or 100.
    Falls back silently if websocket-client isn't installed.
    """
    try:
        import websocket
        tab = get_page_tab()
        if not tab:
            return
        ws_url = tab.get("webSocketDebuggerUrl", "")
        if not ws_url:
            return

        zoom_factor = zoom_percent / 100.0

        result = {}
        def _send():
            try:
                ws = websocket.create_connection(ws_url, timeout=8)
                ws.send(json.dumps({
                    "id": 1,
                    "method": "Page.setZoomFactor",
                    "params": {"zoomFactor": zoom_factor}
                }))
                ws.recv()
                ws.close()
                result["ok"] = True
            except Exception as e:
                result["err"] = str(e)

        t = threading.Thread(target=_send)
        t.start()
        t.join(timeout=10)

        if result.get("ok"):
            print(f"[kiosk] zoom set to {zoom_percent}%")
        elif "err" in result:
            print(f"[kiosk] zoom error: {result['err']}", file=sys.stderr)

    except ImportError:
        # websocket-client not installed — zoom silently skipped
        pass
    except Exception as e:
        print(f"[kiosk] zoom error: {e}", file=sys.stderr)

def navigate(url, zoom=100):
    """
    Open a new tab to the URL, close the previous tab,
    then apply the zoom level.
    """
    try:
        with urllib.request.urlopen(f"{DEBUG}/json", timeout=5) as r:
            tabs = json.loads(r.read())

        old_tab = next((t for t in tabs if t.get("type") == "page"), None)
        old_id  = old_tab["id"] if old_tab else None

        req = urllib.request.Request(f"{DEBUG}/json/new?{url}", method="PUT")
        urllib.request.urlopen(req, timeout=5)

        # Wait for page to load before setting zoom
        time.sleep(1.5)

        if old_id:
            try:
                urllib.request.urlopen(f"{DEBUG}/json/close/{old_id}", timeout=5)
            except Exception:
                pass

        # Apply zoom after navigation
        if zoom != 100:
            set_zoom(zoom)

        print(f"[kiosk] -> {url} (zoom: {zoom}%)")

    except Exception as e:
        print(f"[kiosk] navigate error: {e}", file=sys.stderr)

def main():
    if not wait_for_chromium():
        print("[kiosk] Chromium debug port never opened. Giving up.", file=sys.stderr)
        sys.exit(1)

    write_state({"running": True, "paused": False, "index": -1, "url": ""})
    time.sleep(2)
    index = 0
    last_paused_url = None

    while True:
        cfg   = load_config()
        state = load_state()
        urls  = cfg.get("urls", [])

        # Paused — stay on pinned URL
        if state.get("paused", False):
            pinned = state.get("pinned_index", -1)
            if pinned >= 0 and pinned < len(urls):
                entry = urls[pinned]
                url   = entry.get("url", "about:blank")
                zoom  = int(entry.get("zoom", 100))
                if url != last_paused_url:
                    navigate(url, zoom)
                    last_paused_url = url
                    write_state({"index": pinned, "url": url})
            time.sleep(3)
            continue

        last_paused_url = None

        # Build active list
        active = [(i, e) for i, e in enumerate(urls) if e.get("enabled", True)]

        if not active:
            write_state({"index": -1, "url": ""})
            time.sleep(10)
            continue

        index = index % len(active)
        real_index, entry = active[index]

        url  = entry.get("url", "about:blank")
        dur  = max(5, int(entry.get("duration", 30)))
        zoom = int(entry.get("zoom", 100))

        write_state({"index": real_index, "url": url})
        navigate(url, zoom)
        time.sleep(dur)
        index += 1

if __name__ == "__main__":
    main()
