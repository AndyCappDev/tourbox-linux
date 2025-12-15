#!/usr/bin/env python3
"""Import conflict dialog for TourBox Elite Configuration GUI

Shown when importing a profile with a name that conflicts with an existing profile.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QButtonGroup, QFrame
)
from PySide6.QtCore import Qt


class ImportConflictDialog(QDialog):
    """Dialog for handling profile import name conflicts"""

    REPLACE = 0
    RENAME = 1
    CANCEL = 2

    def __init__(self, existing_name: str, parent=None):
        """Initialize the dialog

        Args:
            existing_name: Name of the existing profile that conflicts
            parent: Parent widget
        """
        super().__init__(parent)
        self.existing_name = existing_name
        self.result_action = self.CANCEL
        self.new_name = ""

        self.setWindowTitle("Profile Name Conflict")
        self.setMinimumWidth(400)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Warning message
        warning_label = QLabel(
            f"A profile named <b>{self.existing_name}</b> already exists.\n\n"
            "What would you like to do?"
        )
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # Radio button group
        self.button_group = QButtonGroup(self)

        # Option 1: Replace existing
        self.replace_radio = QRadioButton("Replace existing profile")
        self.replace_radio.setToolTip(
            f"Delete the existing '{self.existing_name}' profile and import the new one"
        )
        self.button_group.addButton(self.replace_radio, self.REPLACE)
        layout.addWidget(self.replace_radio)

        # Option 2: Rename
        rename_layout = QHBoxLayout()
        self.rename_radio = QRadioButton("Import with new name:")
        self.rename_radio.setChecked(True)  # Default selection
        self.button_group.addButton(self.rename_radio, self.RENAME)
        rename_layout.addWidget(self.rename_radio)

        self.name_edit = QLineEdit()
        self.name_edit.setText(f"{self.existing_name}_imported")
        self.name_edit.setPlaceholderText("Enter new profile name")
        rename_layout.addWidget(self.name_edit)
        layout.addLayout(rename_layout)

        # Connect radio button to enable/disable name edit
        self.rename_radio.toggled.connect(self._on_rename_toggled)
        self.replace_radio.toggled.connect(lambda: self.name_edit.setEnabled(False))

        # Spacer
        layout.addSpacing(10)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_btn)

        self.ok_btn = QPushButton("Import")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        button_layout.addWidget(self.ok_btn)

        layout.addLayout(button_layout)

    def _on_rename_toggled(self, checked: bool):
        """Handle rename radio button toggle"""
        self.name_edit.setEnabled(checked)
        if checked:
            self.name_edit.setFocus()
            self.name_edit.selectAll()

    def _on_ok(self):
        """Handle OK button click"""
        selected_id = self.button_group.checkedId()

        if selected_id == self.RENAME:
            # Validate new name
            new_name = self.name_edit.text().strip()
            if not new_name:
                self.name_edit.setFocus()
                return

            # Check for invalid characters
            if ':' in new_name or '[' in new_name or ']' in new_name:
                self.name_edit.setFocus()
                self.name_edit.selectAll()
                return

            self.new_name = new_name

        self.result_action = selected_id
        self.accept()

    def _on_cancel(self):
        """Handle Cancel button click"""
        self.result_action = self.CANCEL
        self.reject()

    def get_result(self) -> tuple:
        """Get the dialog result

        Returns:
            Tuple of (action, new_name)
            - action: REPLACE, RENAME, or CANCEL
            - new_name: New profile name if RENAME, empty string otherwise
        """
        return self.result_action, self.new_name
