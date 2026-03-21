#!/bin/bash
# =============================================================
# setup-kiosk.sh
# Sets up a fullscreen URL-cycling kiosk on:
#   Raspberry Pi 5 — OS Lite 64-bit (Debian Trixie)
#
# Run after cloning:
#   git clone https://github.com/Fabiany-cs/PiKioskManager.git
#   cd PiKioskManager
#   sudo bash setup-kiosk.sh
#
# Tested and confirmed working. All fixes included:
#   - Xwrapper.config  (non-root X permission)
#   - 99-vc4.conf      (Pi 5 GPU driver fix)
#   - user groups      (tty/video/input/render)
#   - remote debug     (Chromium port 9222 for kiosk.py)
# =============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
print_step()    { echo -e "\n${CYAN}==>${NC} $1"; }

# ── root check ────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    print_error "Run with sudo: sudo bash setup-kiosk.sh"
    exit 1
fi

# ── make sure we're running from the repo root directory ──────
# The script needs kiosk.py, app.py, and index.html next to it.
# SCRIPT_DIR resolves to wherever setup-kiosk.sh actually lives,
# even if the user runs it from a different directory.
# Resolve the directory the script lives in.
# "sudo bash setup-kiosk.sh" sets $0 to "setup-kiosk.sh" with no path,
# so we fall back to $PWD when dirname gives us just "."
_RAW_DIR="$(dirname "${BASH_SOURCE[0]:-$0}")"
if [ "$_RAW_DIR" = "." ]; then
    SCRIPT_DIR="$PWD"
else
    SCRIPT_DIR="$(cd "$_RAW_DIR" && pwd)"
fi

if [ ! -f "${SCRIPT_DIR}/kiosk.py" ] || \
   [ ! -f "${SCRIPT_DIR}/app.py" ] || \
   [ ! -f "${SCRIPT_DIR}/web/index.html" ]; then
    print_error "Missing files. Make sure you cloned the full repo:"
    print_error "  git clone https://github.com/Fabiany-cs/PiKioskManager.git"
    print_error "  cd PiKioskManager"
    print_error "  sudo bash setup-kiosk.sh"
    exit 1
fi

# ── detect the real user (the one who called sudo) ────────────
KIOSK_USER="${SUDO_USER:-pi}"
KIOSK_HOME=$(eval echo "~${KIOSK_USER}")
print_info "Kiosk will run as user: ${YELLOW}${KIOSK_USER}${NC} (home: ${KIOSK_HOME})"

clear
echo ""
echo "========================================"
echo "   Kiosk Setup — Pi 5 OS Lite Trixie"
echo "========================================"
echo -e "  ${YELLOW}Tip: Press Ctrl+C at any time to quit${NC}"
echo "========================================"
echo ""
echo "  This script will install and configure:"
echo "    - Chromium (kiosk mode, fullscreen)"
echo "    - openbox + xserver (minimal display layer)"
echo "    - URL cycling controller (kiosk.py)"
echo "    - Web UI to manage URLs (Flask, port 5000)"
echo "    - Auto-start on boot, no login needed"
echo ""
read -r -p "Press Enter to begin, or Ctrl+C to cancel: "
echo ""

# ═══════════════════════════════════════════════════════════════
# STEP 1 — SYSTEM UPDATE
# ═══════════════════════════════════════════════════════════════
print_step "Step 1 of 6 — Updating system packages"
apt update && apt upgrade -y
print_info "System up to date."

# ═══════════════════════════════════════════════════════════════
# STEP 2 — INSTALL PACKAGES
# ═══════════════════════════════════════════════════════════════
print_step "Step 2 of 6 — Installing packages"

# xserver-xorg        : X11 display server
# xinit               : allows startx from .bash_profile
# openbox             : minimal window manager, no desktop
# x11-xserver-utils   : xset — disable screensaver/blanking
# chromium            : the browser (Trixie package name is 'chromium')
# unclutter           : hides the mouse cursor after idle
# python3-flask       : web framework for the management UI
# python3-full        : ensures full Python stdlib is available

apt install -y --no-install-recommends \
    xserver-xorg \
    xinit \
    openbox \
    x11-xserver-utils \
    chromium \
    unclutter \
    python3-flask \
    python3-full

print_info "Packages installed."

# ═══════════════════════════════════════════════════════════════
# STEP 3 — SYSTEM CONFIGURATION FOR X11
# ═══════════════════════════════════════════════════════════════
print_step "Step 3 of 6 — Configuring system for X11 + autologin"

# Console autologin — B2 = Console Autologin (no password on tty1)
raspi-config nonint do_boot_behaviour B2
print_info "Console autologin enabled."

# Add user to groups X11 requires
# tty   : open /dev/tty0 — without this startx fails immediately
# video : GPU and framebuffer access
# input : keyboard, mouse, touch
# render: GPU render nodes (/dev/dri/renderD*)
usermod -a -G tty,video,input,render "${KIOSK_USER}"
print_info "Added ${KIOSK_USER} to tty, video, input, render groups."

# Allow non-root users to start X on Debian Trixie
# Without this: parse_vt_settings: Cannot open /dev/tty0 (Permission denied)
mkdir -p /etc/X11
echo "needs_root_rights=yes" > /etc/X11/Xwrapper.config
print_info "Xwrapper.config written."

# Pi 5 GPU driver — tell X to use modesetting on the vc4 device
# Without this: Cannot run in framebuffer mode. Please specify busIDs
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/99-vc4.conf << 'EOF'
Section "OutputClass"
    Identifier "vc4"
    MatchDriver "vc4"
    Driver "modesetting"
    Option "PrimaryGPU" "true"
EndSection
EOF
print_info "Pi 5 GPU config written (99-vc4.conf)."

# ═══════════════════════════════════════════════════════════════
# STEP 4 — DEPLOY KIOSK FILES
# ═══════════════════════════════════════════════════════════════
print_step "Step 4 of 6 — Deploying kiosk files to /opt/kiosk"

mkdir -p /opt/kiosk/web

# Copy the Python and HTML files from the repo into place
# These are the real source files sitting next to this script —
# no heredocs, no inline code, just a straight file copy
cp "${SCRIPT_DIR}/kiosk.py"   /opt/kiosk/kiosk.py
cp "${SCRIPT_DIR}/app.py"     /opt/kiosk/app.py
cp "${SCRIPT_DIR}/index.html" /opt/kiosk/web/index.html
chmod +x /opt/kiosk/kiosk.py
chmod +x /opt/kiosk/app.py
print_info "kiosk.py, app.py, index.html copied."

# Create default kiosk.json only if it doesn't already exist
# This preserves the user's URL list if they're re-running the script
if [ ! -f /opt/kiosk/kiosk.json ]; then
    cat > /opt/kiosk/kiosk.json << 'EOF'
{
  "urls": [
    {"url": "https://example.com", "duration": 30}
  ]
}
EOF
    print_info "Created default kiosk.json"
else
    print_warning "kiosk.json already exists — leaving it unchanged."
fi

# Fix ownership so the kiosk user can read/write kiosk.json
chown -R "${KIOSK_USER}:${KIOSK_USER}" /opt/kiosk
chmod 664 /opt/kiosk/kiosk.json

# ═══════════════════════════════════════════════════════════════
# STEP 5 — USER SESSION FILES
# ═══════════════════════════════════════════════════════════════
print_step "Step 5 of 6 — Configuring user session files"

# .bash_profile — starts X on tty1 (physical screen) only, not SSH
# The $XDG_VTNR check means:
#   Physical console (tty1) → startx → kiosk runs
#   SSH session             → normal bash prompt, no X
cat > "${KIOSK_HOME}/.bash_profile" << 'EOF'
[[ -f ~/.bashrc ]] && source ~/.bashrc

if [[ -z $DISPLAY && $XDG_VTNR -eq 1 ]]; then
    startx -- -nocursor
fi
EOF
chown "${KIOSK_USER}:${KIOSK_USER}" "${KIOSK_HOME}/.bash_profile"
print_info ".bash_profile written."

# .xinitrc — startx runs this, which launches openbox-session
# openbox-session then reads /etc/xdg/openbox/autostart
cat > "${KIOSK_HOME}/.xinitrc" << 'EOF'
exec openbox-session
EOF
chown "${KIOSK_USER}:${KIOSK_USER}" "${KIOSK_HOME}/.xinitrc"
print_info ".xinitrc written."

# openbox autostart — runs inside X as the kiosk user
# Key Chromium flags:
#   --kiosk                      : fullscreen, no UI chrome
#   --remote-debugging-port=9222 : HTTP API that kiosk.py uses to navigate
#   --noerrdialogs               : suppress crash popups
#   --no-first-run               : skip first-run wizard
#   --password-store=basic       : suppress keyring unlock dialog
#   --disable-restore-session-state : no "restore pages?" prompt
cat > /etc/xdg/openbox/autostart << 'EOF'
# Disable screensaver, blanking, power management
xset s off
xset s noblank
xset -dpms

# Hide mouse cursor after 1 second idle
unclutter -idle 1 -root &

# Clear Chromium crash flag — prevents restore dialog on boot
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' \
    ~/.config/chromium/'Local State' 2>/dev/null || true
sed -i 's/"exit_type":"[^"]*"/"exit_type":"Normal"/' \
    ~/.config/chromium/Default/Preferences 2>/dev/null || true

# Launch Chromium in kiosk mode with remote debugging enabled
chromium \
    --kiosk \
    --remote-debugging-port=9222 \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --password-store=basic \
    --disable-translate \
    --disable-features=TranslateUI \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    about:blank &

# Start the URL cycling controller
python3 /opt/kiosk/kiosk.py &
EOF
print_info "openbox autostart written."

# Set openbox as the default x-session-manager
update-alternatives --set x-session-manager /usr/bin/openbox-session
print_info "openbox set as default x-session-manager."

# ═══════════════════════════════════════════════════════════════
# STEP 6 — FLASK WEB UI SYSTEMD SERVICE
# ═══════════════════════════════════════════════════════════════
print_step "Step 6 of 6 — Creating kiosk-ui systemd service"

cat > /etc/systemd/system/kiosk-ui.service << EOF
[Unit]
Description=Kiosk Web UI (Flask)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${KIOSK_USER}
WorkingDirectory=/opt/kiosk
ExecStart=/usr/bin/python3 /opt/kiosk/app.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable kiosk-ui.service
print_info "kiosk-ui.service enabled."

# ═══════════════════════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════════════════════
CURRENT_IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')

echo ""
echo "========================================"
echo -e "  ${GREEN}Kiosk setup complete!${NC}"
echo "========================================"
echo ""
echo "  On reboot the Pi will:"
echo "    1. Auto-login as ${KIOSK_USER}"
echo "    2. Start X on the physical display"
echo "    3. Open Chromium fullscreen"
echo "    4. Cycle through your URLs automatically"
echo ""
echo "  Manage URLs from any browser on your network:"
if [ -n "$CURRENT_IP" ]; then
    echo -e "    ${GREEN}http://${CURRENT_IP}:5000${NC}"
else
    echo -e "    ${GREEN}http://<pi-ip>:5000${NC}"
fi
echo ""
echo "  SSH still works — X only starts on the"
echo "  physical screen, not over SSH."
echo ""
echo "  Useful commands:"
echo -e "    ${CYAN}sudo systemctl status kiosk-ui${NC}"
echo -e "    ${CYAN}sudo systemctl restart kiosk-ui${NC}"
echo ""

read -r -p "Reboot now to start the kiosk? (yes/no): " ANS
if [[ "$ANS" =~ ^[Yy] ]]; then
    print_info "Rebooting in 5 seconds... (Ctrl+C to cancel)"
    sleep 5
    reboot
else
    print_warning "Reboot skipped. Run 'sudo reboot' when ready."
fi
