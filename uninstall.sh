#!/bin/bash
# TourBox Elite Driver Uninstallation Script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}TourBox Elite Driver Uninstallation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Confirm uninstall
read -p "Are you sure you want to uninstall the TourBox driver? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

# Check if systemd is available
HAS_SYSTEMD=false
if command -v systemctl &> /dev/null && systemctl --user status &> /dev/null; then
    HAS_SYSTEMD=true
fi

if [ "$HAS_SYSTEMD" = "true" ]; then
    # Stop service if running
    if systemctl --user is-active --quiet tourbox 2>/dev/null; then
        echo "Stopping TourBox service..."
        systemctl --user stop tourbox
        echo -e "${GREEN}✓${NC} Service stopped"
    fi

    # Disable service if enabled
    if systemctl --user is-enabled --quiet tourbox 2>/dev/null; then
        echo "Disabling TourBox service..."
        systemctl --user disable tourbox
        echo -e "${GREEN}✓${NC} Service disabled"
    fi

    # Remove systemd service file
    SERVICE_FILE="$HOME/.config/systemd/user/tourbox.service"
    if [ -f "$SERVICE_FILE" ]; then
        echo "Removing systemd service..."
        rm "$SERVICE_FILE"
        systemctl --user daemon-reload
        echo -e "${GREEN}✓${NC} Service file removed"
    fi
else
    # Non-systemd system - try to stop any running driver process
    if pgrep -f "python.*tourboxelite" > /dev/null 2>&1; then
        echo "Stopping TourBox driver process..."
        pkill -f "python.*tourboxelite" 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Driver process stopped"
    fi
    echo -e "${YELLOW}!${NC} Non-systemd system - please remove any init scripts you created manually"
fi

# Ask about config files
CONFIG_DIR="$HOME/.config/tourbox"
PROFILES_DIR="$CONFIG_DIR/profiles"
CONFIG_FILE="$CONFIG_DIR/config.conf"
LEGACY_CONFIG_FILE="$CONFIG_DIR/mappings.conf"

if [ -d "$CONFIG_DIR" ]; then
    echo ""
    echo "Configuration directory found: $CONFIG_DIR"

    # Show what exists
    if [ -d "$PROFILES_DIR" ]; then
        PROFILE_COUNT=$(ls -1 "$PROFILES_DIR"/*.profile 2>/dev/null | wc -l)
        echo "  - $PROFILE_COUNT profile(s) in profiles/"
    fi
    [ -f "$CONFIG_FILE" ] && echo "  - config.conf (device settings)"
    [ -f "$LEGACY_CONFIG_FILE" ] && echo "  - mappings.conf (legacy config)"

    read -p "Remove all configuration files? (y/N): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Remove profiles directory
        if [ -d "$PROFILES_DIR" ]; then
            rm -rf "$PROFILES_DIR"
            echo -e "${GREEN}✓${NC} Profiles directory removed"
        fi
        # Remove config files
        [ -f "$CONFIG_FILE" ] && rm "$CONFIG_FILE"
        [ -f "$LEGACY_CONFIG_FILE" ] && rm "$LEGACY_CONFIG_FILE"
        # Remove any backup files
        rm -f "$CONFIG_DIR"/*.backup.* 2>/dev/null
        rm -f "$CONFIG_DIR"/*.legacy 2>/dev/null
        # Remove directory if empty
        rmdir "$CONFIG_DIR" 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Configuration removed"
    else
        echo -e "${YELLOW}!${NC} Configuration kept"
    fi
fi

# Remove PID file
PID_FILE="${XDG_RUNTIME_DIR:-/tmp}/tourbox.pid"
if [ -f "$PID_FILE" ]; then
    rm "$PID_FILE"
    echo -e "${GREEN}✓${NC} PID file removed"
fi

# Remove GUI launcher script
LAUNCHER_FILE="/usr/local/bin/tourbox-gui"
if [ -f "$LAUNCHER_FILE" ]; then
    echo "Removing GUI launcher..."
    sudo rm "$LAUNCHER_FILE"
    echo -e "${GREEN}✓${NC} Launcher script removed"
fi

# Remove desktop entry
DESKTOP_FILE="/usr/share/applications/tourbox-gui.desktop"
if [ -f "$DESKTOP_FILE" ]; then
    echo "Removing desktop entry..."
    sudo rm "$DESKTOP_FILE"
    sudo update-desktop-database /usr/share/applications/ 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Desktop entry removed"
fi

# Remove application icon
ICON_FILE="/usr/share/pixmaps/tourbox-icon.png"
if [ -f "$ICON_FILE" ]; then
    echo "Removing application icon..."
    sudo rm "$ICON_FILE"
    echo -e "${GREEN}✓${NC} Application icon removed"
fi

# Get installation directory
INSTALL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Ask about removing installation directory
echo ""
read -p "Remove installation directory ($INSTALL_DIR)? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}✓ Uninstallation Complete!${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo "Removing installation directory..."

    # We can't delete the directory while this script is running from it,
    # so we use exec to replace this process with a cleanup command
    cd /tmp
    exec sh -c "rm -rf '$INSTALL_DIR' && echo 'Installation directory removed.'"
else
    echo -e "${YELLOW}!${NC} Installation directory kept: $INSTALL_DIR"
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}✓ Uninstallation Complete!${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
fi
