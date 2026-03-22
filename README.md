# PiKioskManager

A lightweight kiosk manager for the **Raspberry Pi 5** running **Raspberry Pi OS Lite 64-bit (Debian Trixie)**. Automatically boots into fullscreen Chromium and cycles through a list of URLs on a timer — no desktop environment needed.

Built as a self-hosted monitoring solution for services like Grafana, Proxmox, TrueNAS, and Unifi, but can be used for any URL you want displayed on a screen.

---

## Why I built this

There was no simple, automated way to run a kiosk on Pi OS Lite without either:

- Manually editing a handful of config files scattered across the system
- Installing a full desktop environment just to run a browser

This project automates the entire setup with a single script and adds a password-protected web UI so you can manage your kiosk from any device on your network — no SSH required after initial setup.

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
| Kiosk files | Copies all files to `/opt/kiosk/` |
| Session | Writes `~/.bash_profile` and `~/.xinitrc` |
| openbox | Writes `/etc/xdg/openbox/autostart` to launch Chromium + kiosk.py |
| Service | Creates and enables `kiosk-ui.service` (Flask on port 5000) |
| Credentials | Creates default login: `admin` / `admin` |

---

## Web UI

After rebooting, open a browser on any device on your network and go to:

```
http://<pi-ip>:5000
```

**Default login:** username `admin`, password `admin` — change it after first login.

### Managing URLs

- Add URLs and set how long each displays (in seconds)
- Enable or disable individual URLs without removing them
- Reorder URLs with the up/down arrows
- Click **Save** — changes take effect automatically on the next cycle

### Controls

- **Restart cycle** — restarts kiosk.py from the first URL immediately
- **Pause** — stops cycling and locks the display on a URL you choose from a dropdown. The page stays loaded without refreshing until you resume.
- **Resume** — picks up cycling from where it left off

### Account

- **Change password** — available via the button in the top right corner after logging in
- Sessions last 24 hours

---

## Uninstall

To completely remove PiKioskManager from your Pi:

```bash
sudo bash uninstall-kiosk.sh
```

This removes all installed packages, kiosk files, service, and config files, and reverts the autologin setting. Your personal files and OS are untouched.

---

## SSH access

SSH works normally at any time. X only starts on the **physical display** — it will never launch over an SSH session, so you always have a clean terminal when connecting remotely.

---

## File structure

```
PiKioskManager/
├── setup-kiosk.sh      # Run this once to set everything up
├── uninstall-kiosk.sh  # Removes everything setup-kiosk.sh installed
├── kiosk.py            # Controls Chromium via remote debug API (port 9222)
├── app.py              # Flask backend — API + serves the web UI
└── web/
    ├── index.html      # Main web UI — manage URLs, controls, account
    └── login.html      # Login page
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

# Reset credentials to admin/admin
sudo bash -c 'echo '"'"'{"username":"admin","password_hash":"8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"}'"'"' > /opt/kiosk/auth.json'
sudo systemctl restart kiosk-ui
```

---

## Tested on

- Raspberry Pi 5 (8GB)
- Raspberry Pi OS Lite 64-bit — Debian Trixie
- Chromium (package: `chromium`)
