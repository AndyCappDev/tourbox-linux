#!/usr/bin/env python3
"""TourBox Elite BLE Driver - Linux Input Device
Integrates reverse-engineered BLE protocol with evdev virtual input device
"""

import sys
import os
import asyncio
import logging
import signal
import pathlib
from typing import Optional

from bleak import BleakClient
from evdev import UInput, ecodes as e
from .config_loader import load_config, load_device_config, load_profiles, BUTTON_CODES, parse_action
from .window_monitor import WaylandWindowMonitor

logger = logging.getLogger(__name__)

# BLE Configuration
VENDOR_SERVICE = "0000fff0-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR = "0000fff1-0000-1000-8000-00805f9b34fb"  # Button data notifications
WRITE_CHAR = "0000fff2-0000-1000-8000-00805f9b34fb"   # Commands to device

# Unlock sequence discovered from Windows BLE capture
UNLOCK_COMMAND = bytes.fromhex("5500078894001afe")

# Configuration commands to enable button reporting
CONFIG_COMMANDS = [
    bytes.fromhex("b5005d0400050006000700080009000b000c000d"),
    bytes.fromhex("000e000f0026002700280029003b003c003d003e"),
    bytes.fromhex("003f004000410042004300440045004600470048"),
    bytes.fromhex("0049004a004b004c004d004e004f005000510052"),
    bytes.fromhex("0053005400a800a900aa00ab00fe"),
]


class GracefulKiller:
    """Handle SIGINT, SIGTERM, and SIGHUP gracefully"""
    kill_now = False
    reload_config = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        signal.signal(signal.SIGHUP, self.reload_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True

    def reload_gracefully(self, *args):
        self.reload_config = True
        logger.info("Received SIGHUP - will reload config")


class TourBoxBLE:
    """TourBox Elite BLE Driver"""

    def __init__(self, mac_address: str, pidfile: Optional[str] = None, config_path: Optional[str] = None):
        self.mac_address = mac_address
        # Default to user runtime dir, fallback to /tmp for user access
        default_pidfile = os.path.join(os.getenv('XDG_RUNTIME_DIR', '/tmp'), 'tourbox.pid')
        self.pidfile = pidfile or os.getenv('pidfile') or default_pidfile
        self.config_path = config_path
        self.controller: Optional[UInput] = None
        self.killer = GracefulKiller()
        self.client: Optional[BleakClient] = None
        self.button_count = 0
        self.mapping = None
        self.capabilities = None
        self.profiles = []
        self.current_profile = None
        self.window_monitor = None
        self.use_profiles = False
        self.disconnected = False
        self.reconnect_delay = 5.0  # Initial reconnection delay in seconds

        # Modifier state tracking
        self.modifier_buttons = set()              # Set of button names that are modifiers
        self.active_modifiers = set()              # Currently pressed modifier buttons
        self.modifier_mappings = {}                # (modifier, control) -> action events
        self.modifier_base_actions = {}            # modifier -> base action events
        self.base_action_active = set()            # Modifiers with base action currently pressed
        self.combo_used = set()                    # Modifiers that had a combo used while held

    def disconnection_handler(self, client):
        """Handle disconnection from TourBox Elite"""
        self.disconnected = True
        # Clear modifier state on disconnect to prevent stuck modifiers
        self.active_modifiers.clear()
        self.base_action_active.clear()
        self.combo_used.clear()
        logger.warning("TourBox Elite disconnected")
        print("\n⚠️  TourBox Elite disconnected - waiting for reconnection...")

    def is_modifier_button(self, control_name: str) -> bool:
        """Check if a control is configured as a modifier button

        Args:
            control_name: Name of the control (e.g., 'tall', 'short')

        Returns:
            True if the control is a modifier button, False otherwise
        """
        return control_name in self.modifier_buttons

    def get_control_name_from_code(self, data_bytes: bytes) -> Optional[tuple]:
        """Get control name and press/release state from button code

        Args:
            data_bytes: Raw button data from device

        Returns:
            Tuple of (control_name, is_press) or None if not found
        """
        for control_name, codes in BUTTON_CODES.items():
            if len(codes) >= 2:
                press_code, release_code = codes[0], codes[1]
                if data_bytes == bytes([press_code]):
                    return (control_name, True)
                elif data_bytes == bytes([release_code]):
                    return (control_name, False)
        return None

    def get_modified_action(self, control_name: str) -> Optional[list]:
        """Get modified action if a modifier is currently active

        Args:
            control_name: Name of the control being actuated

        Returns:
            List of action events if a modifier combo exists, None otherwise
        """
        # Check if any modifier is active
        if not self.active_modifiers:
            return None

        # For now, we only support single modifiers (not multiple simultaneous)
        # Take the first (and only) active modifier
        if len(self.active_modifiers) == 1:
            modifier_name = next(iter(self.active_modifiers))

            # Check if there's a combo mapping for this modifier + control
            combo_key = (modifier_name, control_name)
            if combo_key in self.modifier_mappings:
                return self.modifier_mappings[combo_key]

        return None

    def notification_handler(self, sender, data: bytearray):
        """Handle button/dial notifications from TourBox Elite

        Each notification is a single byte containing button press/release
        or dial rotation data. Maps to Linux input events via MAPPING dict.

        Implements modifier button logic:
        - Tracks modifier button state (pressed/released)
        - Executes modifier base actions if configured
        - Routes to combo actions when modifier is held
        """
        self.button_count += 1

        # Convert bytearray to bytes for dict lookup
        data_bytes = bytes(data)

        # Step 1: Identify control name and press/release state
        control_info = self.get_control_name_from_code(data_bytes)

        # Step 2: Check if this is a modifier button event
        if control_info:
            control_name, is_press = control_info

            if self.is_modifier_button(control_name):
                # This is a modifier button - update state
                if is_press:
                    self.active_modifiers.add(control_name)
                    logger.info(f"🔘 Modifier {control_name} PRESSED, active: {self.active_modifiers}")

                    # Execute base action press if configured
                    if control_name in self.modifier_base_actions:
                        events = self.modifier_base_actions[control_name]
                        # Send press events only
                        for event_type, event_code, value in events:
                            if value == 1:  # Press events
                                self.controller.write(event_type, event_code, value)
                        self.controller.syn()
                        self.base_action_active.add(control_name)
                        logger.info(f"🔘 Modifier {control_name} base action PRESSED")
                    else:
                        logger.info(f"🔘 Modifier {control_name} - no base action, tracking state only")
                else:
                    # Modifier released
                    self.active_modifiers.discard(control_name)
                    logger.info(f"🔘 Modifier {control_name} RELEASED, active: {self.active_modifiers}")

                    # Release base action if it's still active (wasn't cancelled by combo)
                    if control_name in self.base_action_active:
                        events = self.modifier_base_actions[control_name]
                        # Send release events
                        for event_type, event_code, value in events:
                            if value == 1:  # Was a press event, send release
                                self.controller.write(event_type, event_code, 0)
                        self.controller.syn()
                        self.base_action_active.discard(control_name)
                        logger.info(f"🔘 Modifier {control_name} base action RELEASED")

                    # Reset combo usage tracking
                    self.combo_used.discard(control_name)
                return

        # Step 3: Check for modified action (combo)
        if control_info:
            control_name, is_press = control_info
            modified_action = self.get_modified_action(control_name)

            if modified_action:
                # Execute combo action instead of normal action
                modifier_name = next(iter(self.active_modifiers))

                if is_press:
                    # Combo button pressed - cancel base action if active
                    if modifier_name in self.base_action_active:
                        # Release the base action first
                        base_events = self.modifier_base_actions[modifier_name]
                        for event_type, event_code, value in base_events:
                            if value == 1:  # Was a press, send release
                                self.controller.write(event_type, event_code, 0)
                        self.controller.syn()
                        self.base_action_active.discard(modifier_name)
                        logger.info(f"🔘 Cancelled base action for {modifier_name} (combo triggered)")

                    # Mark that combo was used
                    self.combo_used.add(modifier_name)

                    # Send combo press
                    events_to_send = modified_action
                else:
                    # Combo button released - send combo release
                    events_to_send = []
                    for event_type, event_code, value in modified_action:
                        if event_type == e.EV_KEY and value == 1:
                            # Convert press to release
                            events_to_send.append((event_type, event_code, 0))
                        else:
                            # Keep other events as-is
                            events_to_send.append((event_type, event_code, value))

                # Log the actual events being sent
                event_desc = []
                for event_type, event_code, value in events_to_send:
                    if event_type == e.EV_KEY:
                        key_name = next((k for k, v in e.__dict__.items() if k.startswith('KEY_') and v == event_code), f"KEY_{event_code}")
                        action = "PRESS" if value == 1 else "RELEASE" if value == 0 else f"VAL={value}"
                        event_desc.append(f"{key_name}:{action}")
                logger.info(f"🔘 Combo: {modifier_name}.{control_name} -> {', '.join(event_desc)}")

                for event in events_to_send:
                    self.controller.write(*event)
                self.controller.syn()
                return

        # Step 4: Execute normal action (no modifier or no combo mapping)
        if data_bytes:
            mapping = self.mapping.get(data_bytes, [])
            if mapping:
                # Log the actual events being sent
                event_desc = []
                for event_type, event_code, value in mapping:
                    if event_type == e.EV_KEY:
                        key_name = next((k for k, v in e.__dict__.items() if k.startswith('KEY_') and v == event_code), f"KEY_{event_code}")
                        action = "PRESS" if value == 1 else "RELEASE" if value == 0 else f"VAL={value}"
                        event_desc.append(f"{key_name}:{action}")
                    elif event_type == e.EV_REL:
                        rel_name = next((k for k, v in e.__dict__.items() if k.startswith('REL_') and v == event_code), f"REL_{event_code}")
                        event_desc.append(f"{rel_name}:{value}")
                logger.info(f"🔘 {data_bytes.hex()} -> {', '.join(event_desc)}")

                # Send input events to virtual device
                for event in mapping:
                    self.controller.write(*event)
                self.controller.syn()
            else:
                logger.warning(f"Unknown button code: {data_bytes.hex()}")

    async def unlock_device(self):
        """Send unlock sequence to TourBox Elite

        This is required before the device will report button presses.
        Sequence discovered via Windows BLE traffic capture.
        """
        logger.info("Sending unlock command...")

        # Send unlock command
        await self.client.write_gatt_char(WRITE_CHAR, UNLOCK_COMMAND, response=False)
        await asyncio.sleep(0.1)

        logger.info("Sending configuration commands...")

        # Send configuration commands
        for i, cmd in enumerate(CONFIG_COMMANDS, 1):
            await self.client.write_gatt_char(WRITE_CHAR, cmd, response=False)
            await asyncio.sleep(0.01)

        logger.info("Device unlocked and configured")

    def switch_profile(self, profile):
        """Switch to a different profile

        Updates the active mapping and recreates the virtual input device
        with the new capabilities if needed.
        """
        if profile == self.current_profile:
            return

        self.current_profile = profile
        self.mapping = profile.mapping

        # Load modifier configuration
        self.modifier_buttons = profile.modifier_buttons
        self.active_modifiers.clear()  # Clear modifier state when switching
        self.base_action_active.clear()  # Clear base action state
        self.combo_used.clear()  # Clear combo usage tracking

        # Convert modifier mappings from action strings to events
        self.modifier_mappings = {}
        logger.info(f"Converting {len(profile.modifier_mappings)} modifier mappings from strings to events")
        for (modifier, control), action_str in profile.modifier_mappings.items():
            events = parse_action(action_str)
            logger.info(f"  Parsing combo {modifier}.{control} = '{action_str}' -> {events}")
            # For rotary controls, add press+release cycle
            if control in ('scroll_up', 'scroll_down', 'knob_cw', 'knob_ccw', 'dial_cw', 'dial_ccw'):
                # Create release events
                release_events = []
                for event_type, event_code, value in events:
                    if event_type == e.EV_KEY:
                        release_events.append((event_type, event_code, 0))
                self.modifier_mappings[(modifier, control)] = events + release_events
            else:
                self.modifier_mappings[(modifier, control)] = events
            # Log the final stored events with key names
            for event_type, event_code, value in self.modifier_mappings[(modifier, control)]:
                if event_type == e.EV_KEY:
                    key_name = next((k for k, v in e.__dict__.items() if k.startswith('KEY_') and v == event_code), f"KEY_{event_code}")
                    logger.info(f"  Event: {key_name} (code={event_code}) value={value}")

        # Convert base actions from action strings to events
        self.modifier_base_actions = {}
        for modifier, action_str in profile.modifier_base_actions.items():
            self.modifier_base_actions[modifier] = parse_action(action_str)

        # Print profile switch to console
        print(f"\n🎮 Switched to profile: {profile.name}")
        logger.info(f"Switched to profile: {profile.name}")
        if self.modifier_buttons:
            logger.info(f"  Modifiers active: {', '.join(self.modifier_buttons)}")

        # Check if capabilities changed
        if profile.capabilities != self.capabilities:
            logger.info("Profile has different capabilities - recreating virtual input device")
            self.capabilities = profile.capabilities

            # Close old controller if exists
            if self.controller:
                self.controller.close()

            # Create new controller with updated capabilities
            self.controller = UInput(
                self.capabilities,
                name='TourBox Elite',
                vendor=0xC251,
                product=0x2005
            )
            logger.debug(f"Virtual input device recreated: {self.controller.device.path}")

    def reload_config_mappings(self):
        """Reload configuration from file and update mappings

        Called when SIGHUP is received. Reloads the config file and updates
        the current profile's mappings without restarting the driver.
        """
        print("\n🔄 Reloading configuration...")
        logger.info("Reloading configuration from file")

        try:
            # Remember current profile name
            current_profile_name = self.current_profile.name if self.current_profile else 'default'

            # Reload profiles from config
            new_profiles = load_profiles(self.config_path)

            if not new_profiles:
                logger.error("Failed to reload config - no profiles found")
                print("❌ Failed to reload: No profiles found in config")
                return

            self.profiles = new_profiles
            logger.info(f"Reloaded {len(self.profiles)} profiles")

            # Find the current profile in the new profiles
            new_current_profile = next((p for p in self.profiles if p.name == current_profile_name), None)

            if not new_current_profile:
                # Current profile no longer exists, fall back to default or first profile
                logger.warning(f"Profile '{current_profile_name}' not found after reload")
                new_current_profile = next((p for p in self.profiles if p.name == 'default'), self.profiles[0])
                print(f"⚠️  Profile '{current_profile_name}' not found, using '{new_current_profile.name}'")

            # Update current profile and mapping
            self.current_profile = new_current_profile
            self.mapping = new_current_profile.mapping

            # Reload modifier configuration
            self.modifier_buttons = new_current_profile.modifier_buttons
            self.active_modifiers.clear()  # Clear modifier state on reload

            # Convert modifier mappings from action strings to events
            self.modifier_mappings = {}
            for (modifier, control), action_str in new_current_profile.modifier_mappings.items():
                events = parse_action(action_str)
                # For rotary controls, add press+release cycle
                if control in ('scroll_up', 'scroll_down', 'knob_cw', 'knob_ccw', 'dial_cw', 'dial_ccw'):
                    release_events = []
                    for event_type, event_code, value in events:
                        if event_type == e.EV_KEY:
                            release_events.append((event_type, event_code, 0))
                    self.modifier_mappings[(modifier, control)] = events + release_events
                else:
                    self.modifier_mappings[(modifier, control)] = events

            # Convert base actions from action strings to events
            self.modifier_base_actions = {}
            for modifier, action_str in new_current_profile.modifier_base_actions.items():
                self.modifier_base_actions[modifier] = parse_action(action_str)

            # Check if capabilities changed
            if new_current_profile.capabilities != self.capabilities:
                logger.info("Capabilities changed - recreating virtual input device")
                self.capabilities = new_current_profile.capabilities

                # Close old controller
                if self.controller:
                    self.controller.close()

                # Create new controller with updated capabilities
                self.controller = UInput(
                    self.capabilities,
                    name='TourBox Elite',
                    vendor=0xC251,
                    product=0x2005
                )
                logger.debug(f"Virtual input device recreated: {self.controller.device.path}")

            print(f"✅ Configuration reloaded successfully - using profile: {self.current_profile.name}")
            if self.modifier_buttons:
                print(f"   Modifiers active: {', '.join(self.modifier_buttons)}")
            logger.info(f"Configuration reload complete - active profile: {self.current_profile.name}")

        except Exception as e:
            logger.error(f"Error reloading config: {e}", exc_info=True)
            print(f"❌ Error reloading config: {e}")

    async def on_window_change(self, window_info):
        """Handle window focus changes

        Args:
            window_info: WindowInfo object with current window details
        """
        # Find matching profile
        for profile in self.profiles:
            if profile.matches(window_info):
                if profile != self.current_profile:
                    self.switch_profile(profile)
                return

        # No match - switch to default profile
        default_profile = next((p for p in self.profiles if p.name == 'default'), None)
        if default_profile and default_profile != self.current_profile:
            self.switch_profile(default_profile)

    async def run_connection(self, monitor_task):
        """Run a single connection session with the TourBox Elite

        Args:
            monitor_task: The window monitor task (if using profiles)

        Returns:
            True if should retry connection, False if user requested exit
        """
        try:
            logger.info(f"Connecting to TourBox Elite at {self.mac_address}...")
            self.disconnected = False

            async with BleakClient(
                self.mac_address,
                timeout=5.0,
                disconnected_callback=self.disconnection_handler
            ) as client:
                self.client = client
                logger.info(f"Connected to TourBox Elite")

                # Enable notifications
                logger.info("Enabling button notifications...")
                await client.start_notify(NOTIFY_CHAR, self.notification_handler)

                # Unlock device and send configuration
                await self.unlock_device()

                logger.info("TourBox Elite ready! Press buttons to generate input events.")
                print("✅ TourBox Elite connected and ready!")
                print(f"Virtual input device: {self.controller.device.path}")

                if self.use_profiles:
                    print(f"Profile switching enabled - Current profile: {self.current_profile.name}")

                print("Press Ctrl+C to exit")

                # Reset reconnect delay on successful connection
                self.reconnect_delay = 5.0

                # Keep running until disconnected or killed
                while not self.killer.kill_now and not self.disconnected:
                    # Check if config reload was requested
                    if self.killer.reload_config:
                        self.reload_config_mappings()
                        self.killer.reload_config = False

                    await asyncio.sleep(0.5)

                # Check if user requested exit
                if self.killer.kill_now:
                    logger.info("Shutting down...")
                    await client.stop_notify(NOTIFY_CHAR)
                    return False  # Don't reconnect

                # Device disconnected, will reconnect
                return True

        except asyncio.TimeoutError:
            logger.error("Connection timeout - device not found")
            print(f"❌ Connection timeout - is the TourBox Elite turned on?")
            return True  # Retry
        except Exception as e:
            logger.error(f"Connection error: {e}")
            print(f"❌ Connection error: {e}")
            return True  # Retry

    async def start(self):
        """Start the TourBox BLE driver with automatic reconnection"""

        # Load profiles from config
        self.profiles = load_profiles(self.config_path)

        if not self.profiles:
            logger.error("No profiles found in config file")
            print("❌ Error: Config file must contain at least one [profile:default] section")
            print("")
            print("Your config file should use the profile format:")
            print("")
            print("[device]")
            print("mac_address = XX:XX:XX:XX:XX:XX")
            print("")
            print("[profile:default]")
            print("side = KEY_LEFTMETA")
            print("top = KEY_LEFTSHIFT")
            print("# ... (all buttons and rotary controls)")
            print("")
            print("See the default config for a complete example:")
            print("  cat tourboxelite/default_mappings.conf")
            print("")
            print("Or see the config guide:")
            print("  https://github.com/your-repo/docs/CONFIG_GUIDE.md")
            sys.exit(1)

        self.use_profiles = True
        logger.info(f"Loaded {len(self.profiles)} profiles")

        # Find default profile
        default_profile = next((p for p in self.profiles if p.name == 'default'), None)
        if default_profile:
            self.current_profile = default_profile
            self.mapping = default_profile.mapping
            self.capabilities = default_profile.capabilities
            logger.info(f"Using default profile: {default_profile}")
        else:
            # Use first profile as default
            self.current_profile = self.profiles[0]
            self.mapping = self.profiles[0].mapping
            self.capabilities = self.profiles[0].capabilities
            logger.warning(f"No 'default' profile found, using '{self.profiles[0].name}' as fallback")

        # Initialize window monitor
        self.window_monitor = WaylandWindowMonitor()

        # Write PID file
        pid = str(os.getpid())
        p = pathlib.Path(self.pidfile)
        p.write_text(pid)

        # Create virtual input device (persists across reconnections)
        logger.info("Creating virtual input device...")
        self.controller = UInput(
            self.capabilities,
            name='TourBox Elite',
            vendor=0xC251,
            product=0x2005
        )
        logger.info("Virtual input device created")

        # Start window monitoring if using profiles
        monitor_task = None
        if self.use_profiles and self.window_monitor and self.window_monitor.compositor:
            logger.info("Starting window monitor for profile switching")
            monitor_task = asyncio.create_task(
                self.window_monitor.monitor_window_changes(self.on_window_change, interval=0.2)
            )

        # Connection loop with automatic reconnection
        try:
            while not self.killer.kill_now:
                # Check if config reload was requested
                if self.killer.reload_config:
                    self.reload_config_mappings()
                    self.killer.reload_config = False

                should_retry = await self.run_connection(monitor_task)

                if not should_retry:
                    break

                # Wait before reconnecting with exponential backoff
                if not self.killer.kill_now:
                    delay = min(self.reconnect_delay, 10.0)  # Cap at 10 seconds
                    logger.info(f"Attempting to reconnect in {delay} seconds...")
                    print(f"🔄 Reconnecting in {delay} seconds...")
                    await asyncio.sleep(delay)
                    self.reconnect_delay = min(self.reconnect_delay * 1.5, 10.0)
        except KeyboardInterrupt:
            pass
        finally:
            # Cancel monitor task if running
            if monitor_task:
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass

            # Cleanup
            if self.controller:
                self.controller.close()

            logger.info("TourBox Elite driver stopped")


def main():
    """Main entry point for BLE driver"""
    import argparse

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='TourBox Elite BLE Driver')
    parser.add_argument('mac_address', nargs='?', help='Bluetooth MAC address (XX:XX:XX:XX:XX:XX) - overrides config file')
    parser.add_argument('-c', '--config', help='Path to custom config file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    # Enable debug logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get MAC address from: 1) command line, 2) environment, 3) config file
    mac_address = args.mac_address or os.getenv('TOURBOX_MAC')

    if not mac_address:
        # Try to load from config file
        device_config = load_device_config(args.config)
        mac_address = device_config.get('mac_address')

        if mac_address:
            logger.info(f"Using MAC address from config: {mac_address}")
        else:
            print("Error: MAC address not found")
            print("")
            print("Provide MAC address via:")
            print("  1. Command line:  python -m tourboxelite.device_ble <MAC_ADDRESS>")
            print("  2. Environment:   TOURBOX_MAC=<MAC_ADDRESS> python -m tourboxelite.device_ble")
            print("  3. Config file:   Add 'mac_address = XX:XX:XX:XX:XX:XX' to [device] section")
            print("")
            print("Example: python -m tourboxelite.device_ble D9:BE:1E:CC:40:D7")
            print("")
            print("To set up config file:")
            print("  ./install_config.sh")
            print("  nano ~/.config/tourbox/mappings.conf")
            print("")
            print("Options:")
            print("  -c, --config PATH    Use custom config file")
            print("  -v, --verbose        Enable verbose logging")
            sys.exit(1)

    # Validate MAC address format
    if ':' not in mac_address:
        print(f"Error: Invalid MAC address format: {mac_address}")
        print("Expected format: XX:XX:XX:XX:XX:XX")
        sys.exit(1)

    # Create and start driver
    driver = TourBoxBLE(mac_address, config_path=args.config)

    try:
        asyncio.run(driver.start())
    except KeyboardInterrupt:
        print("\nExited by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
