# kdotool - Window Detection for KDE Plasma

## What is kdotool?

`kdotool` is a Rust-based utility similar to `xdotool` but designed for Wayland compositors, specifically KDE Plasma (KWin). It allows querying and manipulating windows on KDE Plasma running Wayland.

## Why is it needed?

The TourBox Elite driver uses window detection to enable **Profile Mode** - automatic switching of button mappings based on which application you're using.

Different Wayland compositors provide different APIs for window information:
- **GNOME (Mutter)** - Uses D-Bus API (built-in)
- **Sway** - Uses IPC socket (built-in)
- **Hyprland** - Uses IPC socket (built-in)
- **KDE Plasma (KWin)** - Requires external tool like `kdotool`

## Do I need kdotool?

**You need kdotool ONLY if:**
- ✅ You're using KDE Plasma
- ✅ You're running Wayland (not X11)
- ✅ You want to use Profile Mode (app-specific button mappings)

**You DON'T need kdotool if:**
- ❌ You're using GNOME, Sway, or Hyprland
- ❌ You're running X11
- ❌ You only use the default profile (no app-specific profiles)

## Installation

### 1. Install System Dependencies

Before installing kdotool, you need some system libraries for compilation:

```bash
sudo apt install build-essential pkg-config libdbus-1-dev libxcb1-dev
```

**What these are:**
- `build-essential` - GCC compiler and basic build tools
- `pkg-config` - Helper tool for compiling applications
- `libdbus-1-dev` - D-Bus development headers (kdotool uses D-Bus internally to talk to KWin)
- `libxcb1-dev` - X C Bindings development headers (for X11/Wayland window management)

**Note:** Our TourBox driver doesn't use D-Bus directly - it calls `kdotool` as a command-line tool. But kdotool itself needs these libraries to compile because it uses D-Bus to communicate with KWin.

### 2. Install Rust (if not already installed)

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

### 3. Install kdotool

```bash
cargo install kdotool
```

This compiles and installs `kdotool` to `~/.cargo/bin/kdotool`.

**Note:** Compilation may take a few minutes the first time.

### Verify Installation

```bash
kdotool --version
# Should output: kdotool v0.2.1 (or similar)
```

### Add to PATH (if needed)

If `kdotool --version` doesn't work, add Cargo bin to your PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## How it's used

### Architecture

```
TourBox Driver (Python)
    ↓ subprocess.run()
kdotool (Rust binary)
    ↓ D-Bus
KWin (KDE Window Manager)
```

**The flow:**
1. Our Python driver calls `kdotool` as a command-line tool (subprocess)
2. `kdotool` communicates with KWin via D-Bus
3. KWin returns window information to kdotool
4. kdotool outputs the result to stdout
5. Our driver reads the output and switches profiles

**Why not use D-Bus directly?** KDE Plasma 6 changed the D-Bus API, making it complex and undocumented. `kdotool` abstracts this complexity and provides a simple command-line interface.

### Comparison with Other Compositors

Different Wayland compositors provide different APIs for window detection:

| Compositor | Method | What TourBox Driver Uses |
|------------|--------|--------------------------|
| **GNOME** | D-Bus API | Python D-Bus library directly |
| **Sway** | IPC Socket | Python socket connection directly |
| **Hyprland** | IPC Socket | Python socket connection directly |
| **KDE Plasma** | D-Bus (complex) | `kdotool` command-line tool → D-Bus |

**Why KDE is different:** KDE Plasma 6's D-Bus API for window management is complex and poorly documented. Using `kdotool` as an abstraction layer makes the implementation much simpler and more reliable.

### Commands Used

The TourBox driver uses `kdotool` to query window information:

```bash
# Get active window class
kdotool getactivewindow getwindowclassname

# Get active window title
kdotool getactivewindow getwindowname
```

This information is used to match against profile definitions in your config:

```ini
[profile:vscode]
window_class = Code
# Button mappings specific to VS Code
```

When you focus VS Code, the driver detects "Code" as the window class and switches to the vscode profile.

## Troubleshooting

### Compilation errors when installing kdotool

If `cargo install kdotool` fails with errors like:
```
error: failed to run custom build command for `xxx`
could not find system library 'dbus-1'
pkg-config has not been configured to support cross-compilation
```

**Solution:** Install the required system dependencies:
```bash
sudo apt install build-essential pkg-config libdbus-1-dev libxcb1-dev
```

Then try again:
```bash
cargo install kdotool
```

**Common missing dependencies and their errors:**
- Missing `pkg-config`: "pkg-config has not been configured"
- Missing `libdbus-1-dev`: "could not find system library 'dbus-1'"
- Missing `libxcb1-dev`: "could not find library 'xcb'"
- Missing `build-essential`: "linker 'cc' not found"

### kdotool not found

```bash
# Check if installed
ls -la ~/.cargo/bin/kdotool

# If not found, install it
cargo install kdotool
```

### kdotool installed but not working

```bash
# Test manually
kdotool getactivewindow getwindowclassname

# Should output the class of currently focused window
```

If it returns nothing or errors, kdotool might not be compatible with your KDE Plasma version.

### Profile switching still not working

```bash
# Test window detection directly
./venv/bin/python -m tourboxelite.window_monitor

# This will show:
# - Detected compositor
# - Current window info
# - Whether kdotool is being used
```

### Alternative: Use Default Profile Only

If kdotool doesn't work or you don't want to install it, you can use only the default profile without app-specific profiles. The driver will always use `[profile:default]` mappings regardless of which window is focused.

## Technical Details

### kdotool source

- GitHub: https://github.com/jinliu/kdotool
- Written in: Rust
- License: MIT
- Platform: Linux (KDE Plasma/Wayland)

### How TourBox finds kdotool

The driver searches for `kdotool` in these locations (in order):

1. `kdotool` in PATH
2. `~/.cargo/bin/kdotool` (Cargo default)
3. `/usr/local/bin/kdotool` (system-wide)
4. `/usr/bin/kdotool` (package manager)

See `tourboxelite/window_monitor.py` function `_find_kdotool()` for implementation.

### Polling Interval

The driver polls for window changes every 200ms (default). You can adjust this in `device_ble.py`:

```python
# Start window monitoring with custom interval
await self.window_monitor.monitor_window_changes(
    self.on_window_change,
    interval=0.2  # seconds
)
```

## Alternatives to kdotool

If you're on KDE Plasma and kdotool doesn't work, there are a few alternatives:

### 1. Use KWin Scripts (experimental)

The repository includes `kwin_active_window.js` which is a KWin script approach (not currently used).

### 2. D-Bus API (KDE 5 only)

Older KDE Plasma 5 had D-Bus APIs for window info. These were removed in Plasma 6, which is why kdotool is needed.

### 3. Use Default Profile Only

Just use the `[profile:default]` mappings for all applications (no window detection needed).

## Summary

- **kdotool** enables Profile Mode on KDE Plasma/Wayland
- **System dependencies needed:** `build-essential pkg-config libdbus-1-dev libxcb1-dev`
- **Install with:** `cargo install kdotool` (after installing Rust and dependencies)
- Only needed for KDE Plasma users who want app-specific profiles
- Other compositors (GNOME, Sway, Hyprland) don't need it
- Without kdotool, the driver uses `[profile:default]` for all applications

## Quick Install Reference

```bash
# Complete installation for KDE Plasma users
sudo apt install build-essential pkg-config libdbus-1-dev libxcb1-dev
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
cargo install kdotool
kdotool --version  # Verify
```
