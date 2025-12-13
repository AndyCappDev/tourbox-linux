#!/usr/bin/env python3
"""TourBox Elite Base Driver - Abstract base class for transport implementations

This module contains the shared logic for both BLE and USB transport implementations.
It handles button code processing, modifier state machine, profile management,
and virtual input device (uinput) creation.
"""

import os
import signal
import logging
import pathlib
from abc import ABC, abstractmethod
from typing import Optional, Dict, Set, List, Tuple

from evdev import UInput, ecodes as e
from .config_loader import load_profiles, BUTTON_CODES, parse_action
from .window_monitor import WaylandWindowMonitor

logger = logging.getLogger(__name__)


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


class TourBoxBase(ABC):
    """Abstract base class for TourBox Elite transport implementations

    This class contains all transport-agnostic logic including:
    - Button code to control name mapping
    - Modifier button state machine
    - Profile switching and management
    - Virtual input device (uinput) creation and event sending
    - Configuration hot-reload via SIGHUP

    Subclasses must implement:
    - connect(): Establish connection to device
    - disconnect(): Close connection
    - run_connection(): Main connection loop
    """

    def __init__(self, pidfile: Optional[str] = None, config_path: Optional[str] = None):
        """Initialize the TourBox driver base

        Args:
            pidfile: Path to PID file (default: $XDG_RUNTIME_DIR/tourbox.pid)
            config_path: Path to configuration file (default: auto-detect)
        """
        # Default to user runtime dir, fallback to /tmp for user access
        default_pidfile = os.path.join(os.getenv('XDG_RUNTIME_DIR', '/tmp'), 'tourbox.pid')
        self.pidfile = pidfile or os.getenv('pidfile') or default_pidfile
        self.config_path = config_path
        self.controller: Optional[UInput] = None
        self.killer = GracefulKiller()
        self.button_count = 0
        self.mapping: Optional[Dict] = None
        self.capabilities: Optional[Dict] = None
        self.profiles: List = []
        self.current_profile = None
        self.window_monitor: Optional[WaylandWindowMonitor] = None
        self.use_profiles = False

        # Modifier state tracking
        self.modifier_buttons: Set[str] = set()        # Set of button names that are modifiers
        self.active_modifiers: Set[str] = set()        # Currently pressed modifier buttons
        self.modifier_mappings: Dict[Tuple[str, str], List] = {}  # (modifier, control) -> action events
        self.modifier_base_actions: Dict[str, List] = {}  # modifier -> base action events
        self.base_action_active: Set[str] = set()      # Modifiers with base action currently pressed
        self.combo_used: Set[str] = set()              # Modifiers that had a combo used while held

    def is_modifier_button(self, control_name: str) -> bool:
        """Check if a control is configured as a modifier button

        Args:
            control_name: Name of the control (e.g., 'tall', 'short')

        Returns:
            True if the control is a modifier button, False otherwise
        """
        return control_name in self.modifier_buttons

    def get_control_name_from_code(self, data_bytes: bytes) -> Optional[Tuple[str, bool]]:
        """Get control name and press/release state from button code

        Args:
            data_bytes: Raw button data from device (single byte)

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

    def get_modified_action(self, control_name: str) -> Optional[List]:
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

    def process_button_code(self, data: bytearray):
        """Process button/dial data from TourBox Elite

        Each notification is a single byte containing button press/release
        or dial rotation data. Maps to Linux input events via MAPPING dict.

        Implements modifier button logic:
        - Tracks modifier button state (pressed/released)
        - Executes modifier base actions if configured
        - Routes to combo actions when modifier is held

        Args:
            data: Raw button data (single byte as bytearray)
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
                    logger.info(f"Modifier {control_name} PRESSED, active: {self.active_modifiers}")

                    # Execute base action press if configured
                    if control_name in self.modifier_base_actions:
                        events = self.modifier_base_actions[control_name]
                        # Send press events only
                        for event_type, event_code, value in events:
                            if value == 1:  # Press events
                                self.controller.write(event_type, event_code, value)
                        self.controller.syn()
                        self.base_action_active.add(control_name)
                        logger.info(f"Modifier {control_name} base action PRESSED")
                    else:
                        logger.info(f"Modifier {control_name} - no base action, tracking state only")
                else:
                    # Modifier released
                    self.active_modifiers.discard(control_name)
                    logger.info(f"Modifier {control_name} RELEASED, active: {self.active_modifiers}")

                    # Release base action if it's still active (wasn't cancelled by combo)
                    if control_name in self.base_action_active:
                        events = self.modifier_base_actions[control_name]
                        # Send release events
                        for event_type, event_code, value in events:
                            if value == 1:  # Was a press event, send release
                                self.controller.write(event_type, event_code, 0)
                        self.controller.syn()
                        self.base_action_active.discard(control_name)
                        logger.info(f"Modifier {control_name} base action RELEASED")

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
                        logger.info(f"Cancelled base action for {modifier_name} (combo triggered)")

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
                logger.info(f"Combo: {modifier_name}.{control_name} -> {', '.join(event_desc)}")

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
                logger.info(f"{data_bytes.hex()} -> {', '.join(event_desc)}")

                # Send input events to virtual device
                for event in mapping:
                    self.controller.write(*event)
                self.controller.syn()
            else:
                logger.warning(f"Unknown button code: {data_bytes.hex()}")

    def switch_profile(self, profile):
        """Switch to a different profile

        Updates the active mapping and recreates the virtual input device
        with the new capabilities if needed.

        Args:
            profile: Profile object to switch to
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
        print(f"\nSwitched to profile: {profile.name}")
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
        print("\nReloading configuration...")
        logger.info("Reloading configuration from file")

        try:
            # Remember current profile name
            current_profile_name = self.current_profile.name if self.current_profile else 'default'

            # Reload profiles from config
            new_profiles = load_profiles(self.config_path)

            if not new_profiles:
                logger.error("Failed to reload config - no profiles found")
                print("Failed to reload: No profiles found in config")
                return

            self.profiles = new_profiles
            logger.info(f"Reloaded {len(self.profiles)} profiles")

            # Find the current profile in the new profiles
            new_current_profile = next((p for p in self.profiles if p.name == current_profile_name), None)

            if not new_current_profile:
                # Current profile no longer exists, fall back to default or first profile
                logger.warning(f"Profile '{current_profile_name}' not found after reload")
                new_current_profile = next((p for p in self.profiles if p.name == 'default'), self.profiles[0])
                print(f"Profile '{current_profile_name}' not found, using '{new_current_profile.name}'")

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

            print(f"Configuration reloaded successfully - using profile: {self.current_profile.name}")
            if self.modifier_buttons:
                print(f"   Modifiers active: {', '.join(self.modifier_buttons)}")
            logger.info(f"Configuration reload complete - active profile: {self.current_profile.name}")

        except Exception as ex:
            logger.error(f"Error reloading config: {ex}", exc_info=True)
            print(f"Error reloading config: {ex}")

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

    def clear_modifier_state(self):
        """Clear all modifier state - call on disconnect to prevent stuck keys"""
        self.active_modifiers.clear()
        self.base_action_active.clear()
        self.combo_used.clear()

    def create_virtual_device(self):
        """Create the virtual input device (uinput)

        Should be called after loading profiles and setting capabilities.
        """
        logger.info("Creating virtual input device...")
        self.controller = UInput(
            self.capabilities,
            name='TourBox Elite',
            vendor=0xC251,
            product=0x2005
        )
        logger.info("Virtual input device created")

    def cleanup(self):
        """Clean up resources - close virtual device"""
        if self.controller:
            self.controller.close()
            self.controller = None

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the TourBox device

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from the TourBox device"""
        pass

    @abstractmethod
    async def run_connection(self) -> bool:
        """Run a single connection session

        Returns:
            True if should retry connection, False if user requested exit
        """
        pass
