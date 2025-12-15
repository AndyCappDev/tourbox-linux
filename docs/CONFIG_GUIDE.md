# TourBox Elite Configuration Guide

This guide explains how to configure your TourBox Elite device and customize button mappings.

## Configuration File Structure

TourBox Elite supports two configuration formats:

### New Format (v2.3.0+) - Individual Profile Files

Profiles are stored as individual `.profile` files in `~/.config/tourbox/profiles/`:

```
~/.config/tourbox/
├── config.conf              # Device settings only
└── profiles/
    ├── default.profile      # Default profile (required)
    ├── davinci_resolve.profile
    ├── blender.profile
    └── ...
```

**Benefits:**
- Easy to share profiles with other users
- Import/export profiles via the GUI
- Better organization for many profiles

### Legacy Format - Single Config File

All profiles in one file at `~/.config/tourbox/mappings.conf`:

```ini
[device]
mac_address = XX:XX:XX:XX:XX:XX

[profile:default]
side = KEY_A
...

[profile:VSCode]
app_id = Code
...
```

**Note:** The GUI will offer to migrate your configuration to the new format on first launch. Your original config is backed up before migration.

---

## Quick Start

> **Note:** If you used `install.sh` from the README, you already have a config file set up with your MAC address. You can skip to step 2 below to edit your configuration.

### 1. Install the default config (if needed)

**Only run this if:**
- You didn't use the main `install.sh` script
- You want to reset your config back to defaults (WARNING: loses all customizations!)
- You want to get updated example profiles

```bash
./install_config.sh
```

This creates `~/.config/tourbox/mappings.conf`. If you don't have a MAC address configured yet, it will prompt you to enter it, otherwise it will preserve it.

**⚠️ WARNING:** Running this on an existing config will:
- Replace ALL your custom button mappings with defaults
- Replace ALL your custom profiles with example profiles
- Preserve ONLY your MAC address (everything else is lost)

### 2. Edit your configuration (optional)

```bash
nano ~/.config/tourbox/mappings.conf
# or
gedit ~/.config/tourbox/mappings.conf
```

### 3. Run the driver

```bash
# If MAC address is in config file:
sudo ./venv/bin/python -m tourboxelite.device_ble

# Or override with command line:
sudo ./venv/bin/python -m tourboxelite.device_ble D9:BE:1E:CC:40:D7
```

---

## Configuration Format

This config system uses **profiles** to define button mappings.

### Profile System

- All configs use `[profile:name]` sections
- The `[profile:default]` section is **required** and serves as the fallback
- On **X11**: Only `[profile:default]` is used (no automatic switching)
- On **Wayland**: Profiles automatically switch based on focused window

This means:
- X11 users simply configure `[profile:default]` and ignore app-specific profiles
- Wayland users can add app-specific profiles for automatic switching

---

## Configuration File Format

The config file uses INI format with these sections:

### `[device]` Section

Configures your TourBox Elite device connection.

**Format:** `setting = value`

**Available settings:**
- `mac_address` - Your TourBox Elite's Bluetooth MAC address (XX:XX:XX:XX:XX:XX)

**How to find your MAC address:**
```bash
bluetoothctl devices
```
Look for "TourBox Elite" in the output.

**Example:**
```ini
[device]
mac_address = D9:BE:1E:CC:40:D7
```

### `[profile:name]` Sections

Profiles define button and rotary control mappings. You can have multiple profiles.

**The `[profile:default]` section is REQUIRED** - it's used:
- On X11: Always (no profile switching)
- On Wayland: When no app-specific profile matches

**Format:**
```ini
[profile:name]
# Optional: Window matchers (for app-specific profiles on Wayland)
window_class = ApplicationClass
window_title = Window Title
app_id = app.id

# Button mappings
side = KEY_A
top = KEY_B
# ... (all buttons and rotary controls)

# Rotary mappings
scroll_up = REL_WHEEL:1
scroll_down = REL_WHEEL:-1
# ... (all rotary controls)
```

**Available buttons:**
- `side`, `top`, `tall`, `short` - Main buttons
- `c1`, `c2` - Right side buttons
- `dpad_up`, `dpad_down`, `dpad_left`, `dpad_right` - D-pad
- `scroll_click`, `knob_click`, `dial_click` - Clickable controls
- `tour` - Tour button

**Available rotary controls:**
- `scroll_up`, `scroll_down` - Scroll wheel
- `knob_cw`, `knob_ccw` - Knob (clockwise/counter-clockwise)
- `dial_cw`, `dial_ccw` - Dial (clockwise/counter-clockwise)

**Window Matchers:**

You can use one or more of these matchers in a profile. If you specify multiple matchers, the profile matches if **any** of them match (OR logic).

- **`window_class`** - Exact match, case-insensitive
  - Must match the entire class name
  - Example: `window_class = Code` matches class "Code" or "code", but NOT "VSCode"

- **`app_id`** - Exact match, case-insensitive
  - Must match the entire app_id
  - Example: `app_id = firefox-esr` matches "firefox-esr" or "Firefox-ESR", but NOT "firefox"

- **`window_title`** - Substring match, case-insensitive
  - Matches if the matcher appears anywhere in the title
  - Example: `window_title = Firefox` matches "Mozilla Firefox", "GitHub - Mozilla Firefox", etc.
  - Most flexible option for matching windows

**Matching Examples:**

```ini
# Match by exact class
[profile:vscode]
window_class = Code

# Match by partial title (more flexible)
[profile:browser]
window_title = Firefox

# Use multiple matchers - matches if ANY match
[profile:editor]
window_class = Code
app_id = code
window_title = Visual Studio
```

**Finding window_class for your applications:**

**Sway:**
```bash
swaymsg -t get_tree | grep app_id
# Focus the window, then look for "app_id": "..."
```

**Hyprland:**
```bash
hyprctl activewindow | grep class
# Focus the window, shows current window class
```

**Test script (any compositor):**

The window monitor tool will show you the window class, app_id, and title for any window you focus. This is the easiest way to find the correct values for your config file.

To run it:
```bash
# Navigate to the tourboxelite directory
cd /path/to/tourboxelite

# Run the window monitor
./venv/bin/python -m tourboxelite.window_monitor
```

The monitor will continuously display information about the currently focused window. As you switch between different applications, you'll see output like:

```
Active window: WindowInfo(app_id='firefox-esr', title='Mozilla Firefox', class='firefox-esr')
Active window: WindowInfo(app_id='code', title='README.md - Visual Studio Code', class='Code')
```

Use the `class` value in your `window_class` field or the `app_id` value in your `app_id` field in the config file. Press `Ctrl+C` to stop the monitor when you're done.

**Example profile configuration:**
```ini
[device]
mac_address = D9:BE:1E:CC:40:D7

# Default profile (fallback)
[profile:default]
side = KEY_LEFTMETA
top = KEY_LEFTSHIFT
scroll_up = REL_WHEEL:1
scroll_down = REL_WHEEL:-1

# VSCode profile
[profile:vscode]
window_class = Code
side = KEY_LEFTCTRL+KEY_SPACE     # Code completion
top = KEY_LEFTCTRL+KEY_SLASH      # Toggle comment
c1 = KEY_LEFTCTRL+KEY_Z           # Undo
c2 = KEY_LEFTCTRL+KEY_Y           # Redo
scroll_up = REL_WHEEL:1
scroll_down = REL_WHEEL:-1

# Firefox profile
[profile:firefox]
window_class = firefox
side = KEY_LEFTALT+KEY_LEFT       # Back
top = KEY_LEFTALT+KEY_RIGHT       # Forward
c1 = KEY_LEFTCTRL+KEY_W           # Close tab
c2 = KEY_LEFTCTRL+KEY_T           # New tab
scroll_up = REL_WHEEL:1
scroll_down = REL_WHEEL:-1
```

**How it works:**
1. Driver starts with `default` profile
2. Window monitor checks focused window every 200ms
3. When window changes, driver looks for matching profile
4. If match found, **instantly switches** button mappings
5. Console shows: `🎮 Switched to profile: vscode`
6. If no match, falls back to `default` profile

**Notes:**
- Profile switching is **instant** - no reconnection needed
- Only works on **Wayland** (X11 support possible in future)
- All profiles must have complete button/rotary definitions
- Profiles can have different capabilities (e.g., one uses REL_WHEEL, another uses keys)

---

## Action Formats

### Single Key

```ini
side = KEY_A
top = KEY_SPACE
```

### Key Combination

```ini
c1 = KEY_LEFTCTRL+KEY_C        # Ctrl+C (copy)
c2 = KEY_LEFTCTRL+KEY_V        # Ctrl+V (paste)
```

### Multiple Modifiers

```ini
c1 = KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_T   # Ctrl+Shift+T
```

### Mouse Wheel Events

```ini
scroll_up = REL_WHEEL:1         # Scroll up
scroll_down = REL_WHEEL:-1      # Scroll down
dial_cw = REL_HWHEEL:1          # Horizontal scroll right
dial_ccw = REL_HWHEEL:-1        # Horizontal scroll left
```

### No Action

```ini
knob_click = none               # Disable this button
```

---

## Haptic Feedback Configuration

The TourBox Elite has haptic motors that provide vibration feedback when rotating the knob, scroll wheel, or dial. You can configure both haptic **strength** (vibration intensity) and **speed** (detent spacing) in the config file.

> **Note:** Haptic feedback is only available on TourBox Elite and Elite Plus. The TourBox Neo does not have haptic motors.

### Global Haptic Settings (Per Profile)

Set haptic strength and speed for all rotary controls in a profile:

```ini
[profile:default]
haptic = strong         # Strength: off, weak, strong
haptic_speed = fast     # Speed: fast, medium, slow
```

### Per-Dial Haptic Settings

Override the global settings for specific dials:

```ini
[profile:default]
haptic = weak                  # Global strength
haptic_speed = fast            # Global speed
haptic.knob = strong           # Override strength for knob
haptic_speed.knob = slow       # Override speed for knob
haptic.scroll = off            # Override strength for scroll wheel
haptic_speed.scroll = medium   # Override speed for scroll wheel
```

### Per-Modifier-Combo Haptic Settings

Set haptic strength and speed for specific modifier+dial combinations:

```ini
[profile:default]
haptic = weak                        # Global strength
haptic_speed = fast                  # Global speed
haptic.knob = strong                 # Knob alone uses strong
haptic.knob.side = off               # side + knob uses no haptic
haptic_speed.knob.side = slow        # side + knob uses slow speed
haptic.scroll.tall = strong          # tall + scroll uses strong
haptic_speed.scroll.tall = medium    # tall + scroll uses medium speed
```

### Haptic Priority Order

When determining haptic settings for a rotary event, the driver checks in this order (same for both strength and speed):

1. **Per-combo setting** (`haptic.dial.modifier` / `haptic_speed.dial.modifier`) - Most specific
2. **Per-dial setting** (`haptic.dial` / `haptic_speed.dial`) - Dial-specific override
3. **Global setting** (`haptic` / `haptic_speed`) - Profile-wide default
4. **Default** - Off for strength, Fast for speed (if nothing configured)

### Haptic Strength Values

| Value | Description |
|-------|-------------|
| `off` | No vibration feedback |
| `weak` | Subtle vibration |
| `strong` | Pronounced vibration |

### Haptic Speed Values

| Value | Description |
|-------|-------------|
| `fast` | More detents per rotation, finer control |
| `medium` | Balanced detent spacing |
| `slow` | Fewer detents per rotation, coarser control |

### Example: Complete Haptic Configuration

```ini
[profile:photo_editing]
window_class = gimp
haptic = strong                 # Default: strong feedback
haptic_speed = fast             # Default: fine control

# Override for specific use cases
haptic.dial = weak              # Dial for fine adjustments
haptic_speed.dial = slow        # Fewer detents for sweeping movements
haptic.knob.tall = off          # No haptic when using tall+knob
haptic_speed.knob.tall = medium # Medium speed for tall+knob combo

# Button mappings...
scroll_up = KEY_LEFTCTRL+KEY_EQUAL
scroll_down = KEY_LEFTCTRL+KEY_MINUS
```

---

## Available Key Names

### Modifier Keys

```
KEY_LEFTCTRL, KEY_RIGHTCTRL
KEY_LEFTSHIFT, KEY_RIGHTSHIFT
KEY_LEFTALT, KEY_RIGHTALT
KEY_LEFTMETA (Super/Windows key)
```

### Letter Keys

```
KEY_A, KEY_B, KEY_C, ... KEY_Z
```

### Number Keys

```
KEY_0, KEY_1, KEY_2, ... KEY_9
```

### Function Keys

```
KEY_F1, KEY_F2, ... KEY_F12
```

### Navigation Keys

```
KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT
KEY_HOME, KEY_END
KEY_PAGEUP, KEY_PAGEDOWN
```

### Special Keys

```
KEY_SPACE, KEY_ENTER, KEY_TAB, KEY_ESC
KEY_BACKSPACE, KEY_DELETE, KEY_INSERT
KEY_CONTEXT_MENU (right-click menu)
KEY_ZOOMRESET, KEY_ZOOMIN, KEY_ZOOMOUT
```

### Mouse/Relative Events

```
REL_WHEEL:1      # Scroll up
REL_WHEEL:-1     # Scroll down
REL_HWHEEL:1     # Scroll right
REL_HWHEEL:-1    # Scroll left
```

---

## Example Configurations

All examples use the profile format. Simply copy the button mappings into your `[profile:default]` section, or create app-specific profiles on Wayland.

### For Photo Editing (GIMP)

```ini
[profile:gimp]
window_class = gimp
side = KEY_LEFTCTRL+KEY_Z      # Undo
top = KEY_LEFTCTRL+KEY_Y       # Redo
tall = KEY_B                   # Brush tool
short = KEY_SPACE              # Pan (hold space + drag)
c1 = KEY_LEFTBRACE            # Decrease brush size
c2 = KEY_RIGHTBRACE           # Increase brush size
scroll_up = REL_WHEEL:1       # Zoom in
scroll_down = REL_WHEEL:-1    # Zoom out
knob_cw = KEY_RIGHTBRACE      # Brush size up
knob_ccw = KEY_LEFTBRACE      # Brush size down
# ... (add remaining buttons)
```

### For Video Editing (DaVinci Resolve, Kdenlive)

```ini
[profile:kdenlive]
window_class = kdenlive
side = KEY_SPACE              # Play/Pause
top = KEY_LEFTCTRL+KEY_Z      # Undo
c1 = KEY_I                    # Mark in
c2 = KEY_O                    # Mark out
dpad_left = KEY_LEFT          # Previous frame
dpad_right = KEY_RIGHT        # Next frame
scroll_up = KEY_UP            # Previous track
scroll_down = KEY_DOWN        # Next track
knob_cw = KEY_EQUAL           # Zoom timeline in
knob_ccw = KEY_MINUS          # Zoom timeline out
# ... (add remaining buttons)
```

### For 3D Modeling (Blender)

```ini
[profile:blender]
window_class = blender
side = KEY_G                  # Grab/Move
top = KEY_R                   # Rotate
tall = KEY_S                  # Scale
short = KEY_SPACE             # Search
c1 = KEY_LEFTCTRL+KEY_Z      # Undo
c2 = KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_Z  # Redo
scroll_up = REL_WHEEL:1       # Zoom
scroll_down = REL_WHEEL:-1    # Zoom
knob_cw = KEY_PERIOD          # Rotate view right
knob_ccw = KEY_COMMA          # Rotate view left
# ... (add remaining buttons)
```

### For Software Development (VSCode)

```ini
[profile:vscode]
window_class = Code
side = KEY_LEFTCTRL+KEY_SPACE           # Code completion
top = KEY_LEFTCTRL+KEY_SLASH            # Toggle comment
c1 = KEY_LEFTCTRL+KEY_Z                 # Undo
c2 = KEY_LEFTCTRL+KEY_Y                 # Redo
tall = KEY_LEFTALT+KEY_ENTER            # Quick fix
short = KEY_F2                          # Rename
scroll_up = KEY_LEFTCTRL+KEY_UP         # Scroll up
scroll_down = KEY_LEFTCTRL+KEY_DOWN     # Scroll down
knob_cw = KEY_LEFTCTRL+KEY_EQUAL        # Increase font size
knob_ccw = KEY_LEFTCTRL+KEY_MINUS       # Decrease font size
# ... (add remaining buttons)
```

### For Web Browsing (Firefox)

```ini
[profile:firefox]
window_class = firefox
side = KEY_LEFTALT+KEY_LEFT             # Back
top = KEY_LEFTALT+KEY_RIGHT             # Forward
c1 = KEY_LEFTCTRL+KEY_T                 # New tab
c2 = KEY_LEFTCTRL+KEY_W                 # Close tab
tall = KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_T # Reopen closed tab
short = KEY_F5                          # Refresh
scroll_up = REL_WHEEL:1                 # Scroll up
scroll_down = REL_WHEEL:-1              # Scroll down
knob_cw = KEY_LEFTCTRL+KEY_TAB          # Next tab
knob_ccw = KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_TAB  # Previous tab
# ... (add remaining buttons)
```

---

## Config File Locations

The driver searches for config files in this order:

1. Custom path (via `-c` option)
2. `~/.config/tourbox/mappings.conf` (user config)
3. `/etc/tourbox/mappings.conf` (system-wide)

## MAC Address Priority

The driver looks for the MAC address in this order:

1. **Command line argument** - `python -m tourboxelite.device_ble D9:BE:1E:CC:40:D7`
2. **Environment variable** - `TOURBOX_MAC=D9:BE:1E:CC:40:D7 python -m tourboxelite.device_ble`
3. **Config file** - `mac_address` in `[device]` section

This allows you to:
- Store MAC in config for convenience
- Override with command line for testing multiple devices
- Use environment variables in scripts/systemd

---

## Testing Your Config

Before testing manually, stop the systemd service (if running):

```bash
systemctl --user stop tourbox
```

### Run with verbose logging to see button events:

```bash
cd /path/to/tourboxelite
./venv/bin/python -m tourboxelite.device_ble -v
```

The driver will read your MAC address from `~/.config/tourbox/mappings.conf`.

### Use a specific config file:

```bash
./venv/bin/python -m tourboxelite.device_ble -c my_custom_config.conf
```

When done testing, restart the service:

```bash
systemctl --user start tourbox
```

### Test in a text editor:

1. Start the driver
2. Open a text editor (gedit, nano, vim, VSCode)
3. Press each button and verify the expected action happens

---

## Troubleshooting

### Button doesn't do anything

- Check the config file syntax
- Verify the key name is correct (case-sensitive!)
- Check logs to see if button is detected:
  ```bash
  # If running as systemd service:
  journalctl --user -u tourbox -f

  # Or run manually with verbose mode:
  systemctl --user stop tourbox
  cd /path/to/tourboxelite
  ./venv/bin/python -m tourboxelite.device_ble -v
  ```

### Wrong action happens

- Look for typos in key combinations
- Check if the `+` separator is used correctly
- Verify you restarted the driver after editing

### "Unknown key name" error

- Key name must match exactly (e.g., `KEY_A`, not `KEY_a`)
- Check the "Available Key Names" section above
- See full list: `python3 -c "from evdev import ecodes; print([k for k in dir(ecodes) if k.startswith('KEY_')])"`

### Config not loading

- Check file permissions: `ls -l ~/.config/tourbox/mappings.conf`
- Verify INI syntax (no extra quotes, proper `=` signs)
- Run with `-v` to see which config file is loaded

### Profile Troubleshooting

#### Profiles not switching

**Check compositor detection:**
```bash
python3 -m tourboxelite.window_monitor
# Should show your compositor and window changes
```

If no compositor detected:
- Verify you're on Wayland: `echo $XDG_SESSION_TYPE` (should say "wayland")
- Check compositor-specific tool is installed:
  - Sway: `which swaymsg`
  - Hyprland: `which hyprctl`
  - GNOME: `which gdbus`
  - KDE: `which qdbus`

**Check window_class matching:**
```bash
# Find the correct window_class for your app
python3 -m tourboxelite.window_monitor
# Focus the application and note the window info
```

**Common issues:**
- `window_class` is case-insensitive but must match exactly
- VSCode is `Code` not `code` or `vscode`
- Firefox is `firefox` (lowercase)
- Check driver output for "Switched to profile" messages

#### Profile switching but buttons wrong

- Verify each profile has **all** button definitions
- Missing buttons in profile will do nothing
- Copy all buttons from `[profile:default]` then modify needed ones

#### "No 'default' profile found" warning

- Profile mode **requires** a `[profile:default]` section
- This is the fallback when no other profile matches
- Add it even if you only have one app-specific profile

#### Profile switching is slow

- Normal delay is 200ms (5 times per second)
- This is intentional to avoid excessive switching
- Profile switches are **instant** once detected

---

## Advanced: Finding More Key Codes

To see all available key codes:

```python
python3 -c "from evdev import ecodes as e; print([k for k in dir(e) if k.startswith('KEY_')])"
```

---

## Need Help?

- Check the default config: `tourboxelite/default_mappings.conf`
- See examples above
- Open an issue on GitHub with your config file and error messages

---

**Happy customizing!** 🎮
