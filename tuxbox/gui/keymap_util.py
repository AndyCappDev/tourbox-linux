#!/usr/bin/env python3
"""Keyboard layout utility for locale-aware key display.

Queries the system's current XKB keyboard layout via libxkbcommon to determine
what character each physical key produces. This allows the GUI to display the
correct symbol for the user's keyboard layout (e.g., '+' instead of '-' on
Finnish keyboards where the minus key produces '+').
"""

import ctypes
import ctypes.util
import logging
from typing import Dict, Optional

from evdev import ecodes as e

logger = logging.getLogger(__name__)

# Symbol keys that may differ between keyboard layouts.
# Maps KEY_* name -> evdev keycode for keys where the US symbol
# doesn't match other layouts.
_SYMBOL_KEYS = {
    'KEY_MINUS': e.KEY_MINUS,
    'KEY_EQUAL': e.KEY_EQUAL,
    'KEY_LEFTBRACE': e.KEY_LEFTBRACE,
    'KEY_RIGHTBRACE': e.KEY_RIGHTBRACE,
    'KEY_SEMICOLON': e.KEY_SEMICOLON,
    'KEY_APOSTROPHE': e.KEY_APOSTROPHE,
    'KEY_GRAVE': e.KEY_GRAVE,
    'KEY_BACKSLASH': e.KEY_BACKSLASH,
    'KEY_COMMA': e.KEY_COMMA,
    'KEY_DOT': e.KEY_DOT,
    'KEY_SLASH': e.KEY_SLASH,
}

# US layout symbols (fallback when xkbcommon is unavailable)
_US_SYMBOLS = {
    'KEY_MINUS': '-',
    'KEY_EQUAL': '=',
    'KEY_LEFTBRACE': '[',
    'KEY_RIGHTBRACE': ']',
    'KEY_SEMICOLON': ';',
    'KEY_APOSTROPHE': "'",
    'KEY_GRAVE': '`',
    'KEY_BACKSLASH': '\\',
    'KEY_COMMA': ',',
    'KEY_DOT': '.',
    'KEY_SLASH': '/',
}

# Cached result
_system_hints: Optional[Dict[str, str]] = None


class _XkbRuleNames(ctypes.Structure):
    """xkb_rule_names struct for xkb_keymap_new_from_names()"""
    _fields_ = [
        ('rules', ctypes.c_char_p),
        ('model', ctypes.c_char_p),
        ('layout', ctypes.c_char_p),
        ('variant', ctypes.c_char_p),
        ('options', ctypes.c_char_p),
    ]


def _query_xkbcommon() -> Dict[str, str]:
    """Query libxkbcommon for the current keyboard layout's symbol characters.

    Returns:
        Dict mapping KEY_* name -> display character for symbol keys
        that differ from the US layout, or empty dict on failure.
    """
    try:
        lib_path = ctypes.util.find_library('xkbcommon')
        lib = ctypes.CDLL(lib_path or 'libxkbcommon.so.0')
    except OSError:
        logger.debug("libxkbcommon not available, using US layout fallback")
        return {}

    try:
        # Set up function signatures
        lib.xkb_context_new.restype = ctypes.c_void_p
        lib.xkb_context_new.argtypes = [ctypes.c_int]
        lib.xkb_keymap_new_from_names.restype = ctypes.c_void_p
        lib.xkb_keymap_new_from_names.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(_XkbRuleNames), ctypes.c_int
        ]
        lib.xkb_keymap_key_get_syms_by_level.restype = ctypes.c_int
        lib.xkb_keymap_key_get_syms_by_level.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_uint32, ctypes.POINTER(ctypes.POINTER(ctypes.c_uint32))
        ]
        lib.xkb_keysym_to_utf32.restype = ctypes.c_uint32
        lib.xkb_keysym_to_utf32.argtypes = [ctypes.c_uint32]
        lib.xkb_keymap_unref.argtypes = [ctypes.c_void_p]
        lib.xkb_context_unref.argtypes = [ctypes.c_void_p]

        # Create context and load system keymap
        ctx = lib.xkb_context_new(0)
        if not ctx:
            logger.debug("Failed to create xkb context")
            return {}

        # NULL names = use system defaults (current layout)
        keymap = lib.xkb_keymap_new_from_names(ctx, None, 0)
        if not keymap:
            lib.xkb_context_unref(ctx)
            logger.debug("Failed to load xkb keymap")
            return {}

        hints = {}
        for key_name, evdev_code in _SYMBOL_KEYS.items():
            xkb_code = evdev_code + 8  # evdev -> XKB offset
            syms = ctypes.POINTER(ctypes.c_uint32)()
            count = lib.xkb_keymap_key_get_syms_by_level(
                keymap, xkb_code, 0, 0, ctypes.byref(syms)
            )
            if count > 0:
                codepoint = lib.xkb_keysym_to_utf32(syms[0])
                if codepoint > 0:
                    char = chr(codepoint)
                    us_char = _US_SYMBOLS.get(key_name)
                    if char != us_char:
                        hints[key_name] = char

        lib.xkb_keymap_unref(keymap)
        lib.xkb_context_unref(ctx)

        if hints:
            logger.info(f"Detected non-US key layout for {len(hints)} symbol keys: {hints}")
        else:
            logger.debug("System keyboard layout matches US symbols")

        return hints

    except Exception as ex:
        logger.debug(f"xkbcommon query failed: {ex}")
        return {}


def get_system_display_hints() -> Dict[str, str]:
    """Get display hints from the system's current keyboard layout.

    Queries libxkbcommon once and caches the result. Returns a dict mapping
    KEY_* names to their locale-aware display characters for any symbol keys
    that differ from the US layout.

    Returns:
        Dict of KEY_* name -> display character (only for non-US keys),
        or empty dict if the layout matches US or xkbcommon is unavailable.
    """
    global _system_hints
    if _system_hints is None:
        _system_hints = _query_xkbcommon()
    return _system_hints
