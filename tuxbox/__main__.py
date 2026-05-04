#!/usr/bin/env python3
"""TuxBox Driver - Unified entry point with auto-detection

Automatically detects whether the TourBox is connected via USB or Bluetooth
and launches the appropriate driver.

Priority:
1. USB (scans /dev/ttyACM* devices, probes each for TourBox response)
2. BLE (fallback)

Can be overridden with --usb or --ble flags.
"""

import sys
import os
import asyncio
import argparse
import logging
import glob
import time

try:
    from . import VERSION
except ImportError:
    # Fallback for broken editable installs (e.g. Python 3.14 + legacy setuptools)
    VERSION = "unknown"
from .config_loader import load_device_config

logger = logging.getLogger(__name__)

DEFAULT_USB_PORT = "/dev/ttyACM0"

# How often the auto-detect supervisor rescans for a USB TourBox while the
# BLE transport is active. Cheap glob check first; full probe only if a
# /dev/ttyACM* device is actually present.
USB_RESCAN_INTERVAL = 3.0

# Grace period to let the BLE driver wind down after kill_now is set before
# we forcibly cancel its task. Bleak scans can be up to ~10s, so this needs
# headroom.
BLE_SHUTDOWN_TIMEOUT = 15.0

# Unlock command used to probe for TourBox
UNLOCK_COMMAND = bytes.fromhex("5500078894001afe")


def probe_usb_device(port: str) -> bool:
    """Probe a USB serial port to check if it's a TourBox Elite

    Sends the unlock command and checks for a valid response.

    Args:
        port: Serial port path to check

    Returns:
        True if the device responds like a TourBox, False otherwise
    """
    try:
        import serial
    except ImportError:
        logger.warning("pyserial not installed, cannot probe USB devices")
        return os.path.exists(port)  # Fall back to simple existence check

    try:
        logger.debug(f"Probing {port} for TourBox...")

        # Try to open the port
        ser = serial.Serial(port, baudrate=115200, timeout=0.5)
        ser.reset_input_buffer()

        # Send unlock command
        ser.write(UNLOCK_COMMAND)
        ser.flush()

        # Wait for response
        time.sleep(0.3)

        # Read response - TourBox should respond with ~26 bytes
        response = ser.read(100)
        ser.close()

        if response:
            logger.debug(f"  Response from {port}: {response.hex()[:40]}...")
            # TourBox unlock response is typically 26 bytes
            # Different firmware versions may have different first bytes (0x07, 0x7a, etc.)
            # Accept any response of reasonable length as a valid TourBox
            if len(response) >= 20:
                logger.info(f"  Found TourBox at {port} ({len(response)} bytes)")
                return True
            else:
                logger.debug(f"  {port} responded but too short ({len(response)} bytes)")
        else:
            logger.debug(f"  No response from {port}")

        return False

    except serial.SerialException as e:
        logger.debug(f"  Cannot open {port}: {e}")
        return False
    except Exception as e:
        logger.debug(f"  Error probing {port}: {e}")
        return False


def find_tuxbox_usb_port(configured_port: str = None) -> str:
    """Find the TourBox Elite USB port by scanning available devices

    Args:
        configured_port: User-configured port to try first

    Returns:
        Port path if found, None otherwise
    """
    # If a specific port is configured, try it first
    if configured_port and os.path.exists(configured_port):
        logger.debug(f"Trying configured port: {configured_port}")
        if probe_usb_device(configured_port):
            return configured_port

    # Scan all ttyACM devices
    acm_devices = sorted(glob.glob("/dev/ttyACM*"))

    if not acm_devices:
        logger.debug("No /dev/ttyACM* devices found")
        return None

    logger.debug(f"Found {len(acm_devices)} ACM device(s): {acm_devices}")

    for port in acm_devices:
        # Skip if we already tried the configured port
        if port == configured_port:
            continue

        if probe_usb_device(port):
            return port

    return None


async def _wait_for_ble_to_stop(ble_task):
    """Wait for a TuxBoxBLE.start() task to wind down after kill_now is set.

    Falls back to cancellation if the driver does not stop within
    BLE_SHUTDOWN_TIMEOUT (e.g. stuck mid-scan inside bleak).
    """
    try:
        await asyncio.wait_for(asyncio.shield(ble_task), timeout=BLE_SHUTDOWN_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(
            f"BLE driver did not exit gracefully within {BLE_SHUTDOWN_TIMEOUT:.0f}s; "
            "cancelling"
        )
        ble_task.cancel()
        try:
            await ble_task
        except (asyncio.CancelledError, Exception):
            pass


async def auto_detect_loop(args, configured_usb_port):
    """Auto-detect transport with USB hot-plug awareness.

    Once USB is selected the supervisor steps out of the way: TuxBoxUSB has
    its own internal hot-plug + reconnect loop and handles cable
    disconnect/reconnect itself.

    When USB is absent at startup, the supervisor runs TuxBoxBLE alongside
    a watcher that promotes to USB the moment a TourBox-responsive
    /dev/ttyACM* device appears. This is the common case for users who
    log in before plugging the cable in, or who share the device across
    multiple computers.
    """
    from .device_usb import TuxBoxUSB
    from .device_ble import TuxBoxBLE

    while True:
        usb_port = find_tuxbox_usb_port(configured_usb_port)

        if usb_port:
            logger.info(f"Auto-detected TourBox at {usb_port}")
            print(f"Found TourBox on USB ({usb_port})")
            await TuxBoxUSB(port=usb_port, config_path=args.config).start()
            return

        logger.info("No TourBox USB device found, using BLE")
        print("No USB device found, using Bluetooth")
        ble_driver = TuxBoxBLE(config_path=args.config)
        ble_task = asyncio.create_task(ble_driver.start())
        promoted_to_usb = False

        try:
            while not ble_task.done():
                await asyncio.sleep(USB_RESCAN_INTERVAL)
                # Cheap glob first; only run the full probe if a port exists
                if not glob.glob("/dev/ttyACM*"):
                    continue
                detected = find_tuxbox_usb_port(configured_usb_port)
                if not detected:
                    continue
                logger.info(
                    f"USB device detected at {detected} - "
                    "switching from BLE to USB"
                )
                print("\nUSB cable detected - switching to USB connection...")
                ble_driver.killer.kill_now = True
                promoted_to_usb = True
                break
        finally:
            await _wait_for_ble_to_stop(ble_task)

        if not promoted_to_usb:
            # BLE task ended on its own (signal received, or unrecoverable error).
            return


def main():
    """Main entry point with auto-detection"""

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='TuxBox Driver (auto-detects USB or BLE)',
        epilog='By default, scans for USB first, then falls back to Bluetooth.'
    )
    parser.add_argument('--version', action='version',
                        version=f'TuxBox {VERSION}')
    parser.add_argument('--usb', action='store_true',
                        help='Force USB mode')
    parser.add_argument('--ble', action='store_true',
                        help='Force BLE mode')
    parser.add_argument('--port', '-p',
                        help=f'USB serial port (default: {DEFAULT_USB_PORT})')
    parser.add_argument('-c', '--config',
                        help='Path to custom config file')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')

    args = parser.parse_args()

    # Enable debug logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load device config
    device_config = load_device_config(args.config)

    # Determine USB port
    usb_port = args.port or device_config.get('usb_port', DEFAULT_USB_PORT)

    # Determine connection mode
    if args.usb and args.ble:
        print("Error: Cannot specify both --usb and --ble")
        sys.exit(1)

    try:
        if args.usb:
            logger.info("USB mode forced via --usb flag")
            from .device_usb import TuxBoxUSB

            # Scan for the device if no explicit port was given
            if not args.port:
                detected_port = find_tuxbox_usb_port(usb_port)
                if detected_port:
                    usb_port = detected_port
                elif not os.path.exists(usb_port):
                    print("Error: No TourBox found on USB")
                    print("Is the TourBox connected via USB cable?")
                    print("Checked: /dev/ttyACM* devices")
                    sys.exit(1)

            if not os.path.exists(usb_port):
                print(f"Error: USB port {usb_port} not found")
                print("Is the TourBox connected via USB?")
                sys.exit(1)

            asyncio.run(TuxBoxUSB(port=usb_port, config_path=args.config).start())

        elif args.ble:
            logger.info("BLE mode forced via --ble flag")
            from .device_ble import TuxBoxBLE
            asyncio.run(TuxBoxBLE(config_path=args.config).start())

        else:
            # Auto-detect with USB hot-plug awareness. The supervisor stays
            # alive across the full session so that plugging the cable in
            # after login (or replugging after using the device on another
            # computer) is picked up automatically without a service restart.
            print("Scanning for TourBox...")
            asyncio.run(auto_detect_loop(args, usb_port))

    except KeyboardInterrupt:
        print("\nExited by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
