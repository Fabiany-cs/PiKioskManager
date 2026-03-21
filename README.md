# PiKioskManager

A lightweight kiosk manager for the **Raspberry Pi 5** running **Raspberry Pi OS Lite 64-bit (Debian Trixie)**. Automatically boots into fullscreen Chromium and cycles through a list of URLs on a timer — no desktop environment needed.

Built as a self-hosted monitoring solution for services like Grafana, Proxmox, TrueNAS, and Unifi, but can be used for any URL you want displayed on a screen.

---

## Why I built this

There was no simple, automated way to run a kiosk on Pi OS Lite without either:

- Manually editing a handful of config files scattered across the system
- Installing a full desktop environment just to run a browser

This project automates the entire setup with a single script and adds a simple web UI so you can manage your URL list from any device on your network — no SSH required after initial setup.

---

## How it works

```
Pi boots
  → Auto-login as your user (no password prompt)
  → X11 starts on the physical display only (SSH sessions unaffected)
  → openbox launches (minimal window manager, no desktop)
  → Chromium opens fullscreen in kiosk mode
  → kiosk.py connects to Chromium via its debug API and cycles URLs
  → Flask web UI runs in the background on port 5000
```

---

## Requirements

- Raspberry Pi 5
- Raspberry Pi OS Lite 64-bit (Debian Trixie)
- Network connection
- Physical display connected via HDMI

---

## Installation

```bash
git clone https://github.com/Fabiany-cs/PiKioskManager.git
cd PiKioskManager
sudo bash setup-kiosk.sh
```

The script will walk you through everything and prompt you to reboot when done.

**What the script installs and configures:**

| Step | What happens |
|---|---|
| Packages | `chromium`, `openbox`, `xserver-xorg`, `xinit`, `x11-xserver-utils`, `unclutter`, `python3-flask` |
| Autologin | Configures console autologin via `raspi-config` |
| X11 permissions | Adds your user to `tty`, `video`, `input`, `render` groups |
| Xwrapper | Writes `/etc/X11/Xwrapper.config` so non-root users can start X |
| Pi 5 GPU | Writes `/etc/X11/xorg.conf.d/99-vc4.conf` so X uses the correct driver |
| Kiosk files | Copies `kiosk.py`, `app.py`, `web/index.html` to `/opt/kiosk/` |
| Session | Writes `~/.bash_profile` and `~/.xinitrc` |
| openbox | Writes `/etc/xdg/openbox/autostart` to launch Chromium + kiosk.py |
| Service | Creates and enables `kiosk-ui.service` (Flask on port 5000) |

---

## Managing your URLs

After rebooting, open a browser on any device on your network and go to:

```
http://<pi-ip>:5000
```

From there you can:

- Add URLs
- Set how long each URL displays (in seconds)
- Reorder URLs with the up/down arrows
- Remove URLs
- Click **Save** — changes take effect automatically on the next cycle

---

## SSH access

SSH works normally at any time. X only starts on the **physical display** — it will never launch over an SSH session, so you always have a clean terminal when connecting remotely.

---

## File structure

```
PiKioskManager/
├── setup-kiosk.sh    # Run this once to set everything up
├── kiosk.py          # Controls Chromium via remote debug API (port 9222)
├── app.py            # Flask backend — serves the web UI and reads/writes kiosk.json
└── index.html        # Web UI — manage your URL list from any browser
```

After setup, files are deployed to `/opt/kiosk/` on the Pi.

---

## How kiosk.py controls Chromium

Rather than using keyboard simulation tools like `xdotool` (which don't work reliably in kiosk mode), `kiosk.py` talks directly to Chromium's built-in remote debugging API on port 9222. It opens a new tab to the target URL and closes the previous one — clean, reliable, no side effects.

---

## Useful commands

```bash
# Check the web UI service
sudo systemctl status kiosk-ui

# Restart the web UI service
sudo systemctl restart kiosk-ui

# View web UI logs
sudo journalctl -u kiosk-ui -f

# Edit the URL list directly
sudo nano /opt/kiosk/kiosk.json
```

---

## Tested on

- Raspberry Pi 5 (8GB)
- Raspberry Pi OS Lite 64-bit — Debian Trixie
- Chromium (package: `chromium`)
