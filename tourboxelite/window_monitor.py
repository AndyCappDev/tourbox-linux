#!/usr/bin/env python3
"""Window monitoring for Wayland compositors

Detects active window information to enable application-specific profiles.
Supports: Sway, Hyprland, GNOME Shell (Mutter), KDE Plasma (KWin)
"""

import asyncio
import logging
import subprocess
import json
import os
from typing import Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WindowInfo:
    """Information about the active window"""
    app_id: str = ""
    title: str = ""
    wm_class: str = ""

    def __repr__(self):
        return f"WindowInfo(app_id='{self.app_id}', title='{self.title}', class='{self.wm_class}')"


class WaylandWindowMonitor:
    """Monitor active window on Wayland compositors"""

    def __init__(self):
        self.compositor = None
        self.last_window = None
        self._kdotool_path = self._find_kdotool()
        self._detect_compositor()

    def _find_kdotool(self) -> Optional[str]:
        """Find kdotool in common locations"""
        # Check common installation paths
        possible_paths = ['kdotool']  # In PATH

        # If running under sudo, check real user's home first
        sudo_user = os.environ.get('SUDO_USER')
        if sudo_user:
            sudo_home = os.path.expanduser(f'~{sudo_user}')
            possible_paths.append(os.path.join(sudo_home, '.cargo/bin/kdotool'))

        # Then check current user's home
        home = os.path.expanduser('~')
        possible_paths.extend([
            os.path.join(home, '.cargo/bin/kdotool'),  # Cargo default
            '/usr/local/bin/kdotool',  # System-wide
            '/usr/bin/kdotool',  # Package manager
        ])

        for path in possible_paths:
            try:
                result = subprocess.run(
                    [path, '--version'],
                    capture_output=True,
                    timeout=1
                )
                if result.returncode == 0:
                    return path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        return None

    def _detect_compositor(self):
        """Auto-detect which Wayland compositor is running"""

        # Check environment variables
        session = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        wayland_display = os.environ.get('WAYLAND_DISPLAY', '')

        if not wayland_display:
            logger.warning("WAYLAND_DISPLAY not set - may not be running Wayland")

        # Try to detect compositor by testing commands
        detectors = [
            ('sway', self._test_sway),
            ('hyprland', self._test_hyprland),
            ('gnome', self._test_gnome),
            ('kde', self._test_kde),
            ('niri', self._test_niri),
        ]

        for name, test_func in detectors:
            if test_func():
                self.compositor = name
                logger.info(f"Detected Wayland compositor: {name}")
                return

        logger.warning(f"Could not detect Wayland compositor (session={session})")
        logger.warning("Profile switching will be disabled")

    def _test_sway(self) -> bool:
        """Test if Sway is running"""
        try:
            result = subprocess.run(
                ['swaymsg', '-t', 'get_version'],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _test_niri(self) -> bool:
        """Test if Niri is running"""
        try:
            result = subprocess.run(
                ['niri', 'msg', 'version'],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _test_hyprland(self) -> bool:
        """Test if Hyprland is running"""
        try:
            result = subprocess.run(
                ['hyprctl', 'version'],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _test_gnome(self) -> bool:
        """Test if GNOME Shell is running"""
        try:
            result = subprocess.run(
                ['gdbus', 'introspect', '--session', '--dest', 'org.gnome.Shell',
                 '--object-path', '/org/gnome/Shell'],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _test_kde(self) -> bool:
        """Test if KDE Plasma (KWin) is running"""
        # Check if kdotool is available (required for KDE window detection)
        if not self._kdotool_path:
            return False

        try:
            result = subprocess.run(
                [self._kdotool_path, 'getactivewindow'],
                capture_output=True,
                timeout=1
            )
            # If kdotool works, KDE is running
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def get_active_window(self) -> Optional[WindowInfo]:
        """Get information about the currently active window"""

        if not self.compositor:
            return None

        try:
            if self.compositor == 'sway':
                return self._get_sway_window()
            elif self.compositor == 'hyprland':
                return self._get_hyprland_window()
            elif self.compositor == 'gnome':
                return self._get_gnome_window()
            elif self.compositor == 'kde':
                return self._get_kde_window()
            elif self.compositor == 'niri':
                return self._get_niri_window()
        except Exception as e:
            logger.error(f"Error getting active window: {e}")
            return None

        return None

    def _get_sway_window(self) -> Optional[WindowInfo]:
        """Get active window from Sway"""
        try:
            result = subprocess.run(
                ['swaymsg', '-t', 'get_tree'],
                capture_output=True,
                text=True,
                timeout=1
            )

            if result.returncode != 0:
                return None

            tree = json.loads(result.stdout)
            focused = self._find_focused_node(tree)

            if focused:
                return WindowInfo(
                    app_id=focused.get('app_id', ''),
                    title=focused.get('name', ''),
                    wm_class=focused.get('window_properties', {}).get('class', '')
                )
        except Exception as e:
            logger.debug(f"Sway window detection error: {e}")

        return None

    def _find_focused_node(self, node):
        """Recursively find the focused node in Sway tree"""
        if node.get('focused'):
            return node

        for child in node.get('nodes', []) + node.get('floating_nodes', []):
            result = self._find_focused_node(child)
            if result:
                return result

        return None

    def _get_hyprland_window(self) -> Optional[WindowInfo]:
        """Get active window from Hyprland"""
        try:
            result = subprocess.run(
                ['hyprctl', 'activewindow', '-j'],
                capture_output=True,
                text=True,
                timeout=1
            )

            if result.returncode != 0:
                return None

            window = json.loads(result.stdout)

            return WindowInfo(
                app_id=window.get('class', ''),
                title=window.get('title', ''),
                wm_class=window.get('class', '')
            )
        except Exception as e:
            logger.debug(f"Hyprland window detection error: {e}")

        return None

    def _get_niri_window(self) -> Optional[WindowInfo]:
        """Get active window from Niri"""
        try:
            result = subprocess.run(
                ['niri', 'msg', '--json', "focused-window"],
                capture_output=True,
                text=True,
                timeout=1
            )

            if result.returncode != 0:
                return None

            window = json.loads(result.stdout)

            return WindowInfo(
                app_id=window.get('app_id', ''),
                title=window.get('title', ''),
                wm_class=window.get('app_id', '')
            )
        except Exception as e:
            logger.debug(f"Niri window detection error: {e}")

        return None

    def _get_gnome_window(self) -> Optional[WindowInfo]:
        """Get active window from GNOME Shell

        Requires the "Focused Window D-Bus" extension:
        https://extensions.gnome.org/extension/5592/focused-window-d-bus/
        """
        try:
            # Try the "Focused Window D-Bus" extension first (works on modern GNOME)
            result = subprocess.run([
                'gdbus', 'call', '--session',
                '--dest', 'org.gnome.Shell',
                '--object-path', '/org/gnome/shell/extensions/FocusedWindow',
                '--method', 'org.gnome.shell.extensions.FocusedWindow.Get'
            ], capture_output=True, text=True, timeout=2)

            if result.returncode == 0 and result.stdout:
                # Parse the returned JSON from gdbus
                # Output format: ('{"wm_class": "...", "title": "...", ...}',)
                import re

                # Extract JSON string from gdbus tuple output
                json_match = re.search(r'\(\'(.+)\',\)', result.stdout)
                if json_match:
                    json_str = json_match.group(1)
                    # Parse JSON
                    try:
                        data = json.loads(json_str)
                        wm_class = data.get('wm_class', '')
                        title = data.get('title', '')

                        if wm_class or title:
                            return WindowInfo(
                                app_id=wm_class,
                                title=title,
                                wm_class=wm_class
                            )
                    except json.JSONDecodeError:
                        logger.debug("Failed to parse JSON from Focused Window D-Bus")

        except Exception as e:
            logger.debug(f"GNOME Focused Window D-Bus extension error: {e}")

        # Extension not installed - GNOME 40+ blocks Shell.Eval for security
        logger.warning("GNOME: Focused Window D-Bus extension not detected")
        logger.warning("Install from: https://extensions.gnome.org/extension/5592/focused-window-d-bus/")
        return None

    def _get_kde_window(self) -> Optional[WindowInfo]:
        """Get active window from KDE Plasma (KWin)

        Uses kdotool as a command-line tool (subprocess).
        kdotool internally uses D-Bus to communicate with KWin.

        Requires: cargo install kdotool
        """
        if not self._kdotool_path:
            return None

        try:
            # Get window class
            class_result = subprocess.run(
                [self._kdotool_path, 'getactivewindow', 'getwindowclassname'],
                capture_output=True,
                text=True,
                timeout=1
            )

            # Get window title
            title_result = subprocess.run(
                [self._kdotool_path, 'getactivewindow', 'getwindowname'],
                capture_output=True,
                text=True,
                timeout=1
            )

            if class_result.returncode == 0 or title_result.returncode == 0:
                window_class = class_result.stdout.strip() if class_result.returncode == 0 else ''
                window_title = title_result.stdout.strip() if title_result.returncode == 0 else ''

                return WindowInfo(
                    app_id=window_class,
                    title=window_title,
                    wm_class=window_class
                )

        except Exception as e:
            logger.debug(f"KDE window detection error: {e}")

        return None

    async def monitor_window_changes(self, callback, interval: float = 0.2):
        """Monitor for window changes and call callback when window changes

        Args:
            callback: Async function to call with WindowInfo when window changes
            interval: Polling interval in seconds (default 200ms)
        """
        if not self.compositor:
            logger.warning("No compositor detected - window monitoring disabled")
            return

        logger.info(f"Starting window monitor (compositor: {self.compositor}, interval: {interval}s)")

        while True:
            try:
                current_window = self.get_active_window()

                # Check if window changed
                if current_window != self.last_window:
                    if current_window:
                        logger.debug(f"Window changed: {current_window}")
                        await callback(current_window)
                    self.last_window = current_window

                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Error in window monitor: {e}")
                await asyncio.sleep(interval)


# Convenience function for testing
async def test_monitor():
    """Test window monitoring"""
    monitor = WaylandWindowMonitor()

    if not monitor.compositor:
        print("No Wayland compositor detected!")
        return

    print(f"Monitoring windows on {monitor.compositor}...")
    print("Switch between applications to see window changes")
    print("Press Ctrl+C to exit")
    print()

    async def print_window(window: WindowInfo):
        print(f"Active window: {window}")

    await monitor.monitor_window_changes(print_window, interval=0.5)


if __name__ == '__main__':
    try:
        asyncio.run(test_monitor())
    except KeyboardInterrupt:
        print("\nExiting...")
        pass
