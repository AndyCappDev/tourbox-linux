# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TourBox Linux is a Python driver for TourBox input devices (Elite, Elite Plus, Neo, Lite) on Linux. It supports USB serial and Bluetooth LE connections, includes a PySide6-based GUI for configuration, and runs as a systemd user service.

## Build & Development Commands

```bash
# Install dependencies (creates venv)
./install.sh

# Manual development setup
python3 -m venv venv
./venv/bin/pip install -e .
./venv/bin/pip install -r tourboxelite/gui/requirements.txt

# Run driver directly (verbose mode)
./venv/bin/python -m tourboxelite -v
./venv/bin/python -m tourboxelite --usb -v   # Force USB
./venv/bin/python -m tourboxelite --ble -v   # Force BLE

# Run GUI
./venv/bin/python -m tourboxelite.gui

# Service management
systemctl --user start tourbox
systemctl --user stop tourbox
systemctl --user restart tourbox
journalctl --user -u tourbox -f

# Test scripts
./venv/bin/python usb_test_tourbox.py    # Test USB button codes
./venv/bin/python ble_test_tourbox.py    # Test BLE button codes
./venv/bin/python -m tourboxelite.window_monitor  # Test window detection
```

## Architecture

The driver uses an abstract base class pattern with transport-specific implementations:

```
TourBoxBase (device_base.py)     - Abstract base with shared logic
├── TourBoxUSB (device_usb.py)   - USB serial via pyserial
└── TourBoxBLE (device_ble.py)   - Bluetooth LE via bleak
```

**Data Flow:**
1. Device sends button events (BLE notify or USB serial bytes)
2. Base class processes button codes → control names via state machine
3. Config loader maps controls → key events using profile system
4. Window monitor enables automatic profile switching (Wayland)
5. Virtual input device (uinput via evdev) sends Linux input events

**Key Modules:**
- `__main__.py` - Entry point with USB/BLE auto-detection
- `device_base.py` - Button processing, modifier handling (250+ combinations), uinput
- `config_loader.py` - INI parsing, profile system, button code mappings
- `profile_io.py` - Individual .profile files, migration, atomic writes
- `window_monitor.py` - Wayland compositor detection (GNOME, KDE, Sway, Hyprland)
- `haptic.py` - Haptic feedback strength/speed configuration

**GUI Package (`tourboxelite/gui/`):**
- `main_window.py` - Central coordinator
- `profile_manager.py` - Profile list CRUD operations
- `control_editor.py` - Key capture and mapping editor
- `controller_view.py` - SVG-based visual controller representation
- `config_writer.py` - Atomic config file writes with backup rotation
- `driver_manager.py` - systemd service status and control

## Configuration

User config location: `~/.config/tourbox/`
- `config.conf` - Main configuration file
- `profiles/` - Individual `.profile` files

Template: `tourboxelite/default_mappings.conf`

## Dependencies

Core: `bleak>=0.20.0`, `evdev>=1.6.0`, `pyserial>=3.5`
GUI: `PySide6>=6.5.0`, `qasync>=0.24.0`

System: Python 3.9+, bluez (BLE), user in `dialout` and `input` groups, udev rules for uinput

## Version Numbers

When bumping the version, update these files:
- `tourboxelite/__init__.py` - VERSION constant
- `tourboxelite/gui/__init__.py` - __version__ constant
- `README.md` - Version badge at top, image cache-bust parameter
- `docs/GUI_USER_GUIDE.md` - Image cache-bust parameter
