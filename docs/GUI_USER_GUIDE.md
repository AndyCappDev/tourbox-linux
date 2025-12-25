# TourBox Configuration GUI - User Guide

**Version:** 1.5
**Last Updated:** 2025-12-22

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Understanding the Interface](#understanding-the-interface)
4. [Basic Tasks](#basic-tasks)
5. [Working with Profiles](#working-with-profiles)
6. [Importing and Exporting Profiles](#importing-and-exporting-profiles)
7. [Configuring Button Mappings](#configuring-button-mappings)
8. [Using Modifier Buttons](#using-modifier-buttons)
9. [Configuring Haptic Feedback](#configuring-haptic-feedback)
10. [Tips & Tricks](#tips--tricks)
11. [Checking for Updates](#checking-for-updates)
12. [Troubleshooting](#troubleshooting)


---

## Introduction

The TourBox Configuration GUI is a graphical application that lets you configure your TourBox controller without manually editing configuration files. With this tool, you can:

- **Visually configure** all 20 controls (buttons, dials, scroll wheel, knob)
- **Press physical buttons** on your TourBox to instantly select controls for editing
- **Create over 250 unique key combinations per profile** using modifier buttons
- **Create application-specific profiles** that automatically switch based on the active window
- **Import and export profiles** to share with other users
- **Configure haptic feedback** for rotary controls (knob, scroll wheel, dial)
- **Manage multiple profiles** with an intuitive interface
- **Test configurations** without leaving the Configuration GUI

---

## Getting Started

### Launching the GUI

Simply run:

```bash
tourbox-gui
```

**What happens on launch:**

1. If you have a legacy config (`mappings.conf`), it will be automatically migrated to individual profile files
2. Loads your profiles from `~/.config/tourbox/profiles/`
3. Displays all profiles and button mappings

**On exit:**

- Prompts you to save any unsaved changes

> **Note:** The driver continues running while the GUI is open. When you save changes, the configuration is automatically reloaded and applied without restarting the driver.

---

## Understanding the Interface

![TourBox Configuration GUI](images/gui-screenshot.png?v=2.4.1)

The GUI has a 4-panel layout:

```
┌─────────────────────┬──────────────────────────┐
│                     │                          │
│  1. Controller      │  2. Controls             │
│     View            │     Configuration        │
│                     │     (Button List)        │
│  (Visual TourBox)   │                          │
│                     │                          │
├─────────────────────┼──────────────────────────┤
│                     │                          │
│  3. Profiles        │  4. Control Editor       │
│                     │                          │
│  (Profile List)     │  (Edit Mappings)         │
│                     │                          │
└─────────────────────┴──────────────────────────┘
```

### 1. Controller View (Top-Left)

- **Visual representation** of the TourBox controller
- **Highlights controls** when you select them from the list
- Shows which button you're currently editing

### 2. Profiles (Bottom-Left)

- **List of all available profiles** with three columns:
  - **Name** - Profile name (with warning icon if conflicts exist)
  - **Window** - Window matching rules (app_id or window_class)
  - **Active** - Checkbox to enable/disable the profile
- The **default profile** is always present, cannot be deleted, and is always active
- **Active checkbox** - Controls whether a profile participates in automatic window matching:
  - Checked: Profile will activate when its window rules match
  - Unchecked: Profile is disabled and will be skipped during matching
  - Changes take effect immediately (no save required)
- **Conflict warning** - Profiles with an orange **⚠** icon have conflicting window rules with another active profile. Hover to see which profiles conflict. Only the first alphabetically will be used.
- Buttons to **create**, **edit**, **delete**, **import**, and **export** profiles

### 3. Controls Configuration (Top-Right)

- **Table showing all 20 controls** with their current mappings
- Displays human-readable action names (e.g., "Ctrl+C", "Wheel Up")
- Click any control to **select it for editing**
- Shows "(unmapped)" for controls with no action assigned

### 4. Control Editor (Bottom-Right)

- **Configure the selected control's action**
- Choose action type: Keyboard, Mouse Wheel, or None
- Set modifier keys (Ctrl, Alt, Shift, Super)
- Select keys or mouse wheel directions
- Create and edit modifier combinations
- **Apply** button saves changes to memory (not actually saved to the config file yet)

### Menu Bar & Toolbar

- **File Menu:**
  - Save (Ctrl+S) - Write changes to config file and apply them
  - Import Profile - Import a profile
  - Export Profile - Export a profile
  - Quit - Exit the application

- **Help Menu:**
  - Check for Updates - Check GitHub for a newer version
  - User Guide - Open this documentation
  - About - Show version and author information

- **Toolbar:** Quick access button for Save

- **Status Bar:** Shows current status, profile name, and operation feedback

### Using Physical Buttons to Select Controls

You can **press any button or rotate any dial on your TourBox** to instantly select that control for editing in the GUI. This is much faster than clicking through the Controls Configuration table.

**How it works:**
- The driver includes a built-in `TourBox GUI` profile that activates when the GUI window is focused
- Physical button presses are mapped to keyboard shortcuts that the GUI recognizes
- The GUI automatically selects the corresponding control for editing

**Example:** To edit the "knob clockwise" mapping:
1. Make sure the GUI window is focused
2. Rotate the knob clockwise on your TourBox
3. The "Knob Clockwise" control is automatically selected in the Controls Configuration table
4. The Control Editor loads the current mapping, ready to edit

> **Note:** This requires the TourBox driver to be running. If you stopped the driver for testing, physical button selection won't work until you restart it.

---

## Basic Tasks

### Task 1: Change a Button Mapping

**Example:** Change the "side" button to Ctrl+C (copy)

1. **Select the profile** you want to edit from the Profiles list (e.g., "default")
2. **Click "side"** in the Controls Configuration table
   - The controller view highlights the side button
   - The Control Editor loads the current mapping
3. In the Control Editor:
   - Select **"Keyboard"** as the action type
   - Check the **"Ctrl"** modifier box
   - Type **"c"** in the **"Key:"** text input field
4. Click **"Apply"**
   - The Controls Configuration table updates to show "Ctrl+C"
   - Window title shows an asterisk (*) indicating unsaved changes
5. Click **"Save"** (toolbar or Ctrl+S)
   - Creates a timestamped backup of your profile
   - Writes the changes to `~/.config/tourbox/profiles/<profile>.profile`
   - Automatically applies the new configuration
   - Success dialog confirms the save

**Result:** The "side" button now immediately sends Ctrl+C when pressed! The new configuration was applied automatically.

### Task 2: Create a New Application-Specific Profile

**Example:** Create a profile for Visual Studio Code

1. Click the **"+"** button below the Profiles list
2. In the dialog:
   - Enter profile name: **"vscode"** and click **OK**
   - Choose **Yes** if you would like to copy settings for the currently selected profile
3. The new profile is created and selected
4. A dialog appears asking if you would like to set up window matching rules:
   - Click **Yes** 
   - Click **"Capture Active Window"**
   - A dialog box appears giving you 5 seconds to click on VS Code window
   - The GUI auto-fills the App ID and Window Class fields
   - Click **Apply**
5. Customize button mappings for VS Code (see Task 1)
6. Click **"Save"** to write the profile to config

**Result:** When you focus a VS Code window, this profile automatically activates!

### Task 3: Test Your Configuration

**Example:** Test button mappings with the physical device

1. Make changes to button mappings (see Task 1)
2. Click **"Save"** (toolbar or Ctrl+S)
   - Changes are written to config and applied automatically
3. **Switch to your target application** (e.g., text editor, browser)
4. **Press buttons on your physical TourBox**
   - Actions are sent immediately to your application
   - Verify that mappings work as expected
5. **Switch back to the GUI** to make further adjustments if needed

**Result:** You can rapidly iterate: edit → save → test in app → edit → save without closing anything!

---

## Working with Profiles

### What Are Profiles?

Profiles are **collections of button mappings** that can automatically activate based on the active application window. This lets you have different button behaviors for different programs.

**Example use cases:**
- **Default profile:** General mappings for desktop navigation
- **GIMP profile:** Brush size, zoom, undo for image editing
- **Firefox profile:** Tab switching, zoom, page navigation
- **VS Code profile:** Comment code, find, formatting shortcuts

### The Default Profile

- Always present and **cannot be deleted**
- Used when no other profile matches the active window
- Good place to put general-purpose mappings

### Creating Profiles

**Two ways to create a profile:**

1. **Based on selected profile**
   - Copies all button mappings from the currently selected profile
   - Good starting point - customize from there
   - Saves time vs. configuring everything from scratch

2. **Empty profile**
   - No mappings configured
   - All controls show "(unmapped)"
   - Good if you want a completely custom layout

**Steps:**
1. Click **"+"** button
2. Enter a unique name
3. Choose copy or empty
4. Configure window matching rules (next section)

### Window Matching Rules

Profiles activate when the window properties match your rules. You can match by:

- **App ID** - Wayland application identifier (e.g., `code`, `firefox`)
- **Window Class** - X11/Wayland window class (e.g., `firefox-esr`, `Code`)

**Capturing Window Info Automatically:**

1. Click **"⚙"** (settings) button next to a profile
2. Click **"Capture Active Window"** button
3. **Within 5 seconds**, click on the window you want to match
4. The GUI auto-fills the App ID and Window Class fields
5. Edit/clear fields as needed
6. Click **Apply**

**Tips:**
- You can use **one, or both** matching fields
- Any one of the fields must match for the profile to activate
- Leave fields blank to ignore that matching criterion
- We recommend you leave/use both matching methods

### Editing Profiles

1. Select the profile in the Profiles list
2. Click the **"⚙"** (settings) button
3. Edit name and/or window matching rules
4. Click **Apply** (changes saved to memory)
5. Click **Save** button to write to config file

> **Note:** You cannot edit the default profile's settings (name/window matching) - only its button mappings.

### Deleting Profiles

1. Select the profile to delete
2. Click the **"-"** button
3. Confirm deletion in the dialog

> **Warning:** Deletion is permanent!

### Enabling and Disabling Profiles

Each profile has an **Active** checkbox that controls whether it participates in automatic window matching.

**To enable/disable a profile:**
1. Find the profile in the Profiles list
2. Click the checkbox in the **Active** column
3. The change takes effect immediately (driver reloads automatically)

**Use cases for disabling profiles:**
- **Multiple profiles for the same app** - Create variants (e.g., "VS Code - Editing" and "VS Code - Debugging") and enable only the one you want active
- **Temporary disable** - Turn off a profile without deleting it
- **Testing** - Disable app-specific profiles to test with the default profile

> **Note:** The default profile is always active and cannot be disabled.

### Profile Conflicts

When two or more **active** profiles match the same application (same window_class or app_id), a conflict exists. The GUI warns you about this:

- Conflicting profiles show an orange **⚠** icon next to their name
- Hover over the profile name to see which profiles it conflicts with
- Only the **first profile alphabetically** will be used when the application is focused

**To resolve a conflict:**
1. **Disable one profile** - Uncheck the Active box for profiles you don't want to use
2. **Change window matching** - Edit one profile's app_id/window_class to be more specific
3. **Rename** - If you want a different profile to take priority, rename it to sort first alphabetically

**Example conflict:**
- "VS Code" profile with `window_class = Code`
- "VS Code Dev" profile with `window_class = Code`

Both match VS Code windows. "VS Code" wins because it sorts before "VS Code Dev" alphabetically. To use "VS Code Dev" instead, disable "VS Code" by unchecking its Active box.

### Profile Switching

When the TourBox driver is running:

- The driver monitors the active window every 200ms
- Compares window properties against all **active** profile rules
- Switches to the first matching profile (alphabetically if multiple match)
- Falls back to default if no match

**In the GUI:**
- Simply click a profile name to switch to it
- The Controls Configuration table updates

---

## Importing and Exporting Profiles

### Why Import/Export?

- **Share profiles** with other TourBox users
- **Backup** your custom configurations
- **Transfer** profiles between computers
- **Community sharing** - download profiles from other users

### Exporting a Profile

1. **Select the profile** you want to export in the Profiles panel
2. **Click the Export button** (or use **File > Export Profile...**)
3. **Choose a location** and filename in the save dialog
4. **Click Save** to create the `.profile` file

The exported file contains all profile settings:
- Button and rotary control mappings
- Modifier button configurations
- Haptic feedback settings
- Window matching rules
- Comments

### Importing a Profile

1. **Click the Import button** (or use **File > Import Profile...**)
2. **Select a `.profile` file** to import
3. **Handle name conflicts** (if any):
   - **Replace** - Delete existing profile and import the new one
   - **Rename** - Give the imported profile a new name
4. **The profile appears** in your Profiles panel

### Configuration Migration

When you first launch the GUI after upgrading to version 2.3.0 or later, you may see a migration dialog. This converts your existing configuration from the old single-file format to the new individual profile files.

**Benefits of migration:**
- Each profile is stored as a separate `.profile` file
- Easy to share, backup, and manage profiles
- Better organization for users with many profiles

**Migration is safe:**
- Your original configuration is backed up
- Your existing profile settings are preserved during migration

---

## Configuring Button Mappings

### The 20 TourBox Controls

Your TourBox has these controls:

**Buttons (7):**
- `side` - Large side button
- `top` - Top button
- `tall` - Tall button (bottom-left)
- `short` - Short button (bottom-right)
- `c1` - C1 button
- `c2` - C2 button
- `tour` - Tour button (center)

**D-Pad (4):**
- `dpad_up`, `dpad_down`, `dpad_left`, `dpad_right`

**Scroll Wheel (3):**
- `scroll_up` - Scroll wheel up
- `scroll_down` - Scroll wheel down
- `scroll_click` - Press the scroll wheel

**Knob (3):**
- `knob_cw` - Rotate knob clockwise
- `knob_ccw` - Rotate knob counter-clockwise
- `knob_click` - Press the knob

**Dial (3):**
- `dial_cw` - Rotate dial clockwise
- `dial_ccw` - Rotate dial counter-clockwise
- `dial_click` - Press the dial

### Action Types

Each control can be mapped to one of these action types:

#### 1. Keyboard Action

Send a keyboard key press (with optional modifiers).

**Modifiers:** (can combine multiple)
- Ctrl
- Alt
- Shift
- Super (Windows/Command key)

**Keys:**
- **Typeable characters:** Just type them in the text field
  - Letters: a-z (lowercase sends lowercase, uppercase sends uppercase)
  - Numbers: 0-9
  - Symbols: `-` `=` `[` `]` `;` `'` `` ` `` `\` `,` `.` `/`

- **Special keys:** Select from dropdown
  - Control: Enter, Escape, Tab, Space, Backspace, Delete, Insert
  - Arrows: Up, Down, Left, Right
  - Navigation: Home, End, Page Up, Page Down
  - Function: F1-F12
  - Zoom: Zoom In, Zoom Out, Zoom Reset
  - Other: Context Menu

**Examples:**
- `Ctrl+C` - Click Ctrl, type "c"
- `Ctrl+Shift+Z` - Click Ctrl and Shift, type "z"
- `Alt+F4` - Click Alt, select "F4" from dropdown
- `]` - Just type "]" (closing bracket)
- `Super` - Click Super only (no key)

**Tips:**
- Either use the **text input** OR the **dropdown**, not both
- Modifier-only mappings are valid (e.g., just "Ctrl" or "Alt")
- The GUI shows human-readable names in the controls list

#### 2. Mouse Wheel

Simulate mouse wheel scrolling.

**Directions:**
- Vertical Up - Scroll up
- Vertical Down - Scroll down
- Horizontal Left - Scroll left (for apps that support horizontal scrolling)
- Horizontal Right - Scroll right

**Common uses:**
- Map `Knob Clockwise` to Wheel Up and `Knob Counter-CW` to Wheel Down for scrolling
- Map `Dial Clockwise`/`Dial Counter-CW` for zooming (if app supports Ctrl+Wheel)

#### 3. None (Unmapped)

The control does nothing when pressed.

**Use cases:**
- Disable a button you don't use
- Temporarily disable a control while testing
- Prevent accidental presses

---

## Using Modifier Buttons

### What Are Modifier Buttons?

**Modifier buttons** are a powerful feature that allows you to create **over 250 unique key combinations per profile** using your TourBox's physical buttons. When a button acts as a modifier, it can be combined with any other control to trigger different actions.

**Example Workflow:**
- `Side` button alone → Send Super key (open application menu)
- `Side + Top` button → Send Ctrl+C (copy)
- `Side + Tall` button → Send Ctrl+V (paste)
- `Side + Short` button → Send Ctrl+Z (undo)
- `Side + C1` button → Send Ctrl+Shift+Z (redo)
- ... and so on!

This gives you multiple "layers" of functionality from the same physical buttons, similar to how Shift, Ctrl, and Alt keys work on your keyboard.

### Which Buttons Can Be Modifiers?

The **14 physical buttons** that can act as modifiers:

**Main Buttons (7):**
- side, top, tall, short, c1, c2, tour

**D-Pad Buttons (4):**
- dpad_up, dpad_down, dpad_left, dpad_right

**Click Buttons (3):**
- scroll_click, knob_click, dial_click

**Note:** Only the **rotational movements** cannot be modifiers:
- scroll_up/scroll_down (scroll wheel rotation)
- knob_cw/knob_ccw (knob rotation)
- dial_cw/dial_ccw (dial rotation)

However, the **click actions** (scroll_click, knob_click, dial_click) **can** be modifiers and can also be combined with other modifiers.

### Configuring a Modifier Button

**Example:** Make the "side" button a modifier

1. **Select the profile** you want to edit (e.g., "default")
2. **Click the "side" button** in the Controls Configuration table
3. In the Control Editor:
   - Configure the **base action** (what happens when pressed alone):
     - Select **"Keyboard"** as the action type
     - Check the **"Super"** modifier
     - Leave the key field empty (modifier-only action)
   - Click **"Apply"** to save the base action
4. You can now add combinations (see next section)

**Important:** A button becomes a modifier **automatically** when it has at least one modifier combination defined. There's no checkbox to enable/disable modifier mode - it's determined by whether combinations exist.

### Adding Modifier Combinations

**Example:** Add "Side + Top = Ctrl+C" combination

1. **Ensure the modifier button is selected** (e.g., "side")
2. In the **Modifier Combinations** section (bottom of Control Editor):
   - Click **"Add Combination"**
3. In the dialog that appears:
   - **Control:** Select "top" from the dropdown
   - **Action Type:** Select "Keyboard"
   - **Modifiers:** Check "Ctrl"
   - **Key:** Type "c"
   - **Comment:** (Optional) Type "Copy"
   - For dial controls you can select the **Strength** and **Speed** of the haptic feedback
   - Click **"OK"**
4. The combination appears in the Modifier Combinations table
5. Click **"Apply"** to apply changes
6. Click **"Save"** (Ctrl+S) to write to config file (You must save any changes to make them permanent and to test your mappings)

**Result:** Now when you hold the "side" button and press "top", it sends Ctrl+C!

### Editing and Deleting Combinations

**To edit a combination:**
1. Select the modifier button in Controls Configuration
2. In the Modifier Combinations table, click the combination row
3. Click the **"Edit"** button in the rightmost column
4. Make changes in the dialog
5. Click **"OK"**, then **"Apply"**, then **"Save"**

**To delete a combination:**
1. Select the modifier button in Controls Configuration
2. In the Modifier Combinations table, click the combination row
3. Click the **"Delete"** (trash icon) button in the rightmost column
4. Confirm deletion
5. Click **"Apply"**, then **"Save"**

### How Modifier Buttons Work

**Press behavior:**
- **Hold modifier + press another control** → Sends the combination action
- **Press and release modifier alone** → Sends the base action

**Visual feedback:**
- When a modifier button is selected, you'll see its **base action** in the "Current Action" column
- The **Modifier Combinations** section shows all defined combinations for that button
- When you click a combination in the table, both the modifier button **and** the combination control are highlighted in the controller view

### Common Modifier Patterns

**Text Editing (Side as modifier):**
- `side + tall` → Ctrl+C (copy)
- `side + short` → Ctrl+V (paste)
- `side + c1` → Ctrl+Z (undo)
- `side + c2` → Ctrl+Shift+Z (redo)
- `side + tour` → Ctrl+A (select all)
- `side` alone → Super (application menu)

**Navigation (Top as modifier):**
- `top + dpad_up` → Page Up
- `top + dpad_down` → Page Down
- `top + dpad_left` → Home
- `top + dpad_right` → End
- `top + scroll_up` → Ctrl+Home (document start)
- `top + scroll_down` → Ctrl+End (document end)
- `top` alone → Shift

**Application-Specific (Tall as modifier for GIMP/Photoshop):**
- `tall + knob_cw` → Increase brush size
- `tall + knob_ccw` → Decrease brush size
- `tall + c1` → Switch to brush tool
- `tall + c2` → Switch to eraser tool
- `tall + tour` → Reset tool options
- `tall` alone → Alt

### Tips for Using Modifiers

**1. Keep Base Actions Useful**
- Don't set the base action to "None" - you'll lose functionality when pressing the button alone
- Good base actions: Super, Shift, Alt, Ctrl (modifier keys)
- These are useful both alone and in combinations

**2. Organize by Function**
- Group related combinations under one modifier button
- Example: All text editing under "side", all navigation under "top"

**3. Start Simple**
- Begin with 3-4 combinations per modifier
- Add more as you memorize them
- Too many combinations can be overwhelming

**4. Use Comments**
- Add descriptive comments to combinations
- Helps you remember what each combination does
- Especially useful for complex shortcuts

**5. Profile-Specific Modifiers**
- Different profiles can have different modifier combinations
- Example: "side + c1" = Ctrl+Z in default, but "Undo Brush Stroke" in GIMP profile
- The same physical buttons can do completely different things per application

### Example: Complete Modifier Setup

Here's a complete example showing how to set up a modifier-heavy workflow:

**Side Button (Modifier):**
- Base action: Super
- Combinations:
  - side + top → Ctrl+C (copy)
  - side + tall → Ctrl+V (paste)
  - side + short → Ctrl+X (cut)
  - side + c1 → Ctrl+Z (undo)
  - side + c2 → Ctrl+Shift+Z (redo)
  - side + tour → Ctrl+A (select all)
  - side + dpad_up → Ctrl+Home
  - side + dpad_down → Ctrl+End
  - side + knob_cw → Ctrl+= (zoom in)
  - side + knob_ccw → Ctrl+- (zoom out)

**Top Button (Regular):**
- Action: Shift (no combinations)

**Result:** You've created 10 additional shortcuts from just the "side" button, while keeping "top" as a simple Shift key!

### Troubleshooting Modifiers

**Problem:** Combination doesn't trigger

**Solutions:**
1. Verify the combination exists in the Modifier Combinations table
2. Check that you're holding the modifier button while pressing the other control
3. Ensure you clicked "Apply" and "Save" after adding the combination
4. Check driver logs: `journalctl --user -u tourbox -f`
5. Restart the driver: `systemctl --user restart tourbox`

**Problem:** Base action doesn't work when pressed alone

**Solutions:**
1. Verify the base action is configured (check "Current Action" column)
2. Make sure you're **not** holding the modifier button too long
3. Release the modifier button cleanly without pressing other controls

**Problem:** Too many combinations to remember

**Solutions:**
1. Use the comment field to document what each combination does
2. Print a reference card with your most-used combinations
3. Start with fewer combinations and add more gradually
4. Group related functions under the same modifier

---

## Configuring Haptic Feedback

### What is Haptic Feedback?

The TourBox Elite and Elite Plus have built-in haptic motors that provide vibration feedback when you rotate the knob, scroll wheel, or dial. This tactile feedback helps you feel each "click" or detent as you rotate, making it easier to make precise adjustments without looking at the screen.

> **Note:** Haptic feedback is only available on the TourBox Elite and Elite Plus. The TourBox Neo does not have haptic motors.

### Haptic Settings Overview

Haptic feedback has two configurable parameters:

**Strength** - Controls the intensity of the vibration:
- **Off** - No vibration feedback
- **Weak** - Subtle vibration, good for quiet environments
- **Strong** - More pronounced vibration, easier to feel

**Speed** - Controls how spaced out the detents feel when rotating:
- **Fast (more detents)** - More clicks per rotation, finer control
- **Medium** - Balanced spacing
- **Slow (fewer detents)** - Fewer clicks per rotation, coarser control

### Setting Profile-Wide Haptic Feedback

Each profile can have its own haptic settings. This is useful if you want different feedback for different applications (e.g., strong feedback for photo editing, off for video calls).

**To set haptic feedback for a profile:**

1. **Select the profile** in the Profiles list
2. Click the **"⚙"** (settings) button to open Profile Settings
3. Find the **"Haptic Feedback"** section
4. Select your preferred **Strength** from the dropdown
5. Select your preferred **Speed** from the dropdown
6. Click **"Apply"**
7. Click **"Save"** (Ctrl+S) to write changes to config

When set at the profile level, the haptic settings apply to all three rotary controls (knob, scroll wheel, dial) in that profile as the default.

### Setting Per-Dial Haptic Feedback

For more granular control, you can set different haptic strength and speed for each individual dial. This is configured when editing a rotary control.

**To set haptic for a specific dial:**

1. **Select a rotary control** in the Controls Configuration table
   - Choose one of: `Scroll Up`, `Scroll Down`, `Knob Clockwise`, `Knob Counter-CW`, `Dial Clockwise`, or `Dial Counter-CW`
2. In the Control Editor, you'll see a **"Haptic Feedback"** section with two dropdowns side-by-side:
   - **Strength:** dropdown on the left
   - **Speed:** dropdown on the right
3. For each setting, select your preference:
   - **Use Profile Default** - Uses the profile's global setting
   - Or choose a specific value to override the profile default
4. Click **"Apply"**
5. Click **"Save"** (Ctrl+S)

**Example use cases:**
- **Scroll wheel for zooming:** Strong strength + Fast speed for precise zoom control
- **Dial for timeline scrubbing:** Off or Weak strength to avoid distraction during video editing
- **Knob for brush size:** Strong strength + Slow speed for deliberate size changes

### Haptic for Modifier Combinations

When you create a modifier combination that uses a rotary control (e.g., `Side + Knob Clockwise`), you can also set custom haptic strength and speed for that specific combination.

**To set haptic for a modifier+rotary combination:**

1. **Select the modifier button** (e.g., "side")
2. In the **Modifier Combinations** table, click **"Add Combination"** or edit an existing one
3. **Select a rotary control** as the target (e.g., `Knob Clockwise`)
4. The **"Haptic Feedback"** section appears in the dialog with:
   - **Strength:** dropdown
   - **Speed:** dropdown
5. Select your preferred settings for each
6. Click **"OK"**, then **"Apply"**, then **"Save"**

This allows you to have different haptic feedback depending on whether you're using the dial alone or with a modifier button held. For example:
- `Knob Clockwise` alone: Strong + Fast (for scrolling)
- `Side + Knob Clockwise`: Weak + Slow (for fine brush adjustments)

### Haptic Configuration Hierarchy

Haptic settings (both strength and speed) are applied in this priority order (highest to lowest):

1. **Per-combo setting** - Modifier + rotary combination (e.g., `Side + Knob Clockwise`)
2. **Per-dial setting** - Individual dial override (e.g., just `Knob`)
3. **Profile global setting** - Profile-wide haptic setting
4. **Default** - Off for strength, Fast for speed (if nothing is configured)

### Tips for Haptic Configuration

**1. Start with global settings**
- Set profile-wide strength and speed first
- Only add per-dial overrides if you need different behavior

**2. Consider your environment**
- Use "Weak" strength in quiet offices or during video calls
- Use "Strong" strength when you need precise tactile feedback

**3. Match haptic to function**
- **Coarse adjustments** (scrolling, zooming): Strong + Fast
- **Fine adjustments** (brush size, opacity): Weak + Slow or Medium
- **Timeline scrubbing**: Off or Weak to avoid distraction

**4. Speed affects precision feel**
- **Fast:** More detents = more precise, incremental control
- **Slow:** Fewer detents = faster sweeping movements

**5. Test with your applications**
- Save and test your haptic settings in your actual workflow
- Adjust based on what feels natural for each use case

---

## Tips & Tricks

### Keyboard Navigation

Speed up your workflow with keyboard shortcuts:

- **Ctrl+S** - Save changes and apply configuration
- **Arrow keys** - Navigate between controls in the list
- **Tab** - Move between UI elements

### Workflow Efficiency

**Quick iteration:**
1. Keep the GUI open during setup
2. Apply and Save changes
3. Switch to your application to test
4. Switch back to GUI → tweak → save → test again
5. No need to close the GUI or restart anything

**Bulk editing:**
1. Configure one profile completely
2. Create new profile based on it
3. Change only what's different
4. Saves time vs. configuring from scratch

### Common Mapping Patterns

**Undo/Redo:**
- `short` → Ctrl+Z (undo)
- `tall` → Ctrl+Shift+Z (redo)

**Zoom:**
- `knob_cw` → Ctrl+= (zoom in)
- `knob_ccw` → Ctrl+- (zoom out)

**Scrolling:**
- `dial_cw` → Wheel Up
- `dial_ccw` → Wheel Down

**Modifiers:**
- `side` → Super (start menu)
- `top` → Shift
- `tall` → Alt
- `short` → Ctrl

**Navigation:**
- `dpad_up/down` → Page Up/Page Down
- `dpad_left/right` → Home/End

### Visual Feedback

- **Yellow highlight** on controller view shows selected control that has no modifiers or the modifier itself
- **Turquoise highlight** on controller view shows the control that is the base control (that has modifiers defined for it)
- **Orange ⚠ icon** in profile name indicates conflicting window rules with another active profile
- **Asterisk (*)** in window title means unsaved changes
- **"(unmapped)"** in controls list means no action assigned
- **Status bar** shows what's happening

---

## Checking for Updates

To check if a new version of TourBox Linux is available:

1. Open the GUI: `tourbox-gui`
2. Click **Help → Check for Updates**
3. The GUI will check GitHub for the latest version
4. If an update is available, follow the instructions in the dialog

**What happens:**
- The GUI fetches version information from GitHub
- Compares it with your installed version
- Shows a dialog with the result

**If an update is available:**
- The dialog shows update instructions with the correct path to your installation
- Click "View on GitHub" to see the release notes
- Run the commands shown to update

**Note:** This requires an internet connection. The check only reads version information from GitHub and does not send any data.

---

## Troubleshooting

### GUI Won't Launch

**Problem:** Error when running `tourbox-gui`

**Solutions:**
1. Check that launcher script exists:
   ```bash
   ls -la /usr/local/bin/tourbox-gui
   ```
2. If missing, re-run installer or create manually:
   ```bash
   cd /path/to/tourboxelite
   ./install.sh
   ```
3. If launcher exists but still fails, check GUI dependencies:
   ```bash
   /path/to/tourboxelite/venv/bin/pip install -r tourboxelite/gui/requirements.txt
   ```
4. Verify Qt installation:
   ```bash
   /path/to/tourboxelite/venv/bin/python -c "from PySide6 import QtWidgets; print('OK')"
   ```

### Driver Won't Stop/Start

**Problem:** GUI shows error when stopping/starting driver

**Solutions:**
1. Check if driver is installed as systemd service:
   ```bash
   systemctl --user status tourbox
   ```
2. If not installed, see main README.md installation section
3. Try manual stop/start:
   ```bash
   systemctl --user stop tourbox
   systemctl --user start tourbox
   ```

### No Profiles Found

**Problem:** "No profiles found in configuration"

**Solutions:**
1. Check profiles directory exists:
   ```bash
   ls -la ~/.config/tourbox/profiles/
   ```
2. If missing, run `./install_config.sh` to create default config
3. Check file permissions (should be readable)
4. Verify at least `default.profile` exists in the profiles directory

### Changes Not Saving

**Problem:** Click Save but changes don't persist

**Solutions:**
1. Check for error dialogs (file permissions, disk space)
2. Verify profiles directory is writable:
   ```bash
   ls -la ~/.config/tourbox/profiles/
   ```
3. Check disk space:
   ```bash
   df -h ~
   ```
4. Look for backup files (confirms writes are working):
   ```bash
   ls -la ~/.config/tourbox/profiles/*.backup.*
   ```

### Button Presses Don't Work in When Testing

**Problem:** Physical button presses do nothing during Test

**Solutions:**
1. Check driver status:
   ```bash
   systemctl --user status tourbox
   ```
2. Check driver logs for errors:
   ```bash
   journalctl --user -u tourbox -n 50
   ```
3. Verify TourBox is powered on and in range
4. Try reconnecting Bluetooth:
   - Stop test
   - Turn TourBox off and on
   - Start test again
5. Check MAC address in config:
   ```bash
   grep mac_address ~/.config/tourbox/config.conf
   ```

### Profile Switching Not Working

**Problem:** Profile doesn't activate when switching windows

**Solutions:**
1. Check window matching rules are correct:
   - Use "Capture Active Window" feature
   - Verify app_id or window_class matches
2. Check which compositor you're using:
   ```bash
   echo $XDG_SESSION_TYPE  # Should be "wayland"
   echo $XDG_CURRENT_DESKTOP  # Shows your desktop
   ```
3. For GNOME: Install the Focused Window D-Bus extension
4. For KDE: Install `kdotool`
5. Check driver logs to see profile switching:
   ```bash
   journalctl --user -u tourbox -f
   ```
   Should show: "Switched to profile: [name]"

### Window Capture Not Working

**Problem:** "Capture Active Window" doesn't detect window

**Solutions:**
1. Make sure you're on **Wayland** (not X11):
   ```bash
   echo $XDG_SESSION_TYPE
   ```
2. Install compositor-specific tools:
   - **GNOME:** Focused Window D-Bus Extension
   - **KDE:** kdotool package
   - **Sway/Hyprland:** Built-in IPC (should work)
3. Click the target window during the 5-second countdown
4. If detection fails, manually enter window class/app_id

### GUI Freezes or Crashes

**Problem:** GUI becomes unresponsive

**Solutions:**
1. Check system resources (RAM, CPU):
   ```bash
   top
   ```
2. Kill and restart GUI:
   ```bash
   pkill -f "tourboxelite.gui"
   tourbox-gui
   ```
3. Check for Qt/Python errors in terminal output
4. Restart driver if it was left in stopped state:
   ```bash
   systemctl --user start tourbox
   ```

### Config File Corrupted

**Problem:** Can't load config, syntax errors

**Solutions:**
1. Restore a specific profile from automatic backup:
   ```bash
   cd ~/.config/tourbox/profiles/
   ls -la *.backup.*
   cp default.profile.backup.YYYYMMDD_HHMMSS default.profile
   ```
2. Or reset to defaults (removes all profiles):
   ```bash
   rm -rf ~/.config/tourbox/profiles ~/.config/tourbox/config.conf
   ./install_config.sh
   ```
   ⚠️ WARNING: Loses all customizations!

### Getting Help

If you encounter issues not covered here:

1. **Check logs:**
   ```bash
   journalctl --user -u tourbox -n 100
   ```

2. **Enable verbose logging in GUI:**
   Edit `tourboxelite/gui/main_window.py` and change:
   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Report issues:**
   - GitHub: https://github.com/AndyCappDev/tourbox-linux/issues
   - Include: OS, desktop environment, error messages, logs

---

## Appendix: Configuration File Format

The GUI reads and writes profiles to individual files in `~/.config/tourbox/profiles/`.

**File Structure:**
```
~/.config/tourbox/
├── config.conf              # Device settings (MAC address, USB port)
└── profiles/
    ├── default.profile      # Default profile
    ├── vscode.profile       # Application-specific profile
    └── ...
```

**Example Profile (`default.profile`):**
```ini
[profile]
name = default

[mappings]
side = KEY_LEFTMETA
top = KEY_LEFTSHIFT
tall = KEY_LEFTALT
short = KEY_LEFTCTRL
scroll_up = REL_WHEEL:1
scroll_down = REL_WHEEL:-1
knob_cw = KEY_LEFTCTRL+KEY_EQUAL
knob_ccw = KEY_LEFTCTRL+KEY_MINUS
# ... etc

[profile:firefox]
app_id = firefox-esr
window_class = firefox-esr
side = KEY_LEFTCTRL+KEY_T
tall = KEY_LEFTCTRL+KEY_W
# ... etc
```

**Profile sections:**
- `[profile:name]` - Section header
- `window_class`, `app_id` - Optional matching rules
- Control mappings - One line per control

**Action formats:**
- Keyboard: `KEY_LEFTCTRL+KEY_C` (modifiers+key)
- Mouse wheel: `REL_WHEEL:1` (wheel:direction)
- Unmapped: Omit the line or set to empty

The GUI preserves comments and formatting when saving!

---

## Quick Reference Card

### Keyboard Shortcuts
- **Ctrl+S** - Save changes and apply configuration
- **Arrow keys** - Navigate controls

### Workflow
1. Select profile
2. Click control
3. Configure action
4. Apply
5. Save (Ctrl+S) - applies automatically
6. Switch to app and test

### Action Types
- **Keyboard** - Key combos (Ctrl+C, Alt+F4, etc.)
- **Mouse Wheel** - Scroll up/down/left/right
- **None** - Disable control

### Profile Management
- **"+"** - Create new profile
- **"⚙"** - Edit profile settings
- **"-"** - Delete profile
- **Active checkbox** - Enable/disable profile for window matching
- **Import** - Import a profile from file
- **Export** - Export selected profile to file
- **Capture** (in settings) - Auto-detect window info
- **Orange ⚠** - Profile conflicts with another active profile

### Importing and Exporting Profiles

**Exporting a Profile:**
1. Select the profile you want to export
2. Click **Export** button or use **File > Export Profile...**
3. Choose a location and filename
4. Share the `.profile` file with others

**Importing a Profile:**
1. Click **Import** button or use **File > Import Profile...**
2. Select a `.profile` file
3. If a profile with the same name exists, you can:
   - **Replace** the existing profile
   - **Rename** the imported profile
4. The imported profile appears in your list

### Testing
1. Click "Save"
2. Switch to your app
3. Try physical buttons
4. Switch back to GUI to adjust
5. Repeat as needed

---

**Enjoy your TourBox with the power of a visual configuration tool!** 🎨✨

For technical details, see:
- [CONFIG_GUIDE.md](CONFIG_GUIDE.md) - Manual config editing
- [DEVELOPMENT.md](DEVELOPMENT.md) - Architecture and code
