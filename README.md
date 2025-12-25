# TourBox Lite / Neo / Elite / Elite Plus Linux Driver

**Version 2.4.1**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Linux](https://img.shields.io/badge/platform-linux-lightgrey.svg)](https://www.linux.org/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**Author:** Scott Bowman ([AndyCappDev](https://github.com/AndyCappDev))
**Original Repository:** [github.com/AndyCappDev/tourbox-linux](https://github.com/AndyCappDev/tourbox-linux)

Linux driver for the TourBox Lite, Neo, Elite and Elite Plus by TourBox Tech Inc. Supports both **USB** and **Bluetooth LE** connections.

> **If you find this useful, please ⭐ star this repo (click the Star button in the top right) to help others discover it!**

## Device Compatibility

| Device | Status | Connection | Haptics | Notes |
|--------|--------|------------|---------|-------|
| TourBox Elite | ✅ Fully Tested | USB, Bluetooth | ✅ | Full support |
| TourBox Elite Plus | ✅ Fully Tested | USB, Bluetooth | ✅ | Full support |
| TourBox Neo | 🔄 Expected to Work | USB only | ❌ | [Help verify!](https://github.com/AndyCappDev/tourbox-linux/discussions/6) - Same protocol as Elite |
| TourBox Lite | 🔄 Expected to Work | USB, Bluetooth* | ❌ | [Help verify!](https://github.com/AndyCappDev/tourbox-linux/discussions/6) - Same protocol as Elite |

\* Bluetooth available on Lite Bluetooth model only; wired Lite is USB only.

> **Have a TourBox Neo or Lite?** We'd love your help testing compatibility! See our [call for testers](https://github.com/AndyCappDev/tourbox-linux/discussions/6) for details.

## Features

- ✅ **Graphical Configuration** - Full-featured GUI for visual configuration with live preview
- ✅ **USB and Bluetooth LE** - Connect via USB cable or wirelessly via Bluetooth
- ✅ **Haptic Feedback** - Configurable vibration feedback for rotary controls (Elite series only)
- ✅ **Application Profiles** - Different button mappings per application (Wayland only)
- ✅ **Window Detection** - Automatic profile switching based on focused window
- ✅ **Full Button Mapping** - All 20 controls configurable (buttons, knobs, scroll wheel, dial)
- ✅ **Modifier Keys** - Create over 250 unique key combinations per profile using physical buttons as modifiers
- ✅ **Import/Export Profiles** - Import and Export profiles to share with the community
- ✅ **Systemd Integration** - Runs as a user service, starts on login

## Requirements

### System Requirements

- Linux (Debian, Ubuntu, Fedora, Arch tested)
- Python 3.9+
- Bluetooth support (bluez) - for Bluetooth LE connection
- User must be in `dialout` group - for USB connection
- Build tools for compiling Python packages:
  - **Debian/Ubuntu:** `gcc python3-dev linux-headers-generic`
  - **Fedora/RHEL:** `gcc python3-devel kernel-headers`
  - **Arch:** `gcc python linux-headers`
- Running on Wayland (for app-specific profiles) or X11 (default profile only)

> **Note:** The `install.sh` script will check for these dependencies and tell you what to install if anything is missing.

### Python Dependencies

- **For GUI configuration tool:**
  - PySide6 >= 6.5.0 (Qt6 for Python)
  - qasync >= 0.24.0 (async Qt support)
  - Automatically installed by `install.sh`

### Additional Requirements for Profile Mode

- **For profile mode (app-specific mappings):**
  - **KDE Plasma:** `kdotool` required (see installation instructions below)
  - **GNOME:** [Focused Window D-Bus extension](https://extensions.gnome.org/extension/5592/focused-window-d-bus/) required (see installation instructions below)
  - **Sway/Hyprland:** No additional requirements

## Quick Install

### Connection Options

The driver supports two connection methods:

| Method | How to Use | Requirements |
|--------|------------|--------------|
| **USB** | Just plug in the USB-C cable | User in `dialout` group |
| **Bluetooth LE** | Turn on the TourBox (don't connect USB) | MAC address in config |

The driver **auto-detects** the connection type:
- Scans all `/dev/ttyACM*` devices and probes each for a TourBox response
- If a TourBox is found on USB, it uses that port
- Otherwise, it uses Bluetooth LE

> **Note:** For Bluetooth, you do NOT need to pair via system Bluetooth settings. The driver connects directly using the MAC address.

### Step 1: Find Your TourBox MAC Address (Bluetooth only)

**Skip this step if you only plan to use USB or your TourBox is not an Elite or Elite Plus.**  Though we recommend setting it up for Bluetooth on the Elite or Elite Plus in case you want to use Bluetooth later. The driver will still default to USB (when the USB cable is plugged in) even after Bluetooth is configured.

Make sure your TourBox Elite is powered on and NOT connected via USB.

```bash
bluetoothctl devices
```

Look for "TourBox Elite" or "TourBox Elite Plus" - copy the MAC address (format: `XX:XX:XX:XX:XX:XX`). You will need it for step 2.

Example output:
```
Device 12:34:56:78:9A:BC TourBox Elite
```

### Step 2: Run the Installer

```bash
git clone https://github.com/AndyCappDev/tourbox-linux.git
cd tourbox-linux
./install.sh
```

The installer will:
1. Create a Python virtual environment
2. Install the driver and dependencies
3. Set up your configuration file - It will ask for the Bluetooth MAC address from step 1.
4. Install and enable the systemd service

Log off and log back on again or reboot

> **Note:** If you haven't run the GUI yet and you are upgrading, your config may still be in the legacy format at `~/.config/tourbox/mappings.conf`. The GUI will automatically migrate it to the new format on first launch.

Log out and log back in or reboot to activate the driver.

### Additional Step for KDE Plasma Users

If you're using KDE Plasma on Wayland and want profile mode (app-specific mappings), you need to install `kdotool`:

```bash
# 1. Install build dependencies
sudo apt install build-essential pkg-config libdbus-1-dev libxcb1-dev

# 2. Install Rust (if not already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# Choose option 1 for standard installation when prompted
source $HOME/.cargo/env

# 3. Install kdotool
cargo install kdotool

# 4. Verify installation
kdotool --version
```

### Additional Step for GNOME Users

If you're using GNOME on Wayland and want profile mode (app-specific mappings), you need to install the "Focused Window D-Bus" extension:

1. Visit [Focused Window D-Bus extension page](https://extensions.gnome.org/extension/5592/focused-window-d-bus/)
2. Click the Install button
3. Verify installation:
   ```bash
   gnome-extensions list | grep focused-window-dbus
   # Should show: focused-window-dbus@flexagoon.com
   ```

Without this extension, profile mode will not work on GNOME (the driver will use the default profile for all apps).

**Note:** Sway and Hyprland users don't need any additional software.

## Updating

To update to the latest version:

```bash
cd /path/to/tourboxelite
git pull
./install.sh
```

The installer will automatically:
- Stop the running service if it's active
- Update all files and dependencies
- Preserve your existing configuration by default
- Ask if you want to restart the service with the new version

**Note:** It's safe to run the installer while the service is running - it will handle stopping and restarting automatically. Your configuration file and all profiles are preserved during updates.

## Configuration GUI

The driver includes a **graphical configuration tool** that makes it easy to configure button mappings without editing config files manually.

![TourBox Elite Configuration GUI](docs/images/gui-screenshot.png?v=2.4.1)

### Running the GUI

After installation, simply run:

```bash
tourbox-gui
```

You can also run it from the Application Launcher or pin it to your Application Manager after you run it for the first time for easy access.

### What You Can Do with the GUI

- **Visual Configuration** - See a diagram of your TourBox with visual feedback while editing control mappings
- **Profile Management** - Create, edit, and delete application-specific profiles
- **Window Matching** - Use "Capture Active Window" to detect windows for application profile matching
- **Testing** - Test your button mappings in your applications without having to quit the configuration GUI
- **Easy Key Assignment** - Point-and-click interface for keyboard shortcuts and mouse wheel actions
- **Check for Updates** - Easily check if a newer version is available (Help → Check for Updates)

**📖 See the [Complete GUI User Guide](docs/GUI_USER_GUIDE.md) for detailed instructions, tutorials, and troubleshooting.**

## Manual Installation

If you prefer manual setup, first ensure you have the build dependencies installed:

```bash
# Debian/Ubuntu
sudo apt install gcc python3-dev linux-headers-generic bluez python3-pip

# Fedora/RHEL
sudo dnf install gcc python3-devel kernel-headers bluez python3-pip

# Arch
sudo pacman -S gcc python linux-headers bluez python-pip
```

Then proceed with installation:

```bash
# 1. Create virtual environment
python3 -m venv venv

# 2. Install the driver and GUI dependencies
./venv/bin/pip install -e .
./venv/bin/pip install -r tourboxelite/gui/requirements.txt

# 3. Find your TourBox MAC address
bluetoothctl devices
# Look for "TourBox Elite"
# NOTE: Do NOT pair the device - pairing is not required and won't work.
#       The driver connects directly using the MAC address via BLE.

# 4. Copy and edit config (legacy format - GUI will migrate on first launch)
mkdir -p ~/.config/tourbox
cp tourboxelite/default_mappings.conf ~/.config/tourbox/mappings.conf
nano ~/.config/tourbox/mappings.conf
# Set your MAC address in [device] section

# 5. Set up udev rules for uinput access
echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload-rules
sudo modprobe uinput
echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf

# 6. Add user to input group (required for device access)
sudo usermod -a -G input $USER
# You'll need to log out and back in for this to take effect

# 7. Add user to dialout group (for USB access)
sudo usermod -a -G dialout $USER

# 8. Set up systemd service
mkdir -p ~/.config/systemd/user
nano ~/.config/systemd/user/tourbox.service
# Add the following content (replace /path/to/tourboxelite with actual path):
#
# [Unit]
# Description=TourBox Elite Driver
# After=graphical-session.target
#
# [Service]
# Type=simple
# ExecStart=/path/to/tourboxelite/venv/bin/python -m tourboxelite
# Restart=on-failure
# RestartSec=5
#
# [Install]
# WantedBy=default.target

# 9. Enable and start service
systemctl --user daemon-reload
systemctl --user enable tourbox
systemctl --user start tourbox
```

## Configuration

The easiest way to configure button mappings is with the **graphical configuration tool** (see below). For manual editing, profiles are stored in `~/.config/tourbox/profiles/` as individual `.profile` files.

> **Note:** Legacy configs at `~/.config/tourbox/mappings.conf` are automatically migrated when you first run the GUI.

### Legacy Format (Single File)

If editing manually before running the GUI, the config uses **profiles** - the `[profile:default]` section is required and contains your main button mappings:

```ini
[device]
mac_address = XX:XX:XX:XX:XX:XX

[profile:default]
# Button mappings
side = KEY_LEFTMETA
top = KEY_LEFTSHIFT
tall = KEY_LEFTALT
# ... more buttons

# Rotary controls
scroll_up = REL_WHEEL:1
scroll_down = REL_WHEEL:-1
knob_cw = KEY_LEFTCTRL+KEY_EQUAL    # Zoom in
knob_ccw = KEY_LEFTCTRL+KEY_MINUS   # Zoom out
# ... more rotary controls
```

### App-Specific Profiles (Wayland only)

On Wayland, you can add app-specific profiles that automatically switch when you focus different windows:

```ini
[profile:vscode]
window_class = Code
side = KEY_LEFTCTRL+KEY_SPACE          # Code completion
knob_cw = KEY_LEFTCTRL+KEY_EQUAL       # Zoom in
dpad_left = KEY_LEFTCTRL+KEY_PAGEUP    # Previous tab
dpad_right = KEY_LEFTCTRL+KEY_PAGEDOWN # Next tab
# ... all other buttons

[profile:firefox]
window_class = firefox-esr
side = KEY_LEFTALT+KEY_LEFT     # Back
top = KEY_LEFTALT+KEY_RIGHT     # Forward
knob_cw = KEY_LEFTCTRL+KEY_EQUAL    # Zoom in
# ... all other buttons
```

**Note:** On X11, only `[profile:default]` is used. App-specific profiles require Wayland.

### Haptic Feedback

The TourBox Elite has built-in haptic motors that provide vibration feedback when rotating the knob, scroll wheel, or dial. You can configure haptic strength per profile:

```ini
[profile:default]
haptic = strong    # off, weak, or strong

# Per-dial settings (optional, overrides global)
haptic.knob = weak
haptic.scroll = strong
haptic.dial = off
```

Configure haptic settings via the GUI (Profile Settings dialog) or edit the config file directly. Haptic feedback is only available on TourBox Elite / Elite Plus - the Neo model does not have haptic motors.

After editing, restart the service:
```bash
systemctl --user restart tourbox
```

## Usage

### Service Management

```bash
# Start the driver
systemctl --user start tourbox

# Stop the driver
systemctl --user stop tourbox

# Check status
systemctl --user status tourbox

# View logs
journalctl --user -u tourbox -f

# Restart after config changes
systemctl --user restart tourbox
```

### Manual Testing

Before running the driver manually, you must stop the systemd service first:

```bash
# Stop the service
systemctl --user stop tourbox

# Navigate to the tourboxelite directory
cd /path/to/tourboxelite

# Run directly in terminal with verbose logging (auto-detects USB/BLE)
./venv/bin/python -m tourboxelite -v

# Or force a specific connection mode:
./venv/bin/python -m tourboxelite --usb -v   # Force USB
./venv/bin/python -m tourboxelite --ble -v   # Force Bluetooth
```

Press `Ctrl+C` to stop.

When you're done testing, restart the service:

```bash
systemctl --user start tourbox
```

## Uninstall

```bash
./uninstall.sh
```

Or manually:

```bash
systemctl --user stop tourbox
systemctl --user disable tourbox
rm ~/.config/systemd/user/tourbox.service
rm -rf ~/.config/tourbox
systemctl --user daemon-reload
```

## Troubleshooting

### Service won't start

Check logs:
```bash
journalctl --user -u tourbox -n 50
```

Common issues:
- MAC address not set in config (for Bluetooth)
- TourBox not powered on or out of range (for Bluetooth)
- USB cable not connected or power-only cable (for USB)
- Missing Python dependencies
- Device already connected to another system

### USB not detected

If the driver doesn't detect your USB connection:

```bash
# Check if any ttyACM devices exist
ls -la /dev/ttyACM*

# Check if you're in the dialout group
groups | grep dialout

# If not in dialout group, add yourself:
sudo usermod -a -G dialout $USER
# Log out and back in for this to take effect
```

Make sure you're using a **data cable**, not a power-only charging cable. Try a different USB-C cable if the device doesn't appear.

**If you have multiple USB serial devices** (Arduino, etc.), the TourBox might not be on `/dev/ttyACM0`. The driver automatically scans all `/dev/ttyACM*` devices, but you can also specify the port manually:

```bash
# Find which port the TourBox is on
ls -la /dev/ttyACM*

# Run with a specific port
./venv/bin/python -m tourboxelite --usb --port /dev/ttyACM1

# Or set it in your config file (~/.config/tourbox/config.conf):
# [device]
# usb_port = /dev/ttyACM1
```

### "/dev/uinput" cannot be opened for writing

If you see this error in the logs, the uinput device permissions aren't set correctly. The install script should handle this automatically, but if needed, fix it manually:

```bash
# Create udev rule
echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' | sudo tee /etc/udev/rules.d/99-uinput.rules

# Reload udev and load module
sudo udevadm control --reload-rules
sudo modprobe uinput

# Ensure module loads on boot
echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf

# Verify permissions
ls -l /dev/uinput
# Should show: crw-rw---- 1 root input
```

### Profile switching not working

Profile mode requires Wayland. Verify:
```bash
echo $XDG_SESSION_TYPE
# Should output: wayland
```

Test window detection:
```bash
./venv/bin/python -m tourboxelite.window_monitor
```

### Buttons not responding

Make sure you're a member of the `input` group:
```bash
sudo usermod -a -G input $USER
# Log out and back in
```

## Documentation

- **[GUI User Guide](docs/GUI_USER_GUIDE.md)** - Complete guide for the graphical configuration tool
- [Configuration guide](docs/CONFIG_GUIDE.md) - Manual config file editing
- [Example configurations](tourboxelite/default_mappings.conf)
- [Development guide](docs/DEVELOPMENT.md)

## License

MIT License - See [LICENSE.txt](LICENSE.txt) file

