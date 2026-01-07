#!/usr/bin/env python3
"""TourBox Elite USB Driver - Linux Input Device

Implements USB serial communication for TourBox Elite.
Uses the same button code protocol as BLE, but over USB CDC ACM serial.
"""

import sys
import os
import asyncio
import logging
import pathlib
from typing import Optional

import serial

from .device_base import TourBoxBase
from .config_loader import load_profiles, load_device_config
from .window_monitor import WaylandWindowMonitor
from .haptic import build_config_message_usb, HapticConfig

logger = logging.getLogger(__name__)

# USB Configuration
DEFAULT_USB_PORT = "/dev/ttyACM0"

# Unlock command (same as BLE)
UNLOCK_COMMAND = bytes.fromhex("5500078894001afe")

# Note: CONFIG_COMMANDS are now built dynamically by build_config_message_usb()
# from haptic.py to support per-profile haptic settings

# USB Device identification for Elite vs Neo detection
# TourBox uses STMicroelectronics VID with different PIDs
USB_VID = 0x0483  # STMicroelectronics
USB_PID_ELITE = 0x5741  # Confirmed Elite
USB_PID_AMBIGUOUS = 0x5740  # Could be Neo or early Elite firmware


class TourBoxUSB(TourBoxBase):
    """TourBox Elite USB Driver

    Implements USB serial transport. Inherits common functionality
    from TourBoxBase including button processing, modifier state machine,
    profile management, and virtual input device handling.

    The USB protocol uses the same single-byte button codes as BLE.
    """

    def __init__(self, port: str = None, pidfile: Optional[str] = None,
                 config_path: Optional[str] = None, force_haptics: bool = False):
        """Initialize the USB driver

        Args:
            port: Serial port path (default: /dev/ttyACM0)
            pidfile: Path to PID file
            config_path: Path to configuration file
            force_haptics: Force enable haptics even for ambiguous device PIDs
        """
        super().__init__(pidfile=pidfile, config_path=config_path)
        self.port = port or DEFAULT_USB_PORT
        self.serial: Optional[serial.Serial] = None
        self.reconnect_delay = 5.0
        self._read_task: Optional[asyncio.Task] = None
        self._connected = False
        self.force_haptics = force_haptics
        self.haptics_enabled = True  # Will be set based on device detection

    async def send_haptic_config(self):
        """Send haptic configuration to the device

        Called when profile switches to apply the new profile's haptic settings.
        """
        if not self.serial or not self.serial.is_open:
            logger.warning("Cannot send haptic config - not connected")
            return

        if not self.haptics_enabled:
            logger.debug("Haptics disabled for this device, skipping config send")
            return

        haptic_config = None
        if self.current_profile and self.current_profile.haptic_config:
            haptic_config = self.current_profile.haptic_config
            logger.info(f"Sending haptic config for profile '{self.current_profile.name}': {haptic_config}")

        config_message = build_config_message_usb(haptic_config)

        # Send configuration
        self.serial.write(config_message)
        self.serial.flush()
        await asyncio.sleep(0.05)

        logger.info("Haptic configuration sent")

    async def connect(self) -> bool:
        """Connect to TourBox Elite via USB serial

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to TourBox Elite at {self.port}...")

            # Check if port exists
            if not os.path.exists(self.port):
                logger.error(f"Port {self.port} does not exist")
                return False

            # Open serial port
            self.serial = serial.Serial(
                port=self.port,
                baudrate=115200,
                timeout=0.1
            )

            # Clear any pending data
            self.serial.reset_input_buffer()

            # Send unlock command
            logger.info("Sending unlock command...")
            self.serial.write(UNLOCK_COMMAND)
            self.serial.flush()
            await asyncio.sleep(0.3)

            # Read unlock response (expect 26 bytes)
            response = self.serial.read(100)
            if response:
                logger.info(f"Unlock response ({len(response)} bytes): {response.hex()}")
            else:
                logger.warning("No response to unlock command")

            self._connected = True

            # Send haptic configuration for initial profile
            await self.send_haptic_config()

            logger.info("USB device initialized")
            return True

        except serial.SerialException as e:
            logger.error(f"Serial connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"USB connection error: {e}")
            return False

    async def disconnect(self):
        """Close USB serial connection"""
        self._connected = False

        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("USB connection closed")

    async def _read_loop(self):
        """Async loop to read USB button codes"""
        loop = asyncio.get_event_loop()

        while self._connected:
            try:
                # Check for available data (non-blocking check)
                if self.serial.in_waiting > 0:
                    # Read available bytes
                    data = await loop.run_in_executor(
                        None,
                        lambda: self.serial.read(self.serial.in_waiting)
                    )

                    # Process each byte as a button code (same as BLE)
                    for byte in data:
                        self.process_button_code(bytearray([byte]))
                else:
                    # Small sleep to avoid busy loop
                    await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                break
            except serial.SerialException as e:
                logger.error(f"Serial read error: {e}")
                self._connected = False
                break
            except Exception as e:
                if isinstance(e, OSError) and getattr(e, "errno", None) == 5:
                    logger.warning("USB device I/O error (errno 5); treating as disconnect")
                    self._connected = False
                    break
                logger.error(f"USB read error: {e}")
                await asyncio.sleep(0.1)

    async def run_connection(self) -> bool:
        """Run a single USB connection session

        Returns:
            True if should retry connection, False if user requested exit
        """
        try:
            if not await self.connect():
                return True  # Retry

            logger.info("TourBox Elite USB ready!")
            print("TourBox Elite connected via USB!")
            print(f"Virtual input device: {self.controller.device.path}")

            if self.use_profiles:
                print(f"Profile switching enabled - Current profile: {self.current_profile.name}")

            print("Press Ctrl+C to exit")

            # Reset reconnect delay on successful connection
            self.reconnect_delay = 5.0

            # Start read loop
            self._read_task = asyncio.create_task(self._read_loop())

            # Main loop - check for signals and port status
            while not self.killer.kill_now and self._connected:
                # Check if config reload was requested
                if self.killer.reload_config:
                    self.reload_config_mappings()
                    self.killer.reload_config = False

                # Check if port still exists (device unplugged?)
                if not os.path.exists(self.port):
                    logger.warning(f"Port {self.port} disappeared - device unplugged?")
                    self._connected = False
                    break

                await asyncio.sleep(0.5)

            # Cleanup
            await self.disconnect()

            if self.killer.kill_now:
                return False  # Don't reconnect, user requested exit

            # Device disconnected, should retry
            print("\nTourBox Elite disconnected - waiting for reconnection...")
            self.clear_modifier_state()
            return True

        except Exception as e:
            logger.error(f"USB connection error: {e}")
            print(f"Connection error: {e}")
            await self.disconnect()
            return True  # Retry

    async def start(self):
        """Start the TourBox USB driver with automatic reconnection"""

        # Load profiles from config
        self.profiles = load_profiles(self.config_path)

        if not self.profiles:
            logger.error("No profiles found in config file")
            print("Error: Config file must contain at least one [profile:default] section")
            print("")
            print("Your config file should use the profile format:")
            print("")
            print("[device]")
            print("mac_address = XX:XX:XX:XX:XX:XX")
            print("# usb_port = /dev/ttyACM0  # Optional USB port")
            print("")
            print("[profile:default]")
            print("side = KEY_LEFTMETA")
            print("top = KEY_LEFTSHIFT")
            print("# ... (all buttons and rotary controls)")
            print("")
            print("See the default config for a complete example:")
            print("  cat tourboxelite/default_mappings.conf")
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

        # Create virtual input device
        self.create_virtual_device()

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

                # Check if port exists before trying to connect
                if not os.path.exists(self.port):
                    logger.debug(f"Waiting for {self.port} to appear...")
                    await asyncio.sleep(2.0)
                    continue

                should_retry = await self.run_connection()

                if not should_retry:
                    break

                # Wait before reconnecting with exponential backoff
                if not self.killer.kill_now:
                    delay = min(self.reconnect_delay, 10.0)
                    logger.info(f"Attempting to reconnect in {delay} seconds...")
                    print(f"Reconnecting in {delay} seconds...")
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
            await self.disconnect()
            self.cleanup()
            logger.info("TourBox Elite USB driver stopped")


def main():
    """Main entry point for USB driver"""
    import argparse

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='TourBox Elite USB Driver')
    parser.add_argument('--port', '-p', default=None,
                        help=f'USB serial port (default: {DEFAULT_USB_PORT})')
    parser.add_argument('-c', '--config', help='Path to custom config file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    # Enable debug logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get port and settings from: 1) command line, 2) environment, 3) config file, 4) default
    port = args.port or os.getenv('TOURBOX_USB_PORT')

    # Load device config for port and haptics settings
    device_config = load_device_config(args.config)

    if not port:
        port = device_config.get('usb_port', DEFAULT_USB_PORT)

    # Check for force_haptics setting (for Neo vs Elite ambiguous PIDs)
    force_haptics = device_config.get('force_haptics', False)

    logger.info(f"Using USB port: {port}")
    if force_haptics:
        logger.info("force_haptics enabled in config")

    # Create and start driver
    driver = TourBoxUSB(port=port, config_path=args.config, force_haptics=force_haptics)

    try:
        asyncio.run(driver.start())
    except KeyboardInterrupt:
        print("\nExited by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
