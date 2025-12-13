#!/bin/bash
# TourBox Elite Driver Installation Script
# This script installs the TourBox Elite driver as a systemd user service

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}TourBox Elite Driver Installation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo -e "${RED}Error: This driver only works on Linux${NC}"
    exit 1
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓${NC} Found Python $PYTHON_VERSION"

# Detect distribution and package manager
echo ""
echo "Detecting system..."

if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO_ID="$ID"
    DISTRO_NAME="$NAME"
else
    DISTRO_ID="unknown"
    DISTRO_NAME="Linux"
fi

# Determine package manager and package names
if command -v apt &> /dev/null; then
    PKG_MANAGER="apt"
    PKG_INSTALL="sudo apt install"
    PKG_BLUEZ="bluez"
    PKG_PIP="python3-pip"
    PKG_GCC="gcc"
    PKG_PYTHON_DEV="python3-dev"
    PKG_KERNEL_HEADERS="linux-headers-generic"
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
    PKG_INSTALL="sudo dnf install"
    PKG_BLUEZ="bluez"
    PKG_PIP="python3-pip"
    PKG_GCC="gcc"
    PKG_PYTHON_DEV="python3-devel"
    PKG_KERNEL_HEADERS="kernel-headers"
elif command -v pacman &> /dev/null; then
    PKG_MANAGER="pacman"
    PKG_INSTALL="sudo pacman -S"
    PKG_BLUEZ="bluez"
    PKG_PIP="python-pip"
    PKG_GCC="gcc"
    PKG_PYTHON_DEV="python"
    PKG_KERNEL_HEADERS="linux-headers"
else
    PKG_MANAGER="unknown"
    PKG_INSTALL="# Use your package manager to install:"
fi

echo -e "${GREEN}✓${NC} Detected: $DISTRO_NAME ($PKG_MANAGER)"

# Check for required system packages
echo ""
echo "Checking system dependencies..."

MISSING_DEPS=()
MISSING_PKG_NAMES=()

# Check for bluetooth
if ! command -v bluetoothctl &> /dev/null; then
    MISSING_DEPS+=("bluetoothctl")
    MISSING_PKG_NAMES+=("$PKG_BLUEZ")
fi

# Check for pip
if ! python3 -m pip --version &> /dev/null; then
    MISSING_DEPS+=("pip")
    MISSING_PKG_NAMES+=("$PKG_PIP")
fi

# Check for venv module by checking for ensurepip (which is what actually fails)
if ! python3 -c "import ensurepip" &> /dev/null; then
    # Extract major.minor version (e.g., 3.13 from 3.13.5)
    PYTHON_MM_VERSION=$(echo "$PYTHON_VERSION" | cut -d. -f1,2)
    MISSING_DEPS+=("venv")
    if [ "$PKG_MANAGER" = "apt" ]; then
        MISSING_PKG_NAMES+=("python${PYTHON_MM_VERSION}-venv")
    elif [ "$PKG_MANAGER" = "dnf" ]; then
        MISSING_PKG_NAMES+=("python${PYTHON_MM_VERSION}-venv")
    else
        MISSING_PKG_NAMES+=("python-venv")
    fi
fi

# Check for gcc (needed to compile Python packages like evdev)
if ! command -v gcc &> /dev/null; then
    MISSING_DEPS+=("gcc")
    MISSING_PKG_NAMES+=("$PKG_GCC")
fi

# Check for Python development headers (needed to compile Python packages)
if ! python3 -c "import sysconfig; import os; exit(0 if os.path.exists(sysconfig.get_path('include')) else 1)" &> /dev/null; then
    MISSING_DEPS+=("python-dev")
    MISSING_PKG_NAMES+=("$PKG_PYTHON_DEV")
fi

# Check for kernel headers (needed for evdev compilation)
if ! [ -d "/usr/include/linux" ]; then
    MISSING_DEPS+=("kernel-headers")
    MISSING_PKG_NAMES+=("$PKG_KERNEL_HEADERS")
fi

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo -e "${RED}Missing dependencies: ${MISSING_DEPS[*]}${NC}"
    echo ""
    echo "These packages are required to compile and run the TourBox driver."
    echo ""
    echo "Install them with:"
    echo "  $PKG_INSTALL ${MISSING_PKG_NAMES[*]}"
    echo ""
    echo "Then run this installer again:"
    echo "  ./install.sh"
    exit 1
fi

echo -e "${GREEN}✓${NC} All system dependencies found"

# Check if user is in input group
echo ""
echo "Checking permissions..."

if ! groups | grep -q '\binput\b'; then
    echo -e "${YELLOW}!${NC} User '$USER' is not in the 'input' group"
    echo ""
    echo "The driver needs access to /dev/uinput to create virtual input devices."
    echo ""
    echo "Adding user to input group (requires sudo):"
    sudo usermod -a -G input $USER

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} User added to input group"
        NEED_RELOGIN=true
    else
        echo -e "${RED}Error: Failed to add user to input group${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} User is in input group"
fi

# Check if user is in dialout group (for USB access)
if ! groups | grep -q '\bdialout\b'; then
    echo -e "${YELLOW}!${NC} User '$USER' is not in the 'dialout' group"
    echo ""
    echo "The driver needs dialout group for USB serial port access."
    echo ""
    echo "Adding user to dialout group (requires sudo):"
    sudo usermod -a -G dialout $USER

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} User added to dialout group"
        NEED_RELOGIN=true
    else
        echo -e "${RED}Error: Failed to add user to dialout group${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} User is in dialout group"
fi

# Set up udev rule for /dev/uinput permissions
echo ""
echo "Configuring /dev/uinput permissions..."

UDEV_RULE="/etc/udev/rules.d/99-uinput.rules"
if [ ! -f "$UDEV_RULE" ]; then
    echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' | sudo tee "$UDEV_RULE" > /dev/null

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Created udev rule for uinput device"

        # Reload udev rules
        sudo udevadm control --reload-rules

        # Ensure uinput module is loaded
        if ! lsmod | grep -q uinput; then
            sudo modprobe uinput
            echo -e "${GREEN}✓${NC} Loaded uinput kernel module"
        fi

        # Ensure uinput module loads on boot
        if [ ! -f /etc/modules-load.d/uinput.conf ]; then
            echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf > /dev/null
            echo -e "${GREEN}✓${NC} Configured uinput to load on boot"
        fi
    else
        echo -e "${RED}Error: Failed to create udev rule${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} udev rule already exists"
fi

# Create and activate virtual environment
echo ""
echo "Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Created virtual environment"
else
    echo -e "${YELLOW}!${NC} Virtual environment already exists"
fi

# Install package and dependencies
echo ""
echo "Installing TourBox Elite driver..."
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -e .

echo -e "${GREEN}✓${NC} Driver installed successfully"

# Install GUI dependencies
echo ""
echo "Installing GUI dependencies..."
./venv/bin/pip install -q -r tourboxelite/gui/requirements.txt

echo -e "${GREEN}✓${NC} GUI dependencies installed successfully"

# Create GUI launcher script
echo ""
echo "Creating GUI launcher..."

LAUNCHER_FILE="/usr/local/bin/tourbox-gui"
TEMP_LAUNCHER="/tmp/tourbox-gui.$$"

cat > "$TEMP_LAUNCHER" <<EOF
#!/bin/bash
# TourBox Elite Configuration GUI Launcher
# Auto-generated by install.sh

exec "$SCRIPT_DIR/venv/bin/python" -m tourboxelite.gui "\$@"
EOF

chmod +x "$TEMP_LAUNCHER"
sudo mv "$TEMP_LAUNCHER" "$LAUNCHER_FILE"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Created launcher: $LAUNCHER_FILE"
else
    echo -e "${RED}Error: Failed to create launcher${NC}"
    exit 1
fi

# Install application icon
echo ""
echo "Installing application icon..."
ICON_SOURCE="$SCRIPT_DIR/tourboxelite/gui/assets/tourbox-icon.png"
ICON_DEST="/usr/share/pixmaps/tourbox-icon.png"

if [ -f "$ICON_SOURCE" ]; then
    sudo cp "$ICON_SOURCE" "$ICON_DEST"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Installed icon: $ICON_DEST"
    else
        echo -e "${YELLOW}!${NC} Warning: Failed to install icon"
    fi
else
    echo -e "${YELLOW}!${NC} Warning: Icon file not found: $ICON_SOURCE"
fi

# Install desktop entry
echo "Installing desktop entry..."
DESKTOP_SOURCE="$SCRIPT_DIR/tourbox-gui.desktop"
DESKTOP_DEST="/usr/share/applications/tourbox-gui.desktop"

if [ -f "$DESKTOP_SOURCE" ]; then
    sudo cp "$DESKTOP_SOURCE" "$DESKTOP_DEST"
    if [ $? -eq 0 ]; then
        # Update desktop database (makes it appear immediately)
        sudo update-desktop-database /usr/share/applications/ 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Installed desktop entry: $DESKTOP_DEST"
        echo -e "${GREEN}✓${NC} Application added to system menu"
    else
        echo -e "${YELLOW}!${NC} Warning: Failed to install desktop entry"
    fi
else
    echo -e "${YELLOW}!${NC} Warning: Desktop file not found: $DESKTOP_SOURCE"
fi

# Install config file
echo ""
echo "=========================================="
echo "Configuration Setup"
echo "=========================================="
echo ""

CONFIG_DIR="$HOME/.config/tourbox"
CONFIG_FILE="$CONFIG_DIR/mappings.conf"
DEFAULT_CONFIG="tourboxelite/default_mappings.conf"

# Create config directory
mkdir -p "$CONFIG_DIR"

# Check if config exists
if [ -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}!${NC} Config file already exists: $CONFIG_FILE"
    echo ""
    read -p "Do you want to keep your existing config? (Y/n): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Nn]$ ]]; then
        # Backup and replace
        BACKUP="$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        echo "Backing up to: $BACKUP"
        cp "$CONFIG_FILE" "$BACKUP"
        cp "$DEFAULT_CONFIG" "$CONFIG_FILE"
        echo -e "${GREEN}✓${NC} Installed new config (backup saved)"
    else
        echo -e "${GREEN}✓${NC} Keeping existing config"
    fi
else
    # Fresh install
    cp "$DEFAULT_CONFIG" "$CONFIG_FILE"
    echo -e "${GREEN}✓${NC} Installed default config to: $CONFIG_FILE"

    # Prompt for MAC address
    echo ""
    echo "The driver supports both USB and Bluetooth connections."
    echo ""
    echo "  USB:       Just plug in the cable - no configuration needed"
    echo "  Bluetooth: Requires MAC address (see below)"
    echo ""
    echo "To find your TourBox MAC address (for Bluetooth):"
    echo "  1. Make sure TourBox is powered on and NOT connected via USB"
    echo "  2. Run: bluetoothctl devices"
    echo "  3. Look for 'TourBox Elite' in the output"
    echo ""
    read -p "Enter MAC address for Bluetooth (or press Enter to skip for USB-only): " MAC_ADDRESS

    if [ -n "$MAC_ADDRESS" ]; then
        if [[ $MAC_ADDRESS =~ ^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$ ]]; then
            sed -i "s/mac_address = .*/mac_address = $MAC_ADDRESS/" "$CONFIG_FILE"
            echo -e "${GREEN}✓${NC} MAC address configured"
        else
            echo -e "${YELLOW}!${NC} Invalid MAC format - please edit config manually"
        fi
    fi
fi

# Install systemd service
echo ""
echo "=========================================="
echo "Systemd Service Setup"
echo "=========================================="
echo ""

SYSTEMD_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SYSTEMD_DIR/tourbox.service"

mkdir -p "$SYSTEMD_DIR"

# Stop service if it's currently running
if systemctl --user is-active --quiet tourbox; then
    echo -e "${YELLOW}!${NC} Stopping running service..."
    systemctl --user stop tourbox
    echo -e "${GREEN}✓${NC} Service stopped"
fi

# Create service file
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=TourBox Elite Driver
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$SCRIPT_DIR/venv/bin/python -m tourboxelite
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF

echo -e "${GREEN}✓${NC} Installed systemd service"

# Reload systemd
systemctl --user daemon-reload
echo -e "${GREEN}✓${NC} Reloaded systemd daemon"

# Ask about enabling service
echo ""
read -p "Enable TourBox service to start on login? (Y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    systemctl --user enable tourbox
    echo -e "${GREEN}✓${NC} Service enabled (will start on login)"
    SERVICE_ENABLED=true
else
    echo -e "${YELLOW}!${NC} Service not enabled (won't start automatically)"
    SERVICE_ENABLED=false
fi

# Ask about starting service now (only if no relogin required)
if [ "$NEED_RELOGIN" != "true" ]; then
    echo ""
    read -p "Start TourBox service now? (Y/n): " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        systemctl --user restart tourbox
        sleep 2

        if systemctl --user is-active --quiet tourbox; then
            echo -e "${GREEN}✓${NC} Service is running"
        else
            echo -e "${RED}✗${NC} Service failed to start"
            echo ""
            echo "Check logs with: journalctl --user -u tourbox -n 50"
            exit 1
        fi
    else
        echo -e "${YELLOW}!${NC} Service not started"
    fi
fi

# Final summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Installation Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Installed to: $SCRIPT_DIR"
echo "Config file:  $CONFIG_FILE"
echo "Service file: $SERVICE_FILE"
echo ""
echo "Useful commands:"
echo "  Start:   systemctl --user start tourbox"
echo "  Stop:    systemctl --user stop tourbox"
echo "  Status:  systemctl --user status tourbox"
echo "  Logs:    journalctl --user -u tourbox -f"
echo "  Restart: systemctl --user restart tourbox"
echo ""
echo "To customize button mappings:"
echo "  Option 1 - Use the GUI (recommended):"
echo "    - Run from terminal: tourbox-gui"
echo "    - Or find 'TourBox Elite Configuration' in your app menu"
echo ""
echo "  Option 2 - Edit config file manually:"
echo "    nano $CONFIG_FILE"
echo "    systemctl --user restart tourbox  # Apply changes"
echo ""

if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    echo -e "${GREEN}✓${NC} Wayland detected - Profile mode is available!"
    echo "  Edit your config to enable app-specific profiles"
    echo ""

    # Check for kdotool on KDE Plasma
    if [ "$XDG_CURRENT_DESKTOP" = "KDE" ] || [ "$DESKTOP_SESSION" = "plasma" ]; then
        echo "  Detected compositor: KDE Plasma"
        if ! command -v kdotool &> /dev/null; then
            echo ""
            echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
            echo -e "${YELLOW}║  ATTENTION KDE PLASMA USERS:                                   ║${NC}"
            echo -e "${YELLOW}║  kdotool is NOT installed - Profile mode will NOT work!        ║${NC}"
            echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
            echo ""
            echo -e "${BLUE}To enable profile mode (app-specific button mappings), install kdotool:${NC}"
            echo ""
            echo -e "${GREEN}1. Install build dependencies:${NC}"
            echo "   sudo apt install build-essential pkg-config libdbus-1-dev libxcb1-dev"
            echo ""
            echo -e "${GREEN}2. Install Rust (if not already installed):${NC}"
            echo "   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
            echo "   (Choose option 1 for standard installation when prompted)"
            echo "   source \$HOME/.cargo/env"
            echo ""
            echo -e "${GREEN}3. Install kdotool:${NC}"
            echo "   cargo install kdotool"
            echo ""
            echo -e "${GREEN}4. Verify installation:${NC}"
            echo "   kdotool --version"
            echo ""
            echo -e "${YELLOW}Note: Simple mode (single mapping) works without kdotool.${NC}"
            echo ""
        else
            KDOTOOL_VERSION=$(kdotool --version 2>&1 | head -1)
            echo -e "  ${GREEN}✓${NC} kdotool found: $KDOTOOL_VERSION"
        fi
    elif [ "$XDG_CURRENT_DESKTOP" = "GNOME" ] || [[ "$XDG_CURRENT_DESKTOP" == *"GNOME"* ]]; then
        # GNOME requires an extension for window detection
        echo "  Detected compositor: GNOME"

        # Check if Focused Window D-Bus extension is installed
        if gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/shell/extensions/FocusedWindow --method org.gnome.shell.extensions.FocusedWindow.Get &>/dev/null; then
            echo -e "  ${GREEN}✓${NC} Focused Window D-Bus extension is installed"
        else
            echo ""
            echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
            echo -e "${YELLOW}║  ATTENTION GNOME USERS:                                        ║${NC}"
            echo -e "${YELLOW}║  Profile mode requires a GNOME Shell extension!                ║${NC}"
            echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
            echo ""
            echo -e "${BLUE}To enable profile mode (app-specific button mappings):${NC}"
            echo ""
            echo "1. Visit: https://extensions.gnome.org/extension/5592/focused-window-d-bus/"
            echo "2. Click the install button to install the extension"
            echo "3. Verify installation with:"
            echo "   gnome-extensions list | grep focused-window-dbus"
            echo "   (Should show: focused-window-dbus@flexagoon.com)"
            echo ""
            echo -e "${YELLOW}Note: Without this extension, use Simple Mode (single mapping for all apps)${NC}"
            echo ""
        fi
    else
        # Other Wayland compositors (Sway, Hyprland, etc.)
        echo "  Detected compositor: ${XDG_CURRENT_DESKTOP:-Unknown}"
        echo -e "  ${GREEN}✓${NC} Window detection works natively"
    fi
fi

if [ "$NEED_RELOGIN" = "true" ]; then
    echo ""
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  IMPORTANT: You must LOG OUT and LOG BACK IN (or reboot)       ║${NC}"
    echo -e "${YELLOW}║  before the TourBox driver will work!                          ║${NC}"
    echo -e "${YELLOW}║                                                                ║${NC}"
    echo -e "${YELLOW}║  This is required for the input group membership to activate.  ║${NC}"
    if [ "$SERVICE_ENABLED" = "true" ]; then
        echo -e "${YELLOW}║                                                                ║${NC}"
        echo -e "${YELLOW}║  The service will start automatically when you log back in.    ║${NC}"
    else
        echo -e "${YELLOW}║                                                                ║${NC}"
        echo -e "${YELLOW}║  After logging back in, start the service with:                ║${NC}"
        echo -e "${YELLOW}║    systemctl --user start tourbox                              ║${NC}"
    fi
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
fi

echo "Enjoy your TourBox Elite!"
echo ""
