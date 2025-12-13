# TourBox Elite Protocol - SOLVED

**Date:** October 31, 2025 (BLE), December 2025 (USB)
**Status:** ✅ WORKING - Both USB and Bluetooth LE fully functional on Linux

---

## Executive Summary

Successfully reverse-engineered the TourBox Elite authentication protocol by capturing Windows traffic with Microsoft's Bluetooth Virtual Sniffer (BTVS). The device requires a specific unlock sequence before it will report button presses.

**Key Achievement:** TourBox Elite now works on Linux via both **USB** and **Bluetooth Low Energy** without requiring the official Windows software. The same unlock command and button codes work for both connection methods.

---

## The Problem

The TourBox Elite would connect via BLE but responded with `<!not_allow_config!>` to all configuration attempts. The device requires authentication before it will:
- Accept configuration commands
- Report button presses
- Function as an input device

---

## The Solution

### Traffic Capture Method

1. **Tool Used:** Microsoft Bluetooth Virtual Sniffer (BTVS)
   - Part of Bluetooth Test Platform Pack v1.14.0
   - Download: https://download.microsoft.com/download/e/e/e/eeed3cd5-bdbd-47db-9b8e-ca9d2df2cd29/BluetoothTestPlatformPack-1.14.0.msi
   - Location: `C:\BTP\v1.14.0\AMD64\btvs.exe`

2. **Capture Process:**
   ```cmd
   cd C:\BTP\v1.14.0\AMD64
   btvs.exe -Mode Wireshark
   ```
   - Launches Wireshark with live BLE capture
   - Open TourBox Console app
   - Let it connect and initialize device
   - Stop capture in Wireshark
   - Export ATT packets as text

3. **Analysis:** Filtered for Bluetooth ATT (Attribute Protocol) write operations to identify initialization sequence

---

## Device Information

- **Model:** TourBox Elite
- **BLE Address:** D9:BE:1E:CC:40:D7
- **USB IDs:** Vendor 0xc251, Product 0x2005
- **Manufacturer:** TourBox Tech

### GATT Services & Characteristics

**Vendor Service:** `0000fff0-0000-1000-8000-00805f9b34fb`

| UUID | Handle | Type | Purpose |
|------|--------|------|---------|
| `0000fff1-0000-1000-8000-00805f9b34fb` | 0x000d | Notify | Button/control data from device |
| `0000fff2-0000-1000-8000-00805f9b34fb` | 0x0010 | Write | Commands to device |
| Client Characteristic Config | 0x000e | Write | Enable notifications (standard BLE) |

---

## Protocol Details

### Initialization Sequence

#### Step 1: Enable Notifications
**Action:** Write to CCCD (Client Characteristic Configuration Descriptor)
- **Handle:** 0x000e
- **Value:** `01 00` (enable notifications)
- **Purpose:** Subscribe to button data notifications on characteristic fff1

#### Step 2: Send Unlock Command
**Action:** Write to characteristic fff2 (handle 0x0010)
- **Command:** `55 00 07 88 94 00 1a fe`
- **Length:** 8 bytes
- **Timing:** ~80ms after enabling notifications
- **Purpose:** Authenticate and unlock device for configuration

**Expected Response:**
- **Source:** Notification from fff1 (handle 0x000d)
- **Data:** `07 ca 31 78 1b b2 b5 db 1d d5 6c 07 f0 00 00 00 00 00 00 01 00 03 02 02 00 00`
- **Length:** 26 bytes
- **Indicator:** Starts with `0x07` - unlock successful

#### Step 3: Send Configuration Commands
**Action:** Write 5 configuration packets to fff2 (handle 0x0010)

All commands use Write Command (no response expected):

1. **Config 1 (20 bytes):**
   ```
   b5 00 5d 04 00 05 00 06 00 07 00 08 00 09 00 0b 00 0c 00 0d
   ```

2. **Config 2 (20 bytes):**
   ```
   00 0e 00 0f 00 26 00 27 00 28 00 29 00 3b 00 3c 00 3d 00 3e
   ```

3. **Config 3 (20 bytes):**
   ```
   00 3f 00 40 00 41 00 42 00 43 00 44 00 45 00 46 00 47 00 48
   ```

4. **Config 4 (20 bytes):**
   ```
   00 49 00 4a 00 4b 00 4c 00 4d 00 4e 00 4f 00 50 00 51 00 52
   ```

5. **Config 5 (14 bytes):**
   ```
   00 53 00 54 00 a8 00 a9 00 aa 00 ab 00 fe
   ```

**Purpose:** These commands likely:
- Enable button event reporting
- Configure active controls
- Set data format/mode
- Map button IDs

#### Step 4: Device Ready
After configuration, the device begins sending button notifications on fff1.

---

## Button Data Format

### Basic Protocol

Button data arrives as **1-byte notifications** on characteristic fff1.

### Button State Encoding

- **Bit 7 = 0 (0x00-0x7F):** Button pressed or control activated
- **Bit 7 = 1 (0x80-0xFF):** Button released (pressed value + 0x80)

#### "IN payload" from each button to computer

| Button | "Pressed" payload | "Released" payload |
| ------ | ----------------- | ------------------ |
|  Side  |       `01`        |        `81`        |
| Scroll |       `0a`        |        `8a`        |
|  Top   |       `02`        |        `82`        |
|   C1   |       `22`        |        `a2`        |
|   C2   |       `23`        |        `a3`        |
|  Tall  |       `00`        |        `80`        |
| Short  |       `03`        |        `83`        |
|   Up   |       `10`        |        `90`        |
|  Down  |       `11`        |        `91`        |
|  Left  |       `12`        |        `92`        |
| Right  |       `13`        |        `93`        |
|  Knob  |       `37`        |        `b7`        |
|  Tour  |       `2a`        |        `aa`        |
|  Dial  |       `38`        |        `b8`        |

**Pattern:** Each button has a unique ID (0x09, 0x0a, 0x22, 0x23, 0x37, etc.). Release is always `button_id | 0x80`.

#### "IN payload" from each dial to computer

|  Knob  | Clockwise/up payload | Counterclockwise/down payload |
| ------ | -------------------- | ----------------------------- |
| Scroll |         `49`         |             `09`              |
|  Knob  |         `44`         |             `04`              |
|  Dial  |         `4f`         |             `0f`              |


---

## Working Python Implementation

### Complete Script

`ble_unlock_tourbox.py`

```python
#!/usr/bin/env python3
"""Test the discovered unlock command from Windows BLE capture"""

import asyncio
from bleak import BleakClient

TOURBOX_MAC = "D9:BE:1E:CC:40:D7"

# GATT characteristics
VENDOR_SERVICE = "0000fff0-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR = "0000fff1-0000-1000-8000-00805f9b34fb"
WRITE_CHAR = "0000fff2-0000-1000-8000-00805f9b34fb"

# Unlock command from Windows capture
UNLOCK_COMMAND = bytes.fromhex("5500078894001afe")

notification_count = 0

def notification_handler(sender, data):
    """Handle notifications from the device"""
    global notification_count
    notification_count += 1
    print(f"NOTIFICATION #{notification_count}: {data.hex()}")

async def main():
    async with BleakClient(TOURBOX_MAC, timeout=30.0) as client:
        print("Connected to TourBox Elite\n")

        # Step 1: Enable notifications
        await client.start_notify(NOTIFY_CHAR, notification_handler)
        print("Notifications enabled\n")
        await asyncio.sleep(0.5)

        # Step 2: Send unlock command
        await client.write_gatt_char(WRITE_CHAR, UNLOCK_COMMAND, response=False)
        print("Unlock command sent\n")
        await asyncio.sleep(1)

        # Step 3: Send configuration commands
        config_commands = [
            bytes.fromhex("b5005d0400050006000700080009000b000c000d"),
            bytes.fromhex("000e000f0026002700280029003b003c003d003e"),
            bytes.fromhex("003f004000410042004300440045004600470048"),
            bytes.fromhex("0049004a004b004c004d004e004f005000510052"),
            bytes.fromhex("0053005400a800a900aa00ab00fe"),
        ]

        for cmd in config_commands:
            await client.write_gatt_char(WRITE_CHAR, cmd, response=False)
            await asyncio.sleep(0.01)

        print("Configuration complete!\n")
        print("Press buttons on TourBox Elite...\n")

        # Keep listening for button presses
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

        await client.stop_notify(NOTIFY_CHAR)

if __name__ == "__main__":
    asyncio.run(main())
```

### Dependencies

```bash
pip install bleak
```

### Usage

```bash
python3 ble_unlock_tourbox.py
```

---

## Technical Analysis

### Why This Works

1. **Authentication Bypass:** The unlock command `55 00 07 88 94 00 1a fe` is likely a session key or authentication token that proves the client is authorized
2. **Configuration Data:** The 5 config packets contain button mapping tables or enable flags for different control types
3. **Event Model:** Device uses push notifications rather than polling - efficient for battery-powered BLE devices

### Command Structure (Hypothesis)

**Unlock Command:** `55 00 07 88 94 00 1a fe`
- `55` - Possible command prefix/header
- `00 07 88 94 00 1a` - Possible challenge/response or device-specific key
- `fe` - Possible checksum or terminator

**Config Commands Pattern:**
- Start with `b5` or `00`
- Contain 2-byte pairs: `00 XX` format
- Values `04-54`, `a8-ab`, `fe` suggest button/control IDs
- Likely mapping table: "enable reporting for controls 0x04, 0x05, 0x06..."

---

## USB Protocol

The TourBox Elite also supports USB connection via CDC ACM serial interface. The USB protocol uses the **same unlock command and button codes** as Bluetooth LE.

### USB Connection Details

- **Device Path:** `/dev/ttyACM0` (Linux CDC ACM driver)
- **USB IDs:** Vendor 0xc251, Product 0x2005
- **Baud Rate:** 115200 (or any standard rate - CDC ACM is virtual serial)
- **Permissions:** User must be in `dialout` group

### USB Initialization Sequence

The USB initialization is identical to BLE:

1. **Open serial port** at `/dev/ttyACM0`
2. **Send unlock command:** `55 00 07 88 94 00 1a fe` (same as BLE)
3. **Send configuration commands:** Same 5 config packets as BLE
4. **Read button data:** Single-byte button codes (same format as BLE)

### USB vs BLE Comparison

| Aspect | USB | Bluetooth LE |
|--------|-----|--------------|
| Connection | `/dev/ttyACM0` serial | GATT over BLE |
| Unlock command | `5500078894001afe` | `5500078894001afe` |
| Button codes | Single byte (0x01, 0x81, etc.) | Single byte (same codes) |
| Config commands | Same 5 packets | Same 5 packets |
| User setup | Just plug in cable | Configure MAC address |
| Permissions | `dialout` group | `input` group |

**Key Finding:** The unlock command and button codes are identical for both USB and BLE. The device uses the same application-layer protocol regardless of transport.

---

## Comparison with Previous Attempts

### What Didn't Work Initially

1. **Traditional BLE Pairing:**
   - Authentication always failed (status 0x05)
   - Classic pairing methods don't work
   - Device uses application-layer auth instead

2. **Direct BLE Connection (no unlock):**
   - Device connects successfully
   - Reports `<!not_allow_config!>` to all commands
   - Requires specific unlock sequence discovered via capture

### What Worked

- **Application-layer authentication** via specific unlock command (works for both USB and BLE)
- **No traditional BLE pairing required** - just connect and authenticate
- **Windows traffic capture** revealed the exact sequence
- **USB serial works** with the same unlock command as BLE

---

## Next Steps

### Immediate (Driver Development)

1. **Protocol Documentation:**
   - Determine if unlock command is static or changes
   - Understand config command format
   - Identify if device sends additional notification types

2. **Create Linux Input Driver:**
   - Map button codes to Linux input events
   - Handle dial/scroll wheel as REL_DIAL or REL_WHEEL
   - Support all buttons and controls
   - Package as systemd service

### Long-term (Enhancement)

1. **Configuration Support:**
   - Reverse engineer command protocol for:
     - LED control
     - Haptic feedback settings
     - Button remapping
     - Sensitivity adjustment

2. **Multi-device Support:**
   - Test if unlock command works on other TourBox Elite units
   - Verify protocol is consistent across firmware versions
   - Support dual-channel Bluetooth switching

3. **Integration:**
   - Create evdev driver for X11/Wayland
   - Add udev rules for automatic setup
   - Package for Debian/Ubuntu/Arch

---

## Files Created

### Scripts
- `ble_unlock_tourbox.py` - Working driver implementation (run this first to unlock the TourBox)
- `ble_scan_and_pair.py` - BLE connection tool
- `ble_read_buttons.py` - Notification subscriber
- `ble_test_all_chars.py` - Characteristic tester

### Documentation
- `TOURBOX_ELITE_PROTOCOL_SOLVED.md` - This file
- `WINDOWS_BLE_CAPTURE_GUIDE.md` - Traffic capture instructions

### Captured Data
- `tourbox_att_packets.txt` - Wireshark ATT packet export
- Windows BLE capture from BTVS (analyzed in Wireshark)

---

## Key Insights

1. **Hidden Auth Protocol:** TourBox Elite uses proprietary application-layer authentication, not standard BLE pairing
2. **Windows-First Design:** Device assumes official Windows software will initialize it
3. **Reversible via Capture:** Protocol is not encrypted, just undocumented
4. **Simple Once Known:** Total initialization is ~8 bytes unlock + 94 bytes config
5. **Standard BLE Otherwise:** Once unlocked, uses standard GATT notify/write operations

---

## Credits

**Reverse Engineering Process:**
- Traffic capture: Microsoft Bluetooth Virtual Sniffer (BTVS)
- Analysis: Wireshark with Bluetooth ATT filtering
- Implementation: Python with bleak library
- Testing: Linux (Debian 13) with built-in Bluetooth

**References:**
- TourBoxForLinux project: https://github.com/rowan-mcalpin/TourBoxForLinux
- Microsoft BTP Package: https://learn.microsoft.com/en-us/windows-hardware/drivers/bluetooth/testing-btp-setup-package
- Bleak Python library: https://github.com/hbldh/bleak

---

## License

This documentation is provided for educational and interoperability purposes. The TourBox Elite hardware and official software remain property of TourBox Tech.

**Use Responsibly:** This information enables Linux support for hardware you own. Do not use to bypass legitimate security, violate terms of service, or harm the manufacturer.

---

**Status:** Protocol fully documented and working (USB and BLE) ✅
**Last Updated:** December 2025
**Contact:** Share improvements via GitHub issues or pull requests
