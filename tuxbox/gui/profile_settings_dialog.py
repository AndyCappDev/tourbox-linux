#!/usr/bin/env python3
"""Profile settings dialog

Dialog for editing profile settings including name and window matching rules.
"""

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QGroupBox, QMessageBox, QProgressDialog, QComboBox,
    QSlider, QSpinBox, QCheckBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

# Import from existing driver code
from tuxbox.config_loader import Profile
from tuxbox.window_monitor import WindowMonitor, WindowInfo
from tuxbox.gui.theme import muted_label_style
from tuxbox.haptic import HapticStrength, HapticSpeed

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
        self.result_haptic_speed = profile.haptic_config.get_effective_speed()
        self.result_double_click_timeout = profile.double_click_timeout
        self.result_modifier_delay = profile.modifier_delay  # None = use global

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
            info_label.setStyleSheet(muted_label_style(10))
            name_layout.addRow("", info_label)
        else:
            name_layout.addRow("Name:", self.name_edit)

        layout.addWidget(name_group)

        # Window matching section
        matching_group = QGroupBox("Window Matching Rules")
        matching_layout = QFormLayout(matching_group)

        # Info text
        info_label = QLabel(
            "This profile will activate when the focused window matches either of these identifiers.\n"
            "Leave both empty to disable auto-activation (default profile will be used instead)."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(muted_label_style(10))
        matching_layout.addRow(info_label)

        self.app_id_edit = QLineEdit(self.profile.app_id or "")
        self.app_id_edit.setPlaceholderText("e.g., firefox, code, org.kde.kate")
        matching_layout.addRow("App ID:", self.app_id_edit)

        self.window_class_edit = QLineEdit(self.profile.window_class or "")
        self.window_class_edit.setPlaceholderText("e.g., Firefox, Code")
        matching_layout.addRow("Window Class:", self.window_class_edit)

        # Capture button
        capture_button = QPushButton("📷 Capture Active Window")
        capture_button.setToolTip("Click to capture window info from the currently focused window")
        capture_button.clicked.connect(self._on_capture_window)
        matching_layout.addRow(capture_button)

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

        haptic_layout.addRow("Strength:", self.haptic_combo)

        # Speed dropdown
        self.haptic_speed_combo = QComboBox()
        self.haptic_speed_combo.addItem("Fast (more detents)", HapticSpeed.FAST)
        self.haptic_speed_combo.addItem("Medium", HapticSpeed.MEDIUM)
        self.haptic_speed_combo.addItem("Slow (fewer detents)", HapticSpeed.SLOW)

        # Set current speed value from profile
        current_speed = self.result_haptic_speed
        speed_index = self.haptic_speed_combo.findData(current_speed)
        if speed_index >= 0:
            self.haptic_speed_combo.setCurrentIndex(speed_index)

        haptic_layout.addRow("Speed:", self.haptic_speed_combo)

        haptic_info = QLabel(
            "Strength controls vibration intensity. Speed controls how spaced out\n"
            "the detents feel when rotating dials (slower = fewer clicks per turn).\n"
            "Only available on TourBox Elite. Neo models do not have haptic motors."
        )
        haptic_info.setWordWrap(True)
        haptic_info.setStyleSheet(muted_label_style(10))
        haptic_layout.addRow("", haptic_info)

        layout.addWidget(haptic_group)

        # Double-click section
        double_click_group = QGroupBox("Double-Click")
        double_click_layout = QFormLayout(double_click_group)

        # Slider + SpinBox combo (synced) for precise control
        timeout_widget_layout = QHBoxLayout()
        timeout_widget_layout.setContentsMargins(0, 0, 0, 0)

        self.double_click_timeout_slider = QSlider(Qt.Horizontal)
        self.double_click_timeout_slider.setRange(50, 500)   # 50ms to 500ms
        self.double_click_timeout_slider.setSingleStep(25)   # Arrow keys = 25ms
        self.double_click_timeout_slider.setPageStep(50)     # Page up/down = 50ms
        self.double_click_timeout_slider.setTickInterval(50)
        self.double_click_timeout_slider.setTickPosition(QSlider.TicksBelow)

        self.double_click_timeout_spin = QSpinBox()
        self.double_click_timeout_spin.setRange(50, 500)
        self.double_click_timeout_spin.setSuffix(" ms")
        self.double_click_timeout_spin.setSingleStep(1)      # Precise 1ms adjustment
        self.double_click_timeout_spin.setFixedWidth(80)

        # Sync slider and spinbox bidirectionally
        self.double_click_timeout_slider.valueChanged.connect(self.double_click_timeout_spin.setValue)
        self.double_click_timeout_spin.valueChanged.connect(self.double_click_timeout_slider.setValue)

        # Set initial value (clamp to valid range)
        current_timeout = max(50, min(500, self.result_double_click_timeout))
        self.double_click_timeout_spin.setValue(current_timeout)

        timeout_widget_layout.addWidget(self.double_click_timeout_slider, 1)
        timeout_widget_layout.addWidget(self.double_click_timeout_spin)

        double_click_layout.addRow("Timeout:", timeout_widget_layout)

        double_click_info = QLabel(
            "Time window for detecting double-press actions.\n"
            "Shorter = tighter timing, less accidental triggers.\n"
            "Longer = more forgiving, easier to hit."
        )
        double_click_info.setWordWrap(True)
        double_click_info.setStyleSheet(muted_label_style(10))
        double_click_layout.addRow("", double_click_info)

        layout.addWidget(double_click_group)

        # Modifier delay section
        modifier_delay_group = QGroupBox("Modifier Key Delay")
        modifier_delay_layout = QFormLayout(modifier_delay_group)

        # Override checkbox + spinbox
        override_layout = QHBoxLayout()
        override_layout.setContentsMargins(0, 0, 0, 0)

        self.modifier_delay_override_checkbox = QCheckBox("Override global setting")
        self.modifier_delay_override_checkbox.stateChanged.connect(self._on_modifier_delay_override_changed)
        override_layout.addWidget(self.modifier_delay_override_checkbox)

        self.modifier_delay_spin = QSpinBox()
        self.modifier_delay_spin.setRange(0, 100)
        self.modifier_delay_spin.setSuffix(" ms")
        self.modifier_delay_spin.setSingleStep(5)
        self.modifier_delay_spin.setFixedWidth(80)

        # Initialize from profile
        if self.result_modifier_delay is not None:
            self.modifier_delay_override_checkbox.setChecked(True)
            self.modifier_delay_spin.setValue(self.result_modifier_delay)
            self.modifier_delay_spin.setEnabled(True)
        else:
            self.modifier_delay_override_checkbox.setChecked(False)
            self.modifier_delay_spin.setValue(0)
            self.modifier_delay_spin.setEnabled(False)

        override_layout.addWidget(self.modifier_delay_spin)

        modifier_delay_layout.addRow(override_layout)

        modifier_delay_info = QLabel(
            "Delay between modifier keys (Ctrl/Shift/Alt) and other keys in combos.\n"
            "Some apps (e.g. GIMP) need 20-50ms to recognize key combinations.\n"
            "When unchecked, uses the global setting from config.conf [device] section."
        )
        modifier_delay_info.setWordWrap(True)
        modifier_delay_info.setStyleSheet(muted_label_style(10))
        modifier_delay_layout.addRow("", modifier_delay_info)

        layout.addWidget(modifier_delay_group)

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
                self.window_monitor = WindowMonitor()
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

    def _on_modifier_delay_override_changed(self, state):
        """Handle modifier delay override checkbox state change"""
        self.modifier_delay_spin.setEnabled(state == Qt.Checked.value)

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
        self.result_haptic_speed = self.haptic_speed_combo.currentData()
        self.result_double_click_timeout = self.double_click_timeout_spin.value()
        if self.modifier_delay_override_checkbox.isChecked():
            self.result_modifier_delay = self.modifier_delay_spin.value()
        else:
            self.result_modifier_delay = None

        # Accept the dialog
        self.accept()

    def get_results(self):
        """Get the edited profile settings

        Returns:
            Tuple of (name, app_id, window_class, haptic_strength, haptic_speed,
                      double_click_timeout, modifier_delay)
        """
        return (
            self.result_profile_name,
            self.result_app_id,
            self.result_window_class,
            self.result_haptic_strength,
            self.result_haptic_speed,
            self.result_double_click_timeout,
            self.result_modifier_delay
        )
