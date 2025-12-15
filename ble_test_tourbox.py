#!/usr/bin/env python3
"""Test the discovered unlock command from Windows BLE capture"""

import asyncio
import sys
import os
from pathlib import Path
from bleak import BleakClient

def get_mac_address():
    """Get TourBox MAC address from command line, environment, or config file"""

    # 1. Check command line argument
    if len(sys.argv) > 1:
        return sys.argv[1]

    # 2. Check environment variable
    if 'TOURBOX_MAC' in os.environ:
        return os.environ['TOURBOX_MAC']

    # 3. Try to read from config files (new format first, then legacy)
    config_paths = [
        Path.home() / '.config' / 'tourbox' / 'config.conf',      # New format
        Path.home() / '.config' / 'tourbox' / 'mappings.conf',    # Legacy format
    ]
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('mac_address'):
                            mac = line.split('=')[1].strip()
                            if mac != 'XX:XX:XX:XX:XX:XX':  # Skip placeholder
                                return mac
            except Exception:
                pass

    # 4. No MAC address found
    print("Error: No TourBox MAC address provided!")
    print("\nProvide MAC address using one of these methods:")
    print("  1. Command line:   ./ble_test_tourbox.py XX:XX:XX:XX:XX:XX")
    print("  2. Environment:    TOURBOX_MAC=XX:XX:XX:XX:XX:XX ./ble_test_tourbox.py")
    print("  3. Config file:    Set mac_address in ~/.config/tourbox/config.conf")
    print("\nFind your MAC address with: bluetoothctl devices")
    sys.exit(1)

TOURBOX_MAC = get_mac_address()

# GATT characteristics from the Windows capture
VENDOR_SERVICE = "0000fff0-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR = "0000fff1-0000-1000-8000-00805f9b34fb"  # Handle 0x000d - where notifications come from
WRITE_CHAR = "0000fff2-0000-1000-8000-00805f9b34fb"   # Handle 0x0010 - where we send commands

# The unlock command discovered from Windows capture (Frame 96)
UNLOCK_COMMAND = bytes.fromhex("5500078894001afe")

notification_count = 0

def notification_handler(sender, data):
    """Handle notifications from the device"""
    global notification_count
    notification_count += 1

    print(f"\n{'='*60}")
    print(f"NOTIFICATION #{notification_count} from {sender.uuid}:")
    print(f"  Hex: {data.hex()}")
    print(f"  Len: {len(data)} bytes")

    # Check if this matches the expected unlock response from Frame 98
    if notification_count == 1 and len(data) == 28:
        print(f"  ✓✓✓ This looks like the unlock response!")
        if data.hex().startswith("07"):
            print(f"  ✓✓✓ Response starts with 0x07 - UNLOCK SUCCESSFUL!")

    print(f"{'='*60}\n")

async def main():
    print("="*60)
    print("TourBox Elite Unlock Test")
    print("Using command discovered from Windows BLE capture")
    print("="*60)
    print(f"\nConnecting to {TOURBOX_MAC}...\n")

    async with BleakClient(TOURBOX_MAC, timeout=30.0) as client:
        print(f"✓ Connected to TourBox Elite\n")

        # Step 1: Enable notifications (this writes 0x0001 to CCCD automatically)
        print("Step 1: Enabling notifications on fff1...")
        await client.start_notify(NOTIFY_CHAR, notification_handler)
        print("✓ Notifications enabled\n")

        await asyncio.sleep(0.5)

        # Step 2: Send the unlock command
        print("Step 2: Sending unlock command to fff2...")
        print(f"  Command: {UNLOCK_COMMAND.hex()}")
        print(f"  ({' '.join(f'{b:02x}' for b in UNLOCK_COMMAND)})")

        try:
            await client.write_gatt_char(WRITE_CHAR, UNLOCK_COMMAND, response=False)
            print("✓ Unlock command sent!\n")
        except Exception as e:
            print(f"✗ Error sending command: {e}\n")
            return

        # Step 3: Wait for unlock response
        print("Step 3: Waiting for unlock response...")
        await asyncio.sleep(1)

        if notification_count == 0:
            print("✗ No unlock response received!\n")
            return

        print("✓ Got unlock response!\n")

        # Step 4: Send configuration commands (from Frames 99-105)
        print("Step 4: Sending configuration commands...")

        config_commands = [
            bytes.fromhex("b5005d0400050006000700080009000b000c000d"),  # Frame 99
            bytes.fromhex("000e000f0026002700280029003b003c003d003e"),  # Frame 100
            bytes.fromhex("003f004000410042004300440045004600470048"),  # Frame 101
            bytes.fromhex("0049004a004b004c004d004e004f005000510052"),  # Frame 103
            bytes.fromhex("0053005400a800a900aa00ab00fe"),              # Frame 105
        ]

        for i, cmd in enumerate(config_commands, 1):
            print(f"  Config {i}/5: {cmd.hex()} ({len(cmd)} bytes)")
            try:
                await client.write_gatt_char(WRITE_CHAR, cmd, response=False)
                await asyncio.sleep(0.01)  # Small delay between commands
            except Exception as e:
                print(f"  ✗ Error: {e}")

        print("✓ All configuration commands sent!\n")
        await asyncio.sleep(0.5)

        if notification_count > 0:
            print("\n" + "="*60)
            print("SUCCESS! Device responded to unlock command!")
            print("="*60)
            print("\nNow try pressing buttons on your TourBox Elite...")
            print("You should see notifications for each button press!")
            print("Press Ctrl+C to exit.\n")

            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n\nExiting...")
        else:
            print("\n" + "="*60)
            print("NO RESPONSE from device")
            print("="*60)
            print("\nPossible issues:")
            print("1. Wrong characteristic UUID mapping")
            print("2. Device needs different unlock sequence")
            print("3. Try pressing buttons on the device now...")

            # Wait a bit longer in case user presses buttons
            print("\nWaiting 10 more seconds for button presses...")
            await asyncio.sleep(10)

            if notification_count == 0:
                print("\nStill no response. The unlock command may need adjustment.")

        # Cleanup
        await client.stop_notify(NOTIFY_CHAR)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExited")
