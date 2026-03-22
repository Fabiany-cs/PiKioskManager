#!/bin/bash
# =============================================================
# uninstall-kiosk.sh
# Removes everything installed by setup-kiosk.sh
#
# What gets removed:
#   - /opt/kiosk/                  (all kiosk files)
#   - kiosk-ui.service             (systemd service)
#   - ~/.bash_profile              (auto-start X on tty1)
#   - ~/.xinitrc                   (launches openbox)
#   - /etc/xdg/openbox/autostart   (launches Chromium + kiosk.py)
#   - /etc/X11/Xwrapper.config     (non-root X permission)
#   - /etc/X11/xorg.conf.d/99-vc4.conf (Pi 5 GPU fix)
#   - Packages: chromium, openbox, xinit, xserver-xorg,
#               x11-xserver-utils, unclutter, python3-flask
#
# What is NOT removed:
#   - Your OS, personal files, network settings
#   - python3 and python3-full (system-level, may be needed elsewhere)
#   - raspi-config autologin setting (revert manually if needed)
#
# Usage: sudo bash uninstall-kiosk.sh
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
print_skip()    { echo -e "${YELLOW}[SKIP]${NC} $1 not found — skipping"; }

# ── root check ────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    print_error "Run with sudo: sudo bash uninstall-kiosk.sh"
    exit 1
fi

# ── detect the kiosk user ─────────────────────────────────────
KIOSK_USER="${SUDO_USER:-pi}"
KIOSK_HOME=$(eval echo "~${KIOSK_USER}")

clear
echo ""
echo "========================================"
echo "   Kiosk Uninstall"
echo "========================================"
echo -e "  ${YELLOW}Tip: Press Ctrl+C at any time to quit${NC}"
echo "========================================"
echo ""
echo "  This will remove:"
echo "    - All kiosk files from /opt/kiosk/"
echo "    - The kiosk-ui systemd service"
echo "    - Session files (.bash_profile, .xinitrc)"
echo "    - openbox autostart config"
echo "    - X11 config files (Xwrapper, 99-vc4.conf)"
echo "    - Installed packages (chromium, openbox, etc.)"
echo ""
echo -e "  ${GREEN}Your URLs, personal files, and OS are untouched.${NC}"
echo ""

read -r -p "Are you sure you want to uninstall? (yes/no): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy][Ee][Ss]$|^[Yy]$ ]]; then
    print_warning "Uninstall cancelled."
    exit 0
fi
echo ""

# ═══════════════════════════════════════════════════════════════
# STEP 1 — STOP AND DISABLE THE SERVICE
# ═══════════════════════════════════════════════════════════════
print_step "Step 1 of 5 — Stopping kiosk-ui service"

if systemctl list-units --full --all | grep -q "kiosk-ui.service"; then
    systemctl stop kiosk-ui.service  || true
    systemctl disable kiosk-ui.service || true
    print_info "kiosk-ui service stopped and disabled."
else
    print_skip "kiosk-ui.service"
fi

# Remove the service file
SERVICE_FILE="/etc/systemd/system/kiosk-ui.service"
if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload
    print_info "Service file removed."
else
    print_skip "$SERVICE_FILE"
fi

# Kill kiosk.py if it's running
if pgrep -f "kiosk.py" > /dev/null 2>&1; then
    pkill -f "kiosk.py" || true
    print_info "kiosk.py process killed."
fi

# ═══════════════════════════════════════════════════════════════
# STEP 2 — REMOVE KIOSK FILES
# ═══════════════════════════════════════════════════════════════
print_step "Step 2 of 5 — Removing /opt/kiosk/"

if [ -d "/opt/kiosk" ]; then
    rm -rf /opt/kiosk
    print_info "/opt/kiosk removed."
else
    print_skip "/opt/kiosk"
fi

# ═══════════════════════════════════════════════════════════════
# STEP 3 — REMOVE SESSION AND X11 CONFIG FILES
# ═══════════════════════════════════════════════════════════════
print_step "Step 3 of 5 — Removing session and X11 config files"

# .bash_profile — only remove if it contains our startx line
BASH_PROFILE="${KIOSK_HOME}/.bash_profile"
if [ -f "$BASH_PROFILE" ] && grep -q "startx" "$BASH_PROFILE"; then
    rm -f "$BASH_PROFILE"
    print_info ".bash_profile removed."
else
    print_skip ".bash_profile (not ours or not found)"
fi

# .xinitrc
XINITRC="${KIOSK_HOME}/.xinitrc"
if [ -f "$XINITRC" ]; then
    rm -f "$XINITRC"
    print_info ".xinitrc removed."
else
    print_skip ".xinitrc"
fi

# openbox autostart
AUTOSTART="/etc/xdg/openbox/autostart"
if [ -f "$AUTOSTART" ]; then
    rm -f "$AUTOSTART"
    print_info "openbox autostart removed."
else
    print_skip "$AUTOSTART"
fi

# Xwrapper.config
XWRAPPER="/etc/X11/Xwrapper.config"
if [ -f "$XWRAPPER" ]; then
    rm -f "$XWRAPPER"
    print_info "Xwrapper.config removed."
else
    print_skip "$XWRAPPER"
fi

# 99-vc4.conf
VC4_CONF="/etc/X11/xorg.conf.d/99-vc4.conf"
if [ -f "$VC4_CONF" ]; then
    rm -f "$VC4_CONF"
    print_info "99-vc4.conf removed."
else
    print_skip "$VC4_CONF"
fi

# ═══════════════════════════════════════════════════════════════
# STEP 4 — REMOVE PACKAGES
# ═══════════════════════════════════════════════════════════════
print_step "Step 4 of 5 — Removing installed packages"

PACKAGES="chromium openbox xinit xserver-xorg x11-xserver-utils unclutter python3-flask"

print_info "Removing: $PACKAGES"
apt purge -y $PACKAGES 2>/dev/null || true
apt autoremove -y
print_info "Packages removed."

# ═══════════════════════════════════════════════════════════════
# STEP 5 — REVERT AUTOLOGIN
# ═══════════════════════════════════════════════════════════════
print_step "Step 5 of 5 — Reverting console autologin"

# B1 = Console (no autologin)
raspi-config nonint do_boot_behaviour B1
print_info "Console autologin disabled — Pi will prompt for login on boot."

# ═══════════════════════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════════════════════
echo ""
echo "========================================"
echo -e "  ${GREEN}Uninstall complete!${NC}"
echo "========================================"
echo ""
echo "  Everything installed by setup-kiosk.sh"
echo "  has been removed."
echo ""
echo "  To reinstall at any time:"
echo -e "    ${CYAN}sudo bash setup-kiosk.sh${NC}"
echo ""

read -r -p "Reboot now to finalize? (yes/no): " ANS
if [[ "$ANS" =~ ^[Yy] ]]; then
    print_info "Rebooting in 5 seconds... (Ctrl+C to cancel)"
    sleep 5
    reboot
else
    print_warning "Reboot skipped. Run 'sudo reboot' when ready."
fi
