#!/usr/bin/env python3
"""Profile manager widget

Displays list of profiles and allows selection, creation, and deletion.
"""

import logging
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QMessageBox, QInputDialog, QDialog, QHeaderView
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

# Import from existing driver code
from tourboxelite.config_loader import Profile
from tourboxelite.haptic import HapticConfig

# Import GUI dialog
from .profile_settings_dialog import ProfileSettingsDialog

# Import config writer for deletion
from .config_writer import delete_profile

# Import UI constants
from tourboxelite.gui.ui_constants import TABLE_ROW_HEIGHT_MULTIPLIER

logger = logging.getLogger(__name__)


class ProfileManager(QWidget):
    """Widget for managing TourBox profiles"""

    # Signals
    profile_selected = Signal(Profile)  # Emitted when user selects a profile
    profiles_changed = Signal()  # Emitted when profiles list changes
    profiles_reset = Signal(Profile)  # Emitted when profiles reloaded from config (clears modified state)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.profiles: List[Profile] = []
        self.current_profile: Optional[Profile] = None
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Profiles")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Profile table (2 columns: Name, Window)
        self.profile_table = QTableWidget()
        self.profile_table.setColumnCount(2)
        self.profile_table.setHorizontalHeaderLabels(["Name", "Window"])
        self.profile_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.profile_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.profile_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.profile_table.setSelectionMode(QTableWidget.SingleSelection)
        self.profile_table.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only
        self.profile_table.verticalHeader().setVisible(False)  # Hide row numbers
        # Set row height based on font metrics for proper scaling
        fm = self.profile_table.fontMetrics()
        self.profile_table.verticalHeader().setDefaultSectionSize(int(fm.lineSpacing() * TABLE_ROW_HEIGHT_MULTIPLIER))
        self.profile_table.currentCellChanged.connect(self._on_profile_selection_changed)
        layout.addWidget(self.profile_table)

        # Buttons
        button_layout = QHBoxLayout()

        self.new_button = QPushButton("+")
        self.new_button.setToolTip("Create new profile")
        self.new_button.clicked.connect(self._on_new_profile)
        button_layout.addWidget(self.new_button)

        self.edit_button = QPushButton("⚙")
        self.edit_button.setToolTip("Edit profile settings (window matching)")
        self.edit_button.clicked.connect(self._on_edit_profile)
        button_layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("-")
        self.delete_button.setToolTip("Delete selected profile")
        self.delete_button.clicked.connect(self._on_delete_profile)
        button_layout.addWidget(self.delete_button)

        layout.addLayout(button_layout)

    def load_profiles(self, profiles: List[Profile]):
        """Load and display profiles

        Args:
            profiles: List of Profile objects from config file
        """
        self.profiles = profiles
        self.profile_table.setRowCount(0)

        # Filter out the TourBox GUI meta-configuration profile
        # (it's for internal use and shouldn't be edited by users)
        displayed_profiles = [p for p in profiles if p.name != 'TourBox GUI']

        for row, profile in enumerate(displayed_profiles):
            self.profile_table.insertRow(row)

            # Column 0: Profile name
            name_item = QTableWidgetItem(profile.name)
            name_item.setData(Qt.UserRole, profile)  # Store profile object
            self.profile_table.setItem(row, 0, name_item)

            # Column 1: Window matching info
            match_text = self._get_window_match_text(profile)
            match_item = QTableWidgetItem(match_text)
            match_item.setData(Qt.UserRole, profile)  # Store profile object here too
            self.profile_table.setItem(row, 1, match_item)

            # Select default profile by default
            if profile.name == 'default':
                self.profile_table.selectRow(row)
                self.current_profile = profile
                self.profile_selected.emit(profile)

        logger.info(f"Loaded {len(displayed_profiles)} profiles (filtered out {len(profiles) - len(displayed_profiles)} internal profiles)")

        # Enable/disable delete button
        self._update_button_states()

    def get_selected_profile(self) -> Optional[Profile]:
        """Get the currently selected profile

        Returns:
            Selected Profile object, or None if no selection
        """
        return self.current_profile

    def reselect_current_profile(self):
        """Reselect the current profile in the list (used to cancel profile switch)"""
        if not self.current_profile:
            return

        # Find and select the current profile in the table
        for row in range(self.profile_table.rowCount()):
            name_item = self.profile_table.item(row, 0)
            profile = name_item.data(Qt.UserRole)
            if profile == self.current_profile:
                # Block signals to prevent triggering selection change
                self.profile_table.blockSignals(True)
                self.profile_table.selectRow(row)
                self.profile_table.blockSignals(False)
                logger.debug(f"Reselected profile: {self.current_profile.name}")
                break

    def _reload_profile_list(self):
        """Reload the profile list display (after editing profile settings)"""
        # Remember current selection
        current_profile = self.current_profile

        # Block signals to prevent triggering selection events
        self.profile_table.blockSignals(True)

        # Clear and rebuild table
        self.profile_table.setRowCount(0)
        for row, profile in enumerate(self.profiles):
            self.profile_table.insertRow(row)

            # Column 0: Profile name
            name_item = QTableWidgetItem(profile.name)
            name_item.setData(Qt.UserRole, profile)
            self.profile_table.setItem(row, 0, name_item)

            # Column 1: Window matching info
            match_text = self._get_window_match_text(profile)
            match_item = QTableWidgetItem(match_text)
            match_item.setData(Qt.UserRole, profile)
            self.profile_table.setItem(row, 1, match_item)

            # Reselect the current profile
            if profile == current_profile:
                self.profile_table.selectRow(row)

        # Re-enable signals
        self.profile_table.blockSignals(False)

        logger.debug("Profile list reloaded")

    def _on_profile_selection_changed(self, currentRow, currentColumn, previousRow, previousColumn):
        """Handle profile selection change (mouse click or keyboard navigation)"""
        if currentRow < 0:
            return

        # Get profile from the name column (column 0)
        name_item = self.profile_table.item(currentRow, 0)
        if name_item is None:
            return

        profile = name_item.data(Qt.UserRole)
        self.current_profile = profile
        logger.info(f"Selected profile: {profile.name}")
        self.profile_selected.emit(profile)
        self._update_button_states()

    def _on_edit_profile(self):
        """Handle edit profile button click"""
        if not self.current_profile:
            return

        logger.info(f"Edit profile requested: {self.current_profile.name}")

        # Open profile settings dialog
        dialog = ProfileSettingsDialog(self.current_profile, self, is_new=False)
        if dialog.exec() == QDialog.Accepted:
            # Get results
            name, app_id, window_class, haptic_strength = dialog.get_results()

            # Update profile object
            old_name = self.current_profile.name
            self.current_profile.name = name
            self.current_profile.app_id = app_id if app_id else None
            self.current_profile.window_class = window_class if window_class else None
            self.current_profile.window_title = None  # No longer used

            # Update haptic config (Phase 1: global setting)
            self.current_profile.haptic_config.set_global(haptic_strength)

            logger.info(f"Profile updated: {self.current_profile}")
            logger.info(f"  Haptic: {haptic_strength}")

            # Reload the list to show updated info
            self._reload_profile_list()

            # Emit signal that profiles changed (so main window can mark as modified)
            self.profiles_changed.emit()

            # Show success message if name changed
            if name != old_name:
                QMessageBox.information(
                    self,
                    "Profile Updated",
                    f"Profile renamed from '{old_name}' to '{name}'.\n\n"
                    f"Remember to save to apply changes."
                )

    def _on_new_profile(self):
        """Handle new profile button click"""
        logger.info("New profile requested")

        # Ask for profile name
        name, ok = QInputDialog.getText(
            self,
            "New Profile",
            "Enter a name for the new profile:",
            text="new_profile"
        )

        if not ok or not name.strip():
            return

        name = name.strip()

        # Validate name
        if ':' in name or '[' in name or ']' in name:
            QMessageBox.warning(
                self,
                "Invalid Name",
                "Profile name cannot contain ':', '[', or ']' characters."
            )
            return

        # Check if name already exists
        for profile in self.profiles:
            if profile.name == name:
                QMessageBox.warning(
                    self,
                    "Name Exists",
                    f"A profile named '{name}' already exists.\nPlease choose a different name."
                )
                return

        # Ask if they want to copy current profile or start empty
        reply = QMessageBox.question(
            self,
            "Copy Profile?",
            f"Do you want to copy settings from the current profile ('{self.current_profile.name}')?\n\n"
            "Click 'Yes' to copy all button mappings.\n"
            "Click 'No' to start with empty mappings.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        # Create new profile
        if reply == QMessageBox.Yes:
            # Copy from current profile
            new_profile = Profile(
                name=name,
                window_class=None,
                window_title=None,
                app_id=None,
                mapping=self.current_profile.mapping.copy() if self.current_profile.mapping else {},
                capabilities=self.current_profile.capabilities.copy() if self.current_profile.capabilities else {}
            )
            logger.info(f"Created new profile '{name}' based on '{self.current_profile.name}'")
        else:
            # Start with empty mappings
            new_profile = Profile(
                name=name,
                window_class=None,
                window_title=None,
                app_id=None,
                mapping={},
                capabilities={}
            )
            logger.info(f"Created new empty profile '{name}'")

        # Add to profiles list
        self.profiles.append(new_profile)

        # Reload the list
        self._reload_profile_list()

        # Select the new profile
        for row in range(self.profile_table.rowCount()):
            name_item = self.profile_table.item(row, 0)
            profile = name_item.data(Qt.UserRole)
            if profile.name == name:
                self.profile_table.selectRow(row)
                break

        # Emit signal that profiles changed
        self.profiles_changed.emit()

        # Ask if they want to set window matching now
        reply = QMessageBox.question(
            self,
            "Window Matching",
            f"Profile '{name}' created successfully!\n\n"
            "Would you like to set up window matching rules now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._on_edit_profile()

    def _on_delete_profile(self):
        """Handle delete profile button click"""
        if not self.current_profile:
            return

        # Prevent deleting default profile
        if self.current_profile.name == 'default':
            QMessageBox.warning(
                self,
                "Cannot Delete",
                "The default profile cannot be deleted."
            )
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f"Are you sure you want to delete profile '{self.current_profile.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            logger.info(f"Deleting profile: {self.current_profile.name}")

            profile_to_delete = self.current_profile

            # Check if profile exists in config file (may be new, unsaved profile)
            from .config_writer import profile_exists_in_config
            profile_was_in_config = profile_exists_in_config(profile_to_delete.name)

            if profile_was_in_config:
                # Delete from config file
                success = delete_profile(profile_to_delete.name)
            else:
                # Profile doesn't exist in config yet (new, unsaved)
                logger.info(f"Profile '{profile_to_delete.name}' not in config, removing from memory only")
                success = True

            if success:
                if profile_was_in_config:
                    # Profile was saved - deletion is already saved to config file by delete_profile()
                    # Remove from memory
                    self.profiles.remove(profile_to_delete)

                    # Select default profile
                    default_profile = None
                    for i, profile in enumerate(self.profiles):
                        if profile.name == 'default':
                            self.current_profile = profile
                            default_profile = profile
                            break

                    # Reload the list
                    self._reload_profile_list()

                    # Emit profiles_reset to update main window without unsaved changes check
                    # Deletion was already saved, no need to prompt
                    if default_profile:
                        self.profiles_reset.emit(default_profile)
                else:
                    # Profile was never saved - reload from config to reset state
                    from tourboxelite.config_loader import load_profiles
                    self.profiles = load_profiles()

                    # Select default profile
                    for profile in self.profiles:
                        if profile.name == 'default':
                            self.current_profile = profile
                            break

                    # Reload the list
                    self._reload_profile_list()

                    # Emit reset signal to clear modified state without unsaved changes check
                    self.profiles_reset.emit(self.current_profile)

                # Show success message
                QMessageBox.information(
                    self,
                    "Profile Deleted",
                    f"Profile '{profile_to_delete.name}' has been deleted successfully."
                )

                logger.info(f"Profile deleted: {profile_to_delete.name}")
            else:
                QMessageBox.critical(
                    self,
                    "Deletion Failed",
                    f"Failed to delete profile '{profile_to_delete.name}'.\n\n"
                    "Check the logs for details."
                )

    def _get_window_match_text(self, profile: Profile) -> str:
        """Get window matching display text for a profile

        Args:
            profile: Profile object

        Returns:
            Formatted window matching text
        """
        # Leave default profile's window column blank
        if profile.name == 'default':
            return ""

        # Prefer window_class, but show which one is being used
        if profile.window_class:
            return f"class: {profile.window_class}"
        elif profile.app_id:
            return f"app_id: {profile.app_id}"
        else:
            return ""

    def _update_button_states(self):
        """Update button enabled/disabled states"""
        has_selection = self.current_profile is not None
        is_default = has_selection and self.current_profile.name == 'default'

        # Can't edit default profile (no point in setting window matching for it)
        self.edit_button.setEnabled(has_selection and not is_default)

        # Can't delete if nothing selected or if default profile
        self.delete_button.setEnabled(has_selection and not is_default)
