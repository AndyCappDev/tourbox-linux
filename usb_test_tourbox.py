#!/usr/bin/env python3
"""Test the USB serial connection to TourBox Elite"""

import sys
import time
import serial

DEFAULT_PORT = "/dev/ttyACM0"

def get_usb_port():
    """Get USB port from command line or use default"""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return DEFAULT_PORT

USB_PORT = get_usb_port()

# The unlock command (same as BLE)
UNLOCK_COMMAND = bytes.fromhex("5500078894001afe")

# Configuration commands (same as BLE)
CONFIG_COMMANDS = [
    bytes.fromhex("b5005d0400050006000700080009000b000c000d"),
    bytes.fromhex("000e000f0026002700280029003b003c003d003e"),
    bytes.fromhex("003f004000410042004300440045004600470048"),
    bytes.fromhex("0049004a004b004c004d004e004f005000510052"),
    bytes.fromhex("0053005400a800a900aa00ab00fe"),
]

def main():
    print("=" * 60)
    print("TourBox Elite USB Test")
    print("Using same unlock command as BLE")
    print("=" * 60)
    print(f"\nConnecting to {USB_PORT}...\n")

    try:
        ser = serial.Serial(USB_PORT, baudrate=115200, timeout=0.1)
    except serial.SerialException as e:
        print(f"Error opening {USB_PORT}: {e}")
        print("\nMake sure:")
        print("  1. TourBox is connected via USB cable")
        print("  2. You're in the 'dialout' group: groups | grep dialout")
        print("  3. The device exists: ls -la /dev/ttyACM0")
        sys.exit(1)

    print(f"Connected to {USB_PORT}\n")

    # Clear any pending data
    ser.reset_input_buffer()

    # Step 1: Send unlock command
    print("Step 1: Sending unlock command...")
    print(f"  Command: {UNLOCK_COMMAND.hex()}")
    print(f"  ({' '.join(f'{b:02x}' for b in UNLOCK_COMMAND)})")

    ser.write(UNLOCK_COMMAND)
    print("Unlock command sent!\n")

    time.sleep(0.5)

    # Check for response
    response = ser.read(100)
    if response:
        print(f"Unlock response: {response.hex()} ({len(response)} bytes)")
        if response[0:1] == b'\x07':
            print("Response starts with 0x07 - UNLOCK SUCCESSFUL!\n")
    else:
        print("No unlock response (this is normal for USB)\n")

    # Step 2: Send configuration commands
    print("Step 2: Sending configuration commands...")

    for i, cmd in enumerate(CONFIG_COMMANDS, 1):
        print(f"  Config {i}/5: {cmd.hex()} ({len(cmd)} bytes)")
        ser.write(cmd)
        time.sleep(0.01)

    print("All configuration commands sent!\n")

    time.sleep(0.5)

    # Check for any response
    response = ser.read(100)
    if response:
        print(f"Config response: {response.hex()}\n")

    print("=" * 60)
    print("SUCCESS! Device initialized.")
    print("=" * 60)
    print("\nNow try pressing buttons on your TourBox Elite...")
    print("You should see single-byte button codes.")
    print("Press Ctrl+C to exit.\n")

    notification_count = 0

    try:
        while True:
            data = ser.read(1)
            if data:
                notification_count += 1
                byte_val = data[0]

                # Determine if press or release
                if byte_val & 0x80:
                    state = "RELEASE"
                    button_id = byte_val & 0x7F
                else:
                    state = "PRESS"
                    button_id = byte_val

                print(f"Button #{notification_count}: 0x{byte_val:02x} ({state}, id=0x{button_id:02x})")

    except KeyboardInterrupt:
        print(f"\n\nExiting... Received {notification_count} button events.")

    finally:
        ser.close()

if __name__ == "__main__":
    main()
