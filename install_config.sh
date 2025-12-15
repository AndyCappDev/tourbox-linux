#!/bin/bash
# Install TourBox Elite configuration file
#
# NOTE: If you used install.sh, you already have a config file!
#       This script is only needed if:
#       - You didn't use the main installer
#       - You want to reset to defaults (WARNING: loses customizations!)
#       - You want to get updated example profiles

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CONFIG_DIR="$HOME/.config/tourbox"
PROFILES_DIR="$CONFIG_DIR/profiles"
CONFIG_FILE="$CONFIG_DIR/mappings.conf"
DEFAULT_CONFIG="tourboxelite/default_mappings.conf"

echo "TourBox Elite Configuration Installer"
echo "======================================"
echo ""

# Check if using new format (profiles directory)
if [ -d "$PROFILES_DIR" ] && [ "$(ls -A "$PROFILES_DIR"/*.profile 2>/dev/null)" ]; then
    echo -e "${YELLOW}!${NC} You are using the new profile format."
    echo ""
    echo "Your profiles are stored in: $PROFILES_DIR"
    echo ""
    echo "To manage profiles, use the GUI:"
    echo "  tourbox-gui"
    echo ""
    echo "To reset to defaults, first remove the profiles directory:"
    echo "  rm -rf $PROFILES_DIR $CONFIG_DIR/config.conf"
    echo "  ./install_config.sh"
    echo ""
    exit 0
fi

# Create config directory if it doesn't exist
if [ ! -d "$CONFIG_DIR" ]; then
    echo "Creating config directory: $CONFIG_DIR"
    mkdir -p "$CONFIG_DIR"
fi

# Check if legacy config already exists
SKIP_MAC_PROMPT=0
if [ -f "$CONFIG_FILE" ]; then
    echo "Config file already exists: $CONFIG_FILE"
    echo ""
    echo "WARNING: Overwriting will replace:"
    echo "  - ALL your custom button mappings"
    echo "  - ALL your custom profiles"
    echo "  - Your MAC address will be preserved"
    echo ""
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    # Backup existing config
    BACKUP="$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    echo "Backing up existing config to: $BACKUP"
    cp "$CONFIG_FILE" "$BACKUP"

    # Extract existing MAC address if present
    EXISTING_MAC=$(grep -E "^mac_address\s*=" "$CONFIG_FILE" | sed 's/.*=\s*//')
    if [ -n "$EXISTING_MAC" ]; then
        echo "Found existing MAC address: $EXISTING_MAC"
        SKIP_MAC_PROMPT=1
    fi
fi

# Copy default config
echo "Installing default config to: $CONFIG_FILE"
cp "$DEFAULT_CONFIG" "$CONFIG_FILE"

# Prompt for MAC address if not found
if [ $SKIP_MAC_PROMPT -eq 0 ]; then
    echo ""
    echo "===================================="
    echo "TourBox Elite MAC Address Setup"
    echo "===================================="
    echo ""
    echo "To find your TourBox MAC address:"
    echo "  1. Turn on your TourBox Elite"
    echo "  2. Run: bluetoothctl devices"
    echo "  3. Look for 'TourBox Elite' in the output"
    echo ""
    read -p "Enter your TourBox Elite MAC address (XX:XX:XX:XX:XX:XX) or press Enter to skip: " MAC_ADDRESS

    if [ -n "$MAC_ADDRESS" ]; then
        # Validate MAC address format
        if [[ $MAC_ADDRESS =~ ^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$ ]]; then
            echo "Setting MAC address in config: $MAC_ADDRESS"
            sed -i "s/mac_address = .*/mac_address = $MAC_ADDRESS/" "$CONFIG_FILE"
        else
            echo "Warning: Invalid MAC address format. Please edit the config file manually."
        fi
    else
        echo "Skipped MAC address setup. You'll need to edit the config file manually."
    fi
else
    # Restore existing MAC address
    sed -i "s/mac_address = .*/mac_address = $EXISTING_MAC/" "$CONFIG_FILE"
    echo "Restored existing MAC address: $EXISTING_MAC"
fi

echo ""
echo "===================================="
echo "Configuration Mode Selection"
echo "===================================="
echo ""
echo "The TourBox driver supports two configuration modes:"
echo ""
echo "1. SIMPLE MODE"
echo "   - Single mapping for all applications"
echo "   - Works everywhere"
echo "   - Currently ACTIVE in your config"
echo ""
echo "2. PROFILE MODE (Wayland only)"
echo "   - Different mappings per application"
echo "   - Automatically switches based on focused window"
echo "   - Supports Sway, Hyprland, GNOME, KDE"
echo ""

# Check if running Wayland
if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    echo "✓ Detected Wayland session - Profile mode is available!"
    echo ""
    read -p "Would you like to enable profile mode? (y/N): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Enabling profile mode..."
        echo ""
        echo "Available profile examples:"
        echo "  - default (fallback profile)"
        echo "  - vscode (VSCode/Code editor)"
        echo "  - firefox (Firefox browser)"
        echo "  - gimp (GIMP image editor)"
        echo "  - blender (Blender 3D)"
        echo ""
        echo "Note: You'll need to edit $CONFIG_FILE"
        echo "and uncomment the [profile:*] sections you want to use."
        echo ""
        echo "IMPORTANT: You MUST uncomment at least [profile:default]!"
        echo ""
        read -p "Open config file in editor now? (Y/n): " -n 1 -r
        echo ""

        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            # Try to find an editor
            if command -v nano &> /dev/null; then
                nano "$CONFIG_FILE"
            elif command -v vim &> /dev/null; then
                vim "$CONFIG_FILE"
            elif command -v vi &> /dev/null; then
                vi "$CONFIG_FILE"
            else
                echo "No editor found. Please edit manually: $CONFIG_FILE"
            fi
        else
            echo ""
            echo "Remember to uncomment profile sections in: $CONFIG_FILE"
        fi

        echo ""
        echo "To find window_class for your apps:"
        echo "  python3 -m tourboxelite.window_monitor"
        echo ""
    else
        echo ""
        echo "Using simple mode (current config is already set up)"
    fi
else
    echo "ℹ Running X11 session - Profile mode requires Wayland"
    echo "  Continuing with simple mode"
fi

echo ""
echo "===================================="
echo "✓ Installation complete!"
echo "===================================="
echo ""
echo "Configuration file: $CONFIG_FILE"
echo ""
echo "Next steps:"
echo "  1. Run the driver: sudo ./venv/bin/python -m tourboxelite.device_ble"
echo "  2. Test your TourBox buttons"
echo ""
echo "To customize button mappings:"
echo "  nano $CONFIG_FILE"
echo ""
echo "For profile mode tips:"
echo "  - Test window detection: python3 -m tourboxelite.window_monitor"
echo "  - See examples in config file (commented out)"
echo "  - Read CONFIG_GUIDE.md for full documentation"
echo ""
echo "After editing config, restart the TourBox driver."
echo ""
