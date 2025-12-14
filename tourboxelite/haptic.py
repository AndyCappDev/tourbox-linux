#!/usr/bin/env python3
"""Haptic feedback support for TourBox Elite

This module provides haptic (vibration) feedback configuration and message building
for the TourBox Elite device. The Neo model does not support haptics.

The 94-byte configuration message sent to the device contains haptic strength values
at specific byte offsets. This module builds that message dynamically based on
user configuration.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)


class HapticStrength(Enum):
    """Haptic feedback strength levels

    Values correspond to the byte values sent to the device.
    These can be combined with rotation speed bits (0x00, 0x01, 0x02).
    """
    OFF = 0x00
    WEAK = 0x04
    STRONG = 0x08

    @classmethod
    def from_string(cls, s: str) -> 'HapticStrength':
        """Parse from config string

        Args:
            s: String like 'off', 'weak', 'strong', or numeric '0', '1', '2'

        Returns:
            HapticStrength enum value
        """
        if s is None:
            return cls.OFF
        mapping = {
            'off': cls.OFF, 'none': cls.OFF, '0': cls.OFF, 'disabled': cls.OFF,
            'weak': cls.WEAK, 'light': cls.WEAK, 'low': cls.WEAK, '1': cls.WEAK,
            'strong': cls.STRONG, 'heavy': cls.STRONG, 'high': cls.STRONG, '2': cls.STRONG,
        }
        return mapping.get(s.lower().strip(), cls.OFF)

    def __str__(self) -> str:
        return self.name.lower()


# Rotary controls that have haptic feedback
HAPTIC_DIALS = ['knob', 'scroll', 'dial']

# Modifier buttons that can be combined with dials
HAPTIC_MODIFIERS = [
    None,  # Unmodified
    'tall', 'short', 'top', 'side',
    'knob_click', 'scroll_click', 'dial_click',
    'tour',
    'dpad_up', 'dpad_down', 'dpad_left', 'dpad_right',
    'c1', 'c2',
]

# Byte offsets in the 94-byte config message for haptic values
# Based on C driver analysis: tourBoxSetupMap
# Format: (dial, modifier) -> byte_offset
HAPTIC_BYTE_OFFSETS: Dict[Tuple[str, Optional[str]], int] = {
    # Knob (unmodified and with modifiers)
    ('knob', None): 4,
    ('knob', 'tall'): 6,
    ('knob', 'short'): 8,
    ('knob', 'top'): 10,
    ('knob', 'side'): 12,
    ('knob', 'knob_click'): 34,
    ('knob', 'scroll_click'): 36,
    ('knob', 'dial_click'): 38,
    ('knob', 'tour'): 40,
    ('knob', 'dpad_up'): 42,
    ('knob', 'dpad_down'): 44,
    ('knob', 'dpad_left'): 46,
    ('knob', 'dpad_right'): 48,
    ('knob', 'c1'): 50,
    ('knob', 'c2'): 52,

    # Scroll (unmodified and with modifiers)
    ('scroll', None): 14,
    ('scroll', 'tall'): 16,
    ('scroll', 'short'): 18,
    ('scroll', 'top'): 20,
    ('scroll', 'side'): 22,
    ('scroll', 'dpad_up'): 26,
    ('scroll', 'dpad_down'): 28,
    ('scroll', 'dpad_left'): 30,
    ('scroll', 'dpad_right'): 32,
    ('scroll', 'scroll_click'): 54,
    ('scroll', 'knob_click'): 56,
    ('scroll', 'dial_click'): 58,
    ('scroll', 'tour'): 60,
    ('scroll', 'c1'): 62,
    ('scroll', 'c2'): 64,

    # Dial (unmodified and with modifiers)
    ('dial', None): 24,
    ('dial', 'dial_click'): 66,
    ('dial', 'knob_click'): 68,
    ('dial', 'scroll_click'): 70,
    ('dial', 'tour'): 72,
    ('dial', 'dpad_up'): 74,
    ('dial', 'dpad_down'): 76,
    ('dial', 'dpad_left'): 78,
    ('dial', 'dpad_right'): 80,
    ('dial', 'c1'): 82,
    ('dial', 'c2'): 84,
    ('dial', 'tall'): 86,
    ('dial', 'short'): 88,
    ('dial', 'top'): 90,
    ('dial', 'side'): 92,
}

# Base 94-byte config message template (from existing CONFIG_COMMANDS)
# This is the message with all haptic values set to 0x00 (off)
_CONFIG_MESSAGE_TEMPLATE = bytes.fromhex(
    "b5005d04"  # Header + first haptic byte at offset 4
    "00050006000700080009000b000c000d"
    "000e000f0026002700280029003b003c003d003e"
    "003f004000410042004300440045004600470048"
    "0049004a004b004c004d004e004f005000510052"
    "0053005400a800a900aa00ab00fe"
)


@dataclass
class HapticConfig:
    """Per-profile haptic feedback configuration

    Designed for Phase 2 (per-dial, per-modifier) but used by Phase 1
    with a simpler access pattern (global_setting property).

    Phase 1: Set global_setting to apply same haptic to all dials
    Phase 2: Set global_setting=None and use dial_settings/combo_settings
    """
    # Per-dial settings: dial_name -> HapticStrength
    # dial_name is 'knob', 'scroll', or 'dial'
    dial_settings: Dict[str, HapticStrength] = field(default_factory=dict)

    # Per-modifier-combo settings: (dial, modifier) -> HapticStrength
    # modifier is None for unmodified, or button name like 'tall', 'side'
    combo_settings: Dict[Tuple[str, Optional[str]], HapticStrength] = field(default_factory=dict)

    # Phase 1: If set, overrides all per-dial/per-combo settings
    # When None, uses per-dial/per-combo settings (Phase 2 mode)
    global_setting: Optional[HapticStrength] = None

    def get_strength(self, dial: str, modifier: Optional[str] = None) -> HapticStrength:
        """Get haptic strength for a specific dial + modifier combo

        Args:
            dial: 'knob', 'scroll', or 'dial'
            modifier: modifier button name or None for unmodified

        Returns:
            HapticStrength value
        """
        # Phase 1: global setting overrides everything
        if self.global_setting is not None:
            return self.global_setting

        # Phase 2: check combo-specific, then dial-specific, then default
        key = (dial, modifier)
        if key in self.combo_settings:
            return self.combo_settings[key]
        if dial in self.dial_settings:
            return self.dial_settings[dial]
        return HapticStrength.OFF

    def set_global(self, strength: HapticStrength):
        """Set global haptic strength (Phase 1 mode)

        This overrides any per-dial or per-combo settings.
        """
        self.global_setting = strength

    def set_dial(self, dial: str, strength: HapticStrength):
        """Set per-dial haptic strength (Phase 2)

        Args:
            dial: 'knob', 'scroll', or 'dial'
            strength: HapticStrength value
        """
        if dial not in HAPTIC_DIALS:
            logger.warning(f"Unknown dial: {dial}")
            return
        self.dial_settings[dial] = strength

    def set_combo(self, dial: str, modifier: Optional[str], strength: HapticStrength):
        """Set per-combo haptic strength (Phase 2)

        Args:
            dial: 'knob', 'scroll', or 'dial'
            modifier: modifier button name or None
            strength: HapticStrength value
        """
        self.combo_settings[(dial, modifier)] = strength

    def is_global_mode(self) -> bool:
        """Check if in global mode (Phase 1) vs per-dial mode (Phase 2)"""
        return self.global_setting is not None

    def get_effective_global(self) -> HapticStrength:
        """Get effective global setting for display purposes

        Returns global_setting if set, otherwise OFF
        """
        return self.global_setting if self.global_setting is not None else HapticStrength.OFF

    @classmethod
    def default_off(cls) -> 'HapticConfig':
        """Create config with all haptics off (default for Neo/unknown devices)"""
        return cls(global_setting=HapticStrength.OFF)

    @classmethod
    def default_global(cls, strength: HapticStrength) -> 'HapticConfig':
        """Create config with global setting (Phase 1 style)"""
        return cls(global_setting=strength)

    def __repr__(self) -> str:
        if self.global_setting is not None:
            return f"HapticConfig(global={self.global_setting})"
        else:
            dials = ', '.join(f"{d}={s}" for d, s in self.dial_settings.items())
            combos = len(self.combo_settings)
            return f"HapticConfig(dials=[{dials}], combos={combos})"


def build_config_message(haptic_config: Optional[HapticConfig] = None) -> bytes:
    """Build 94-byte config message with haptic values

    Args:
        haptic_config: HapticConfig with settings. If None, uses all-off default.

    Returns:
        94-byte config message ready to send to device
    """
    if haptic_config is None:
        haptic_config = HapticConfig.default_off()

    # Start with template
    msg = bytearray(_CONFIG_MESSAGE_TEMPLATE)

    # Apply haptic values at known offsets
    for (dial, modifier), offset in HAPTIC_BYTE_OFFSETS.items():
        if offset < len(msg):
            strength = haptic_config.get_strength(dial, modifier)
            # Preserve existing speed bits (lower 2 bits), set haptic bits (bits 2-3)
            # Currently we don't use speed settings, so just set the haptic value
            msg[offset] = strength.value

    return bytes(msg)


def build_config_commands(haptic_config: Optional[HapticConfig] = None) -> List[bytes]:
    """Build list of config command packets for BLE transmission

    BLE has a 20-byte MTU limit, so the 94-byte message is split into chunks.

    Args:
        haptic_config: HapticConfig with settings. If None, uses all-off default.

    Returns:
        List of bytes objects (5 packets) ready to send to device via BLE
    """
    full_msg = build_config_message(haptic_config)

    # Split into chunks matching the original CONFIG_COMMANDS structure
    return [
        full_msg[0:20],   # Config 1
        full_msg[20:40],  # Config 2
        full_msg[40:60],  # Config 3
        full_msg[60:80],  # Config 4
        full_msg[80:94],  # Config 5 (14 bytes)
    ]


def build_config_message_usb(haptic_config: Optional[HapticConfig] = None) -> bytes:
    """Build config message for USB transmission

    USB can send the full message at once.

    Args:
        haptic_config: HapticConfig with settings. If None, uses all-off default.

    Returns:
        94-byte config message ready to send to device via USB serial
    """
    return build_config_message(haptic_config)
