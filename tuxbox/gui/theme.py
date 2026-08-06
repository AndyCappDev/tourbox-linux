#!/usr/bin/env python3
"""Palette-aware theme helpers

The GUI inherits its colours from the active Qt palette (KDE, GNOME, etc.).
Anything that hardcodes a colour - stylesheet snippets, the controller SVG -
breaks under a dark theme, so those call sites ask for colours here instead.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def _palette() -> QPalette:
    """Current application palette (falls back to a default if no app yet)"""
    app = QApplication.instance()
    return app.palette() if app else QPalette()


def is_dark_theme(palette: QPalette = None) -> bool:
    """True when the active palette uses a dark window background

    Compares window background against window text rather than trusting
    QStyleHints.colorScheme(), which is unreliable on some platform themes.
    """
    palette = palette or _palette()
    window = palette.color(QPalette.Window)
    text = palette.color(QPalette.WindowText)
    return window.lightness() < text.lightness()


def foreground_hex(palette: QPalette = None) -> str:
    """Hex colour for line art and primary text, e.g. '#eff0f1'"""
    palette = palette or _palette()
    return palette.color(QPalette.WindowText).name()


# How far hint text is pushed from the text colour toward the background.
# 0.4 reproduces the previous hardcoded '#666' on a white background while
# staying readable on dark ones. The Disabled palette role is deliberately
# not used - it is tuned for disabled widgets and comes out far too faint.
_MUTED_BLEND = 0.4

# WCAG AA contrast for normal text. Low-contrast themes (Solarized and
# friends) start close to this, so muting has to back off rather than push
# hint text below it.
_MIN_CONTRAST = 4.5


def _relative_luminance(colour: QColor) -> float:
    """WCAG relative luminance of a colour"""
    def channel(value: int) -> float:
        v = value / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return (0.2126 * channel(colour.red())
            + 0.7152 * channel(colour.green())
            + 0.0722 * channel(colour.blue()))


def _contrast_ratio(a: QColor, b: QColor) -> float:
    """WCAG contrast ratio between two colours (1.0 to 21.0)"""
    la, lb = _relative_luminance(a), _relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def muted_text_hex(palette: QPalette = None) -> str:
    """Hex colour for hint/secondary text

    Replaces the hardcoded '#666', which is unreadable on dark backgrounds.
    Blends the palette text colour toward the window background so the result
    is legible but recessive under any theme, easing off the blend if it would
    drop hint text below readable contrast.
    """
    palette = palette or _palette()
    text = palette.color(QPalette.Active, QPalette.WindowText)
    window = palette.color(QPalette.Window)

    def mix(ratio: float) -> QColor:
        return QColor(
            round(text.red() * (1 - ratio) + window.red() * ratio),
            round(text.green() * (1 - ratio) + window.green() * ratio),
            round(text.blue() * (1 - ratio) + window.blue() * ratio),
        )

    # Take the strongest muting that still clears the contrast floor. Themes
    # with plenty of headroom keep the full blend; tight ones get less.
    ratio = _MUTED_BLEND
    while ratio > 0:
        candidate = mix(ratio)
        if _contrast_ratio(candidate, window) >= _MIN_CONTRAST:
            return candidate.name()
        ratio -= 0.05

    return text.name()


def muted_label_style(font_size_px: int = None, extra: str = "") -> str:
    """Stylesheet for a hint/secondary label, themed for the active palette

    Args:
        font_size_px: Optional font-size in px
        extra: Optional extra declarations, e.g. 'margin-bottom: 10px;'
    """
    style = f"color: {muted_text_hex()};"
    if font_size_px:
        style += f" font-size: {font_size_px}px;"
    if extra:
        style += f" {extra}"
    return style
