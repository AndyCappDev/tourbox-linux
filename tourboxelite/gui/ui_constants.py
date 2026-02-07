#!/usr/bin/env python3
"""UI scaling constants for TourBox Elite GUI

These constants ensure the UI scales properly with user font size settings.
"""

# Font-based sizing multipliers
TABLE_ROW_HEIGHT_MULTIPLIER = 1.6  # Multiplier for font line spacing to calculate table row height
TEXT_EDIT_HEIGHT_MULTIPLIER = 1.5  # Multiplier for font line spacing for single-line text edit fields

# Absolute maximum line spacing in pixels (prevents bogus font metrics)
_MAX_LINE_SPACING = 25

# Maximum fraction of screen height for line spacing
_MAX_SCREEN_FRACTION = 10


def safe_line_spacing(font_metrics):
    """Return font line spacing, capped to a sane maximum.

    Some systems (e.g., Linux Mint/Cinnamon) report wildly incorrect font metrics
    to Qt, resulting in line spacing values of 500+ pixels. This function caps the
    value to the lesser of an absolute maximum and a fraction of screen height so
    the UI remains usable.
    """
    spacing = font_metrics.lineSpacing()
    max_spacing = _MAX_LINE_SPACING
    try:
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_based = screen.size().height() // _MAX_SCREEN_FRACTION
            max_spacing = min(max_spacing, screen_based)
    except Exception:
        pass
    return min(spacing, max_spacing)
