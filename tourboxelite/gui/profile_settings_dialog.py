#!/usr/bin/env python3
"""Profile settings dialog

Dialog for editing profile settings including name and window matching rules.
"""

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QGroupBox, QMessageBox, QProgressDialog, QComboBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

# Import from existing driver code
from tourboxelite.config_loader import Profile
from tourboxelite.window_monitor import WaylandWindowMonitor, WindowInfo
from tourboxelite.haptic import HapticStrength

logger = logging.getLogger(__name__)


class ProfileSettingsDialog(QDialog):
    """Dialog for editing profile settings"""

    def __init__(self, profile: Profile, parent=None, is_new: bool = False):
        super().__init__(parent)
        self.profile = profile
        self.is_new = is_new
        self.window_monitor = None

        # Result values
        self.result_profile_name = profile.name
        self.result_app_id = profile.app_id or ""
        self.result_window_class = profile.window_class or ""
        self.result_haptic_strength = profile.haptic_config.get_effective_global()

        self._init_ui()
        self.setMinimumWidth(500)

    def _init_ui(self):
        """Initialize the UI"""
        title = "New Profile" if self.is_new else f"Edit Profile: {self.profile.name}"
        self.setWindowTitle(title)

        layout = QVBoxLayout(self)

        # Profile name section
        name_group = QGroupBox("Profile Name")
        name_layout = QFormLayout(name_group)

        self.name_edit = QLineEdit(self.profile.name)
        if not self.is_new and self.profile.name == 'default':
            # Don't allow renaming default profile
            self.name_edit.setEnabled(False)
            name_layout.addRow("Name:", self.name_edit)
            info_label = QLabel("(default profile cannot be renamed)")
            info_label.setStyleSheet("color: #666; font-size: 10px;")
            name_layout.addRow("", info_label)
        else:
            name_layout.addRow("Name:", self.name_edit)

        layout.addWidget(name_group)

        # Window matching section
        matching_group = QGroupBox("Window Matching Rules")
        matching_layout = QVBoxLayout(matching_group)

        # Info text
        info_label = QLabel(
            "This profile will activate when the focused window matches either of these identifiers.\n"
            "Leave both empty to never auto-activate (manual selection only)."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 10px; margin-bottom: 10px;")
        matching_layout.addWidget(info_label)

        # Form for matching fields
        form_layout = QFormLayout()

        self.app_id_edit = QLineEdit(self.profile.app_id or "")
        self.app_id_edit.setPlaceholderText("e.g., firefox, code, org.kde.kate")
        form_layout.addRow("App ID:", self.app_id_edit)

        self.window_class_edit = QLineEdit(self.profile.window_class or "")
        self.window_class_edit.setPlaceholderText("e.g., Firefox, Code")
        form_layout.addRow("Window Class:", self.window_class_edit)

        matching_layout.addLayout(form_layout)

        # Capture button
        capture_button = QPushButton("📷 Capture Active Window")
        capture_button.setToolTip("Click to capture window info from the currently focused window")
        capture_button.clicked.connect(self._on_capture_window)
        matching_layout.addWidget(capture_button)

        layout.addWidget(matching_group)

        # Haptic feedback section
        haptic_group = QGroupBox("Haptic Feedback")
        haptic_layout = QFormLayout(haptic_group)

        self.haptic_combo = QComboBox()
        self.haptic_combo.addItem("Off", HapticStrength.OFF)
        self.haptic_combo.addItem("Weak", HapticStrength.WEAK)
        self.haptic_combo.addItem("Strong", HapticStrength.STRONG)

        # Set current value from profile
        current_haptic = self.result_haptic_strength
        index = self.haptic_combo.findData(current_haptic)
        if index >= 0:
            self.haptic_combo.setCurrentIndex(index)

        haptic_layout.addRow("Dial Feedback:", self.haptic_combo)

        haptic_info = QLabel(
            "Controls vibration feedback for rotary controls (knob, scroll, dial).\n"
            "Only available on TourBox Elite. Neo models do not have haptic motors."
        )
        haptic_info.setWordWrap(True)
        haptic_info.setStyleSheet("color: #666; font-size: 10px;")
        haptic_layout.addRow("", haptic_info)

        layout.addWidget(haptic_group)

        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        apply_button = QPushButton("Apply")
        apply_button.setDefault(True)
        apply_button.clicked.connect(self._on_apply)
        button_layout.addWidget(apply_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _on_capture_window(self):
        """Handle capture window button click"""
        # Create countdown dialog
        countdown_dialog = QProgressDialog(
            "Switch to the window you want to capture...\n\nCapturing in 5 seconds",
            "Cancel",
            0, 5,
            self
        )
        countdown_dialog.setWindowTitle("Capture Window")
        countdown_dialog.setWindowModality(Qt.WindowModal)
        countdown_dialog.setMinimumDuration(0)
        countdown_dialog.setAutoClose(False)
        countdown_dialog.setAutoReset(False)
        countdown_dialog.show()

        # Initialize window monitor if needed
        if not self.window_monitor:
            try:
                self.window_monitor = WaylandWindowMonitor()
            except Exception as e:
                countdown_dialog.close()
                QMessageBox.critical(
                    self,
                    "Window Capture Failed",
                    f"Failed to initialize window monitor:\n{e}\n\n"
                    "Window capture may not be supported on your system."
                )
                logger.error(f"Failed to initialize window monitor: {e}")
                return

        # Countdown timer
        self.countdown_value = 5
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(
            lambda: self._countdown_tick(countdown_dialog)
        )
        self.countdown_timer.start(1000)  # 1 second intervals

        # Store dialog reference
        self.countdown_dialog = countdown_dialog

    def _countdown_tick(self, dialog):
        """Handle countdown timer tick"""
        self.countdown_value -= 1

        if self.countdown_value > 0:
            dialog.setLabelText(
                f"Switch to the window you want to capture...\n\nCapturing in {self.countdown_value} seconds"
            )
            dialog.setValue(5 - self.countdown_value)
        else:
            # Time's up - capture the window
            self.countdown_timer.stop()
            self._perform_capture(dialog)

    def _perform_capture(self, dialog):
        """Perform the window capture"""
        try:
            window_info = self.window_monitor.get_active_window()
            dialog.close()

            if window_info:
                # Populate fields with app_id and window_class only
                if window_info.app_id:
                    self.app_id_edit.setText(window_info.app_id)
                if window_info.wm_class:
                    self.window_class_edit.setText(window_info.wm_class)

                logger.info(f"Captured window: {window_info}")

                # Show success message
                QMessageBox.information(
                    self,
                    "Window Captured",
                    f"Captured window information:\n\n"
                    f"App ID: {window_info.app_id or '(none)'}\n"
                    f"Window Class: {window_info.wm_class or '(none)'}\n\n"
                    f"You can edit these values before saving."
                )
            else:
                QMessageBox.warning(
                    self,
                    "No Window Detected",
                    "Could not detect active window information.\n\n"
                    "This may happen if:\n"
                    "• You're not running a supported compositor\n"
                    "• Required tools are not installed\n"
                    "• No window was focused"
                )
                logger.warning("Window capture returned no information")

        except Exception as e:
            dialog.close()
            QMessageBox.critical(
                self,
                "Capture Failed",
                f"Failed to capture window:\n{e}"
            )
            logger.error(f"Window capture failed: {e}")

    def _on_apply(self):
        """Handle apply button click"""
        # Validate profile name
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(
                self,
                "Invalid Name",
                "Profile name cannot be empty."
            )
            return

        # Check for invalid characters in profile name
        if ':' in name or '[' in name or ']' in name:
            QMessageBox.warning(
                self,
                "Invalid Name",
                "Profile name cannot contain ':', '[', or ']' characters."
            )
            return

        # Store results
        self.result_profile_name = name
        self.result_app_id = self.app_id_edit.text().strip()
        self.result_window_class = self.window_class_edit.text().strip()
        self.result_haptic_strength = self.haptic_combo.currentData()

        # Accept the dialog
        self.accept()

    def get_results(self):
        """Get the edited profile settings

        Returns:
            Tuple of (name, app_id, window_class, haptic_strength)
        """
        return (
            self.result_profile_name,
            self.result_app_id,
            self.result_window_class,
            self.result_haptic_strength
        )
