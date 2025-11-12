#!/usr/bin/env python3
"""Control editor widget

Allows editing of individual control actions with modifiers, keys, and action types.
"""

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QGroupBox, QButtonGroup, QTextEdit,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QDialogButtonBox
)
from PySide6.QtCore import Signal, Qt
from evdev import ecodes as e
from tourboxelite.config_loader import VALID_MODIFIER_BUTTONS
from tourboxelite.gui.ui_constants import TABLE_ROW_HEIGHT_MULTIPLIER, TEXT_EDIT_HEIGHT_MULTIPLIER

logger = logging.getLogger(__name__)

# Character to keycode mapping for symbols and special characters
CHAR_TO_KEYCODE = {
    # Symbols (both shifted and unshifted)
    '=': 'EQUAL',
    '+': 'EQUAL',  # Shift+=
    '-': 'MINUS',
    '_': 'MINUS',  # Shift+-
    '[': 'LEFTBRACE',
    '{': 'LEFTBRACE',  # Shift+[
    ']': 'RIGHTBRACE',
    '}': 'RIGHTBRACE',  # Shift+]
    ';': 'SEMICOLON',
    ':': 'SEMICOLON',  # Shift+;
    "'": 'APOSTROPHE',
    '"': 'APOSTROPHE',  # Shift+'
    ',': 'COMMA',
    '<': 'COMMA',  # Shift+,
    '.': 'DOT',
    '>': 'DOT',  # Shift+.
    '/': 'SLASH',
    '?': 'SLASH',  # Shift+/
    '\\': 'BACKSLASH',
    '|': 'BACKSLASH',  # Shift+\
    '`': 'GRAVE',
    '~': 'GRAVE',  # Shift+`
    '1': '1',
    '!': '1',  # Shift+1
    '2': '2',
    '@': '2',  # Shift+2
    '3': '3',
    '#': '3',  # Shift+3
    '4': '4',
    '$': '4',  # Shift+4
    '5': '5',
    '%': '5',  # Shift+5
    '6': '6',
    '^': '6',  # Shift+6
    '7': '7',
    '&': '7',  # Shift+7
    '8': '8',
    '*': '8',  # Shift+8
    '9': '9',
    '(': '9',  # Shift+9
    '0': '0',
    ')': '0',  # Shift+0
}

# Special keys that can't be reliably typed
SPECIAL_KEYS = {
    'None': None,
    '--- Control Keys ---': None,
    'Enter': e.KEY_ENTER,
    'Escape': e.KEY_ESC,
    'Tab': e.KEY_TAB,
    'Space': e.KEY_SPACE,
    'Backspace': e.KEY_BACKSPACE,
    'Delete': e.KEY_DELETE,
    'Insert': e.KEY_INSERT,
    'Context Menu': e.KEY_CONTEXT_MENU,
    '--- Arrow Keys ---': None,
    'Up': e.KEY_UP,
    'Down': e.KEY_DOWN,
    'Left': e.KEY_LEFT,
    'Right': e.KEY_RIGHT,
    '--- Navigation ---': None,
    'Home': e.KEY_HOME,
    'End': e.KEY_END,
    'Page Up': e.KEY_PAGEUP,
    'Page Down': e.KEY_PAGEDOWN,
    '--- Zoom Keys ---': None,
    'Zoom Reset': e.KEY_ZOOMRESET,
    'Zoom In': e.KEY_ZOOMIN,
    'Zoom Out': e.KEY_ZOOMOUT,
    '--- Function Keys ---': None,
    'F1': e.KEY_F1, 'F2': e.KEY_F2, 'F3': e.KEY_F3, 'F4': e.KEY_F4,
    'F5': e.KEY_F5, 'F6': e.KEY_F6, 'F7': e.KEY_F7, 'F8': e.KEY_F8,
    'F9': e.KEY_F9, 'F10': e.KEY_F10, 'F11': e.KEY_F11, 'F12': e.KEY_F12,
}

# All available controls
ALL_CONTROLS = [
    'side', 'top', 'tall', 'short',
    'c1', 'c2', 'tour',
    'dpad_up', 'dpad_down', 'dpad_left', 'dpad_right',
    'scroll_up', 'scroll_down', 'scroll_click',
    'knob_cw', 'knob_ccw', 'knob_click',
    'dial_cw', 'dial_ccw', 'dial_click',
]


class ComboConfigDialog(QDialog):
    """Dialog for configuring a modifier combination"""

    def __init__(self, parent=None, modifier_name: str = "", control_name: str = "",
                 action: str = "", comment: str = "", exclude_controls: set = None):
        super().__init__(parent)
        self.setWindowTitle("Configure Modifier Combination")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel(f"Configure combination for modifier: {modifier_name}")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        # Control selection
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("Control:"))
        self.control_combo = QComboBox()
        self.control_combo.addItem("(select control)")
        # Set minimum height based on font metrics
        fm_control = self.control_combo.fontMetrics()
        self.control_combo.setMinimumHeight(int(fm_control.lineSpacing() * TEXT_EDIT_HEIGHT_MULTIPLIER))

        # Prepare exclusion set (modifier itself + already used controls)
        if exclude_controls is None:
            exclude_controls = set()
        exclude_set = exclude_controls | {modifier_name}

        for control in ALL_CONTROLS:
            # Don't allow the modifier itself or already-used controls
            if control not in exclude_set:
                self.control_combo.addItem(control)

        if control_name:
            idx = self.control_combo.findText(control_name)
            if idx >= 0:
                self.control_combo.setCurrentIndex(idx)
        control_layout.addWidget(self.control_combo, stretch=1)
        layout.addLayout(control_layout)

        # Action type selection
        action_type_layout = QHBoxLayout()
        action_type_layout.addWidget(QLabel("Action Type:"))
        self.action_type_combo = QComboBox()
        self.action_type_combo.addItems(["Keyboard", "Mouse Wheel", "None"])
        # Set minimum height based on font metrics
        fm_action = self.action_type_combo.fontMetrics()
        self.action_type_combo.setMinimumHeight(int(fm_action.lineSpacing() * TEXT_EDIT_HEIGHT_MULTIPLIER))
        self.action_type_combo.currentTextChanged.connect(self._on_action_type_changed)
        action_type_layout.addWidget(self.action_type_combo)
        action_type_layout.addStretch()
        layout.addLayout(action_type_layout)

        # Keyboard action group
        self.keyboard_group = QGroupBox("Keyboard Action")
        keyboard_layout = QVBoxLayout(self.keyboard_group)

        # Modifiers
        mod_label = QLabel("Modifiers:")
        keyboard_layout.addWidget(mod_label)

        # Calculate minimum height for buttons and input fields based on font metrics
        fm = self.keyboard_group.fontMetrics()
        button_height = int(fm.lineSpacing() * TEXT_EDIT_HEIGHT_MULTIPLIER)

        mod_layout = QHBoxLayout()
        self.ctrl_btn = QPushButton("Ctrl")
        self.ctrl_btn.setCheckable(True)
        self.ctrl_btn.setMaximumWidth(80)
        self.ctrl_btn.setMinimumHeight(button_height)
        mod_layout.addWidget(self.ctrl_btn)

        self.alt_btn = QPushButton("Alt")
        self.alt_btn.setCheckable(True)
        self.alt_btn.setMaximumWidth(80)
        self.alt_btn.setMinimumHeight(button_height)
        mod_layout.addWidget(self.alt_btn)

        self.shift_btn = QPushButton("Shift")
        self.shift_btn.setCheckable(True)
        self.shift_btn.setMaximumWidth(80)
        self.shift_btn.setMinimumHeight(button_height)
        mod_layout.addWidget(self.shift_btn)

        self.super_btn = QPushButton("Super")
        self.super_btn.setCheckable(True)
        self.super_btn.setMaximumWidth(80)
        self.super_btn.setMinimumHeight(button_height)
        mod_layout.addWidget(self.super_btn)

        mod_layout.addStretch()
        keyboard_layout.addLayout(mod_layout)

        # Add spacing between modifiers and key input
        keyboard_layout.addSpacing(15)

        # Key input
        from PySide6.QtCore import Qt
        key_layout = QHBoxLayout()
        key_layout.setAlignment(Qt.AlignVCenter)  # Align items vertically in center
        key_label = QLabel("Key:")
        key_layout.addWidget(key_label)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Type a character (a-z, 0-9, symbols)")
        self.key_input.setMaxLength(1)
        self.key_input.setMaximumWidth(200)
        self.key_input.setMinimumHeight(button_height)
        self.key_input.textChanged.connect(self._on_key_input_changed)
        key_layout.addWidget(self.key_input)

        or_label = QLabel("or")
        key_layout.addWidget(or_label)

        self.special_key_combo = QComboBox()
        for key_name in SPECIAL_KEYS.keys():
            self.special_key_combo.addItem(key_name)
            if SPECIAL_KEYS[key_name] is None:
                idx = self.special_key_combo.count() - 1
                self.special_key_combo.model().item(idx).setEnabled(False)
        self.special_key_combo.setMaximumWidth(150)
        self.special_key_combo.setMinimumHeight(button_height)
        self.special_key_combo.currentTextChanged.connect(self._on_special_key_changed)
        key_layout.addWidget(self.special_key_combo)

        key_layout.addStretch()
        keyboard_layout.addLayout(key_layout)

        layout.addWidget(self.keyboard_group)

        # Mouse wheel action group
        self.mouse_group = QGroupBox("Mouse Wheel Action")
        self.mouse_group.setMinimumHeight(80)  # Ensure enough space for controls
        mouse_layout = QVBoxLayout(self.mouse_group)

        # Calculate minimum height for combo box based on font metrics
        fm_mouse = self.mouse_group.fontMetrics()
        combo_height = int(fm_mouse.lineSpacing() * TEXT_EDIT_HEIGHT_MULTIPLIER)

        mouse_dir_layout = QHBoxLayout()
        mouse_dir_layout.addWidget(QLabel("Direction:"))
        self.mouse_direction_combo = QComboBox()
        self.mouse_direction_combo.addItems([
            "Vertical Up",
            "Vertical Down",
            "Horizontal Left",
            "Horizontal Right"
        ])
        self.mouse_direction_combo.setMinimumHeight(combo_height)
        mouse_dir_layout.addWidget(self.mouse_direction_combo)
        mouse_dir_layout.addStretch()
        mouse_layout.addLayout(mouse_dir_layout)

        layout.addWidget(self.mouse_group)
        self.mouse_group.hide()  # Hidden by default

        # Comment field
        comment_label = QLabel("Comment:")
        layout.addWidget(comment_label)
        self.comment_text = QTextEdit()
        self.comment_text.setPlaceholderText("Add notes about this combination...")
        # Set height to approximately 1 line based on font metrics
        fm = self.comment_text.fontMetrics()
        self.comment_text.setMaximumHeight(int(fm.lineSpacing() * TEXT_EDIT_HEIGHT_MULTIPLIER))
        self.comment_text.setPlainText(comment)
        layout.addWidget(self.comment_text)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Parse and populate if editing existing combo
        if action:
            self._parse_and_populate(action)

    def _on_action_type_changed(self, action_type: str):
        """Handle action type change"""
        if action_type == "Keyboard":
            self.keyboard_group.show()
            self.mouse_group.hide()
        elif action_type == "Mouse Wheel":
            self.keyboard_group.hide()
            self.mouse_group.show()
        else:  # None
            self.keyboard_group.hide()
            self.mouse_group.hide()

    def _on_key_input_changed(self, text: str):
        """Handle key input text change - clear special key dropdown"""
        if text:
            self.special_key_combo.setCurrentIndex(0)

    def _on_special_key_changed(self, key_name: str):
        """Handle special key dropdown change - clear text input"""
        if key_name and key_name != "None" and SPECIAL_KEYS.get(key_name) is not None:
            self.key_input.clear()

    def _parse_and_populate(self, action_str: str):
        """Parse action string and populate UI fields"""
        if not action_str or action_str == "none":
            self.action_type_combo.setCurrentText("None")
            return

        # Check if it's a mouse wheel action
        if action_str.startswith("REL_WHEEL:") or action_str.startswith("REL_HWHEEL:"):
            self.action_type_combo.setCurrentText("Mouse Wheel")
            if action_str.startswith("REL_WHEEL:"):
                value = int(action_str.split(":")[1])
                if value > 0:
                    self.mouse_direction_combo.setCurrentText("Vertical Up")
                else:
                    self.mouse_direction_combo.setCurrentText("Vertical Down")
            else:
                value = int(action_str.split(":")[1])
                if value > 0:
                    self.mouse_direction_combo.setCurrentText("Horizontal Right")
                else:
                    self.mouse_direction_combo.setCurrentText("Horizontal Left")
            return

        # It's a keyboard action
        self.action_type_combo.setCurrentText("Keyboard")

        # Parse key combination
        parts = action_str.split("+")
        for part in parts:
            part = part.strip()
            part_upper = part.upper()
            if "CTRL" in part_upper:
                self.ctrl_btn.setChecked(True)
            elif "ALT" in part_upper:
                self.alt_btn.setChecked(True)
            elif "SHIFT" in part_upper:
                self.shift_btn.setChecked(True)
            elif "META" in part_upper or "SUPER" in part_upper:
                self.super_btn.setChecked(True)
            else:
                # It's the actual key
                # Strip KEY_ prefix if present
                key_part = part
                if key_part.startswith("KEY_"):
                    key_part = key_part[4:]  # Remove "KEY_" prefix

                if len(key_part) == 1:
                    self.key_input.setText(key_part.lower())
                else:
                    # Try to match in special keys dropdown
                    for i in range(self.special_key_combo.count()):
                        item_text = self.special_key_combo.itemText(i)
                        if item_text.lower() == key_part.lower():
                            self.special_key_combo.setCurrentIndex(i)
                            break

    def get_control(self) -> str:
        """Get selected control name"""
        control = self.control_combo.currentText()
        return control if control != "(select control)" else ""

    def get_action(self) -> str:
        """Get configured action string"""
        action_type = self.action_type_combo.currentText()

        if action_type == "None":
            return "none"

        if action_type == "Mouse Wheel":
            direction = self.mouse_direction_combo.currentText()
            if direction == "Vertical Up":
                return "REL_WHEEL:1"
            elif direction == "Vertical Down":
                return "REL_WHEEL:-1"
            elif direction == "Horizontal Left":
                return "REL_HWHEEL:-1"
            elif direction == "Horizontal Right":
                return "REL_HWHEEL:1"

        # Keyboard action
        parts = []

        # Add modifiers
        if self.ctrl_btn.isChecked():
            parts.append("KEY_LEFTCTRL")
        if self.alt_btn.isChecked():
            parts.append("KEY_LEFTALT")
        if self.shift_btn.isChecked():
            parts.append("KEY_LEFTSHIFT")
        if self.super_btn.isChecked():
            parts.append("KEY_LEFTMETA")

        # Add key
        if self.key_input.text():
            char = self.key_input.text()
            if char in CHAR_TO_KEYCODE:
                key_name = CHAR_TO_KEYCODE[char]
                parts.append(f"KEY_{key_name}")
            else:
                parts.append(f"KEY_{char.upper()}")
        elif self.special_key_combo.currentText() != "None":
            key_name = self.special_key_combo.currentText()
            if SPECIAL_KEYS.get(key_name):
                for name, code in e.__dict__.items():
                    if name.startswith('KEY_') and code == SPECIAL_KEYS[key_name]:
                        parts.append(name)
                        break

        return "+".join(parts) if parts else "none"

    def get_comment(self) -> str:
        """Get comment text"""
        return self.comment_text.toPlainText().strip()


class ControlEditor(QWidget):
    """Widget for editing a control's action"""

    # Signals emitted when user makes changes
    action_changed = Signal(str, str)  # control_name, action_string
    comment_changed = Signal(str, str)  # control_name, comment
    modifier_config_changed = Signal(str, dict)  # control_name, modifier_config
    combo_selected = Signal(str)  # combo_control_name (control selected from Modifier Combinations table)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_control = None
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)

        # Header
        self.header_label = QLabel("Edit Control")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.header_label)

        # Control name display
        self.control_label = QLabel("No control selected")
        self.control_label.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(self.control_label)

        # Action type selection
        action_type_layout = QHBoxLayout()
        action_type_layout.addWidget(QLabel("Action Type:"))
        self.action_type_combo = QComboBox()
        self.action_type_combo.addItems(["Keyboard", "Mouse Wheel", "None"])
        # Set minimum height based on font metrics
        fm_action = self.action_type_combo.fontMetrics()
        self.action_type_combo.setMinimumHeight(int(fm_action.lineSpacing() * TEXT_EDIT_HEIGHT_MULTIPLIER))
        self.action_type_combo.currentTextChanged.connect(self._on_action_type_changed)
        action_type_layout.addWidget(self.action_type_combo)
        action_type_layout.addStretch()
        layout.addLayout(action_type_layout)

        # Keyboard action group
        self.keyboard_group = QGroupBox("Keyboard Action")
        self.keyboard_group.setMinimumHeight(140)  # Ensure enough space for controls with spacing
        keyboard_layout = QVBoxLayout(self.keyboard_group)

        # Modifiers
        mod_label = QLabel("Modifiers:")
        keyboard_layout.addWidget(mod_label)

        # Calculate minimum height for buttons and input fields based on font metrics
        fm = self.keyboard_group.fontMetrics()
        button_height = int(fm.lineSpacing() * TEXT_EDIT_HEIGHT_MULTIPLIER)

        mod_layout = QHBoxLayout()
        self.ctrl_btn = QPushButton("Ctrl")
        self.ctrl_btn.setCheckable(True)
        self.ctrl_btn.setMaximumWidth(80)
        self.ctrl_btn.setMinimumHeight(button_height)
        mod_layout.addWidget(self.ctrl_btn)

        self.alt_btn = QPushButton("Alt")
        self.alt_btn.setCheckable(True)
        self.alt_btn.setMaximumWidth(80)
        self.alt_btn.setMinimumHeight(button_height)
        mod_layout.addWidget(self.alt_btn)

        self.shift_btn = QPushButton("Shift")
        self.shift_btn.setCheckable(True)
        self.shift_btn.setMaximumWidth(80)
        self.shift_btn.setMinimumHeight(button_height)
        mod_layout.addWidget(self.shift_btn)

        self.super_btn = QPushButton("Super")
        self.super_btn.setCheckable(True)
        self.super_btn.setMaximumWidth(80)
        self.super_btn.setMinimumHeight(button_height)
        mod_layout.addWidget(self.super_btn)

        mod_layout.addStretch()
        keyboard_layout.addLayout(mod_layout)

        # Add spacing between modifiers and key input
        keyboard_layout.addSpacing(15)

        # Key input
        from PySide6.QtCore import Qt
        key_layout = QHBoxLayout()
        key_layout.setAlignment(Qt.AlignVCenter)  # Align items vertically in center
        key_label = QLabel("Key:")
        key_layout.addWidget(key_label)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Type a character (a-z, 0-9, symbols)")
        self.key_input.setMaxLength(1)
        self.key_input.setMaximumWidth(200)
        self.key_input.setMinimumHeight(button_height)
        self.key_input.textChanged.connect(self._on_key_input_changed)
        key_layout.addWidget(self.key_input)

        or_label = QLabel("or")
        key_layout.addWidget(or_label)

        self.special_key_combo = QComboBox()
        for key_name in SPECIAL_KEYS.keys():
            self.special_key_combo.addItem(key_name)
            # Disable separator items
            if SPECIAL_KEYS[key_name] is None:
                idx = self.special_key_combo.count() - 1
                self.special_key_combo.model().item(idx).setEnabled(False)
        self.special_key_combo.setMaximumWidth(150)
        self.special_key_combo.setMinimumHeight(button_height)
        self.special_key_combo.currentTextChanged.connect(self._on_special_key_changed)
        key_layout.addWidget(self.special_key_combo)

        key_layout.addStretch()
        keyboard_layout.addLayout(key_layout)

        layout.addWidget(self.keyboard_group)

        # Mouse wheel action group
        self.mouse_group = QGroupBox("Mouse Wheel Action")
        self.mouse_group.setMinimumHeight(80)  # Ensure enough space for controls
        mouse_layout = QVBoxLayout(self.mouse_group)

        # Calculate minimum height for combo box based on font metrics
        fm_mouse = self.mouse_group.fontMetrics()
        combo_height = int(fm_mouse.lineSpacing() * TEXT_EDIT_HEIGHT_MULTIPLIER)

        mouse_dir_layout = QHBoxLayout()
        mouse_dir_layout.addWidget(QLabel("Direction:"))
        self.mouse_direction_combo = QComboBox()
        self.mouse_direction_combo.addItems([
            "Vertical Up",
            "Vertical Down",
            "Horizontal Left",
            "Horizontal Right"
        ])
        self.mouse_direction_combo.setMinimumHeight(combo_height)
        mouse_dir_layout.addWidget(self.mouse_direction_combo)
        mouse_dir_layout.addStretch()
        mouse_layout.addLayout(mouse_dir_layout)

        layout.addWidget(self.mouse_group)
        self.mouse_group.hide()  # Hidden by default

        # Comment/Notes field (visible for non-modifier controls)
        self.comment_group = QGroupBox("Comment")
        comment_layout = QVBoxLayout(self.comment_group)

        self.comment_text = QTextEdit()
        self.comment_text.setPlaceholderText("Add notes or comments about this mapping...")
        # Set height to approximately 1 line based on font metrics
        fm = self.comment_text.fontMetrics()
        text_height = int(fm.lineSpacing() * TEXT_EDIT_HEIGHT_MULTIPLIER)
        self.comment_text.setMinimumHeight(text_height)
        self.comment_text.setMaximumHeight(text_height)
        comment_layout.addWidget(self.comment_text)

        # Set group box minimum height to accommodate text field plus margins
        self.comment_group.setMinimumHeight(text_height + 40)  # Text + title + margins

        layout.addWidget(self.comment_group)

        # Modifier Combinations section (only visible for physical buttons)
        # No groupbox wrapper - just the label, table, and button
        self.combos_label = QLabel("Modifier Combinations:")
        self.combos_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(self.combos_label)

        self.combos_table = QTableWidget()
        self.combos_table.setColumnCount(4)
        self.combos_table.setHorizontalHeaderLabels(["Control", "Action", "Comment", ""])
        self.combos_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.combos_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.combos_table.horizontalHeader().setStretchLastSection(False)
        self.combos_table.setColumnWidth(3, 120)  # Fixed width for button column
        self.combos_table.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only
        self.combos_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.combos_table.setSelectionMode(QTableWidget.SingleSelection)
        self.combos_table.verticalHeader().setVisible(False)  # Hide row numbers
        # Ensure vertical scrollbar is shown only when needed
        from PySide6.QtCore import Qt
        self.combos_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Set row height and table max height based on font metrics for proper scaling
        fm = self.combos_table.fontMetrics()
        row_height = int(fm.lineSpacing() * TABLE_ROW_HEIGHT_MULTIPLIER)
        self.combos_table.verticalHeader().setDefaultSectionSize(row_height)
        # Set max height to fit ~6 rows plus header (allows table to scale but caps it)
        header_height = self.combos_table.horizontalHeader().height()
        # Header height might be 0 at init, use reasonable default based on font metrics
        if header_height < 20:
            header_height = int(fm.lineSpacing() * 1.5)  # Base on font size
        # Calculate max height: 6 rows + header + frame/borders (shows ~4 rows initially, can grow to 6)
        max_table_height = row_height * 6 + header_height + 4
        self.combos_table.setMaximumHeight(max_table_height)
        self.combos_table.itemSelectionChanged.connect(self._on_combo_selection_changed)
        layout.addWidget(self.combos_table)

        combos_btn_layout = QHBoxLayout()
        self.add_combo_btn = QPushButton("Add Combination")
        self.add_combo_btn.clicked.connect(self._on_add_combo)
        combos_btn_layout.addWidget(self.add_combo_btn)
        combos_btn_layout.addStretch()
        layout.addLayout(combos_btn_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(self.apply_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        layout.addStretch()

        # Initially disabled
        self.setEnabled(False)

    def load_control(self, control_name: str, current_action: str, comment: str = "", modifier_combos: dict = None):
        """Load a control for editing

        Args:
            control_name: Name of the control (e.g., 'side', 'knob_cw')
            current_action: Current action string (e.g., 'KEY_LEFTCTRL+KEY_C')
            comment: Optional comment/notes for this control
            modifier_combos: Dict of control_name -> (action, comment) for combos (optional)
        """
        self.current_control = control_name
        self.control_label.setText(f"Editing: {control_name}")
        self.setEnabled(True)

        # Load comment
        self.comment_text.setPlainText(comment)

        # Parse and populate the action UI
        self._parse_and_populate(current_action)

        # Clear combos table
        self.combos_table.setRowCount(0)

        # Check if this control can have modifier combinations (physical button only)
        can_have_combos = control_name in VALID_MODIFIER_BUTTONS

        # Always show modifier combinations section, but enable/disable based on control type
        self.combos_label.show()
        self.combos_table.show()
        self.add_combo_btn.show()

        if can_have_combos:
            # Enable modifier combinations for physical buttons
            self.combos_table.setEnabled(True)
            self.add_combo_btn.setEnabled(True)

            # Load combos into table if any
            if modifier_combos:
                for combo_control, (combo_action, combo_comment) in modifier_combos.items():
                    # Don't auto-select when loading existing combos
                    self._add_combo_row(combo_control, combo_action, combo_comment, select=False)

                # Select the first combo after loading all of them
                if self.combos_table.rowCount() > 0:
                    self.combos_table.selectRow(0)
        else:
            # Not a physical button - disable modifier combinations (but keep visible)
            self.combos_table.setEnabled(False)
            self.add_combo_btn.setEnabled(False)

        logger.info(f"Loaded control for editing: {control_name}")

    def _parse_and_populate(self, action_str: str):
        """Parse action string and populate UI fields

        Args:
            action_str: Action string like 'KEY_LEFTCTRL+KEY_C' or 'REL_WHEEL:1'
        """
        # Reset UI
        self.ctrl_btn.setChecked(False)
        self.alt_btn.setChecked(False)
        self.shift_btn.setChecked(False)
        self.super_btn.setChecked(False)
        self.key_input.clear()
        self.special_key_combo.setCurrentIndex(0)

        if not action_str or action_str == "(none)" or action_str == "(unmapped)":
            self.action_type_combo.setCurrentText("None")
            return

        # Check if it's a mouse wheel action (handle both raw and human-readable formats)
        if action_str.startswith("Wheel "):
            self.action_type_combo.setCurrentText("Mouse Wheel")
            # Parse direction from human-readable format
            if "Up" in action_str:
                self.mouse_direction_combo.setCurrentText("Vertical Up")
            elif "Down" in action_str:
                self.mouse_direction_combo.setCurrentText("Vertical Down")
            elif "Left" in action_str:
                self.mouse_direction_combo.setCurrentText("Horizontal Left")
            elif "Right" in action_str:
                self.mouse_direction_combo.setCurrentText("Horizontal Right")
            return
        elif action_str.startswith("WHEEL:") or action_str.startswith("HWHEEL:"):
            # Legacy format support
            self.action_type_combo.setCurrentText("Mouse Wheel")
            if action_str.startswith("WHEEL:"):
                value = int(action_str.split(":")[1])
                if value > 0:
                    self.mouse_direction_combo.setCurrentText("Vertical Up")
                else:
                    self.mouse_direction_combo.setCurrentText("Vertical Down")
            elif action_str.startswith("HWHEEL:"):
                value = int(action_str.split(":")[1])
                if value > 0:
                    self.mouse_direction_combo.setCurrentText("Horizontal Right")
                else:
                    self.mouse_direction_combo.setCurrentText("Horizontal Left")
            return

        # It's a keyboard action
        self.action_type_combo.setCurrentText("Keyboard")

        # Parse key combination
        parts = action_str.split("+")
        for part in parts:
            part = part.strip()
            part_upper = part.upper()
            if "CTRL" in part_upper:
                self.ctrl_btn.setChecked(True)
            elif "ALT" in part_upper:
                self.alt_btn.setChecked(True)
            elif "SHIFT" in part_upper:
                self.shift_btn.setChecked(True)
            elif "META" in part_upper or "SUPER" in part_upper:
                self.super_btn.setChecked(True)
            else:
                # It's the actual key
                # Strip KEY_ prefix if present
                key_part = part
                if key_part.startswith("KEY_"):
                    key_part = key_part[4:]  # Remove "KEY_" prefix

                # Check if it's a single character (letter, number, or symbol)
                if len(key_part) == 1:
                    # It's a character - put it in text field
                    self.key_input.setText(key_part.lower())
                else:
                    # It's a special key name - try to match in special keys dropdown
                    # First try exact match, then try without spaces/underscores/case-insensitive
                    found = False
                    part_normalized = key_part.lower().replace(' ', '').replace('_', '')

                    for i in range(self.special_key_combo.count()):
                        item_text = self.special_key_combo.itemText(i)
                        item_normalized = item_text.lower().replace(' ', '').replace('_', '')

                        # Try exact match first
                        if item_text.lower() == key_part.lower():
                            self.special_key_combo.setCurrentIndex(i)
                            found = True
                            break
                        # Try normalized match (no spaces or underscores)
                        elif item_normalized == part_normalized:
                            self.special_key_combo.setCurrentIndex(i)
                            found = True
                            break

                    if not found:
                        # Unknown key, leave dropdown at None
                        logger.warning(f"Could not parse key: {key_part}")
                        self.special_key_combo.setCurrentIndex(0)

    def _on_action_type_changed(self, action_type: str):
        """Handle action type change"""
        if action_type == "Keyboard":
            self.keyboard_group.show()
            self.mouse_group.hide()
        elif action_type == "Mouse Wheel":
            self.keyboard_group.hide()
            self.mouse_group.show()
        else:  # None
            self.keyboard_group.hide()
            self.mouse_group.hide()

    def _on_key_input_changed(self, text: str):
        """Handle key input text change - clear special key dropdown"""
        if text:
            self.special_key_combo.setCurrentIndex(0)

    def _on_special_key_changed(self, key_name: str):
        """Handle special key dropdown change - clear text input"""
        if key_name and key_name != "None" and SPECIAL_KEYS.get(key_name) is not None:
            self.key_input.clear()

    def _on_apply(self):
        """Handle Apply button click"""
        if not self.current_control:
            return

        # Build action string from keyboard/mouse UI
        action_str = self._build_action_string()
        logger.info(f"Apply: {self.current_control} -> {action_str}")

        # Emit action change
        self.action_changed.emit(self.current_control, action_str)

        # Emit comment (always, even if empty)
        comment = self.comment_text.toPlainText().strip()
        self.comment_changed.emit(self.current_control, comment)

        # If this is a physical button, check if there are modifier combinations
        if self.current_control in VALID_MODIFIER_BUTTONS:
            # Extract combos from table
            combos = {}
            for row in range(self.combos_table.rowCount()):
                control_item = self.combos_table.item(row, 0)
                action_item = self.combos_table.item(row, 1)
                comment_item = self.combos_table.item(row, 2)

                if control_item and action_item:
                    control_name = control_item.text().strip()
                    # Get raw action string from UserRole data
                    action = action_item.data(Qt.UserRole) or action_item.text().strip()
                    combo_comment = comment_item.text().strip() if comment_item else ""

                    if control_name and action:
                        combos[control_name] = (action, combo_comment)

            # Build modifier config
            # A button IS a modifier if it has combinations
            is_modifier = len(combos) > 0

            modifier_config = {
                'is_modifier': is_modifier,
                'base_action': action_str,
                'base_action_comment': '',
                'combos': combos
            }

            self.modifier_config_changed.emit(self.current_control, modifier_config)
            logger.info(f"Apply modifier config: {self.current_control} - is_modifier={is_modifier}, {len(combos)} combos")

    def _build_action_string(self) -> str:
        """Build action string from current UI state

        Returns:
            Action string like 'KEY_LEFTCTRL+KEY_C' or 'REL_WHEEL:1'
        """
        action_type = self.action_type_combo.currentText()

        if action_type == "None":
            return "none"

        if action_type == "Mouse Wheel":
            direction = self.mouse_direction_combo.currentText()
            if direction == "Vertical Up":
                return "REL_WHEEL:1"
            elif direction == "Vertical Down":
                return "REL_WHEEL:-1"
            elif direction == "Horizontal Left":
                return "REL_HWHEEL:-1"
            elif direction == "Horizontal Right":
                return "REL_HWHEEL:1"

        # Keyboard action
        parts = []

        # Add modifiers
        if self.ctrl_btn.isChecked():
            parts.append("KEY_LEFTCTRL")
        if self.alt_btn.isChecked():
            parts.append("KEY_LEFTALT")
        if self.shift_btn.isChecked():
            parts.append("KEY_LEFTSHIFT")
        if self.super_btn.isChecked():
            parts.append("KEY_LEFTMETA")

        # Add key
        if self.key_input.text():
            # Convert character to KEY_ code
            char = self.key_input.text()

            # Check if it's a symbol/special character
            if char in CHAR_TO_KEYCODE:
                key_name = CHAR_TO_KEYCODE[char]
                parts.append(f"KEY_{key_name}")
            else:
                # Regular letter (a-z) - just uppercase it
                parts.append(f"KEY_{char.upper()}")
        elif self.special_key_combo.currentText() != "None":
            key_name = self.special_key_combo.currentText()
            if SPECIAL_KEYS.get(key_name):
                # Find the KEY_ constant name
                for name, code in e.__dict__.items():
                    if name.startswith('KEY_') and code == SPECIAL_KEYS[key_name]:
                        parts.append(name)
                        break

        return "+".join(parts) if parts else "none"

    def _on_combo_selection_changed(self):
        """Handle selection change in Modifier Combinations table"""
        selected = self.combos_table.selectedItems()
        if selected:
            row = self.combos_table.currentRow()
            control_item = self.combos_table.item(row, 0)
            if control_item:
                combo_control = control_item.text().strip()
                logger.debug(f"Combo selected: {combo_control}")
                self.combo_selected.emit(combo_control)

    def _on_add_combo(self):
        """Handle Add Combination button click"""
        # Get list of already-used controls
        used_controls = set()
        for row in range(self.combos_table.rowCount()):
            control_item = self.combos_table.item(row, 0)
            if control_item:
                used_controls.add(control_item.text().strip())

        # Open dialog to configure combination
        dialog = ComboConfigDialog(self, modifier_name=self.current_control, exclude_controls=used_controls)
        if dialog.exec() == QDialog.Accepted:
            control = dialog.get_control()
            action = dialog.get_action()
            comment = dialog.get_comment()

            if control and action and action != "none":
                self._add_combo_row(control, action, comment)

    def _on_edit_combo(self, row: int):
        """Handle Edit button click for a combination"""
        # Get current values
        control_item = self.combos_table.item(row, 0)
        action_item = self.combos_table.item(row, 1)
        comment_item = self.combos_table.item(row, 2)

        control = control_item.text() if control_item else ""
        action = action_item.data(Qt.UserRole) if action_item else ""  # Get raw action string
        comment = comment_item.text() if comment_item else ""

        # Get list of already-used controls (excluding the one being edited)
        used_controls = set()
        for r in range(self.combos_table.rowCount()):
            if r != row:  # Skip the row being edited
                c_item = self.combos_table.item(r, 0)
                if c_item:
                    used_controls.add(c_item.text().strip())

        # Open dialog with current values
        dialog = ComboConfigDialog(self, modifier_name=self.current_control,
                                   control_name=control, action=action, comment=comment,
                                   exclude_controls=used_controls)
        if dialog.exec() == QDialog.Accepted:
            new_control = dialog.get_control()
            new_action = dialog.get_action()
            new_comment = dialog.get_comment()

            if new_control and new_action and new_action != "none":
                # Update row
                control_item.setText(new_control)

                # Store raw action and display readable version
                readable_action = self._action_to_readable(new_action)
                action_item.setText(readable_action)
                action_item.setData(Qt.UserRole, new_action)

                comment_item.setText(new_comment)

    def _add_combo_row(self, control_name: str, action: str, comment: str, select: bool = True):
        """Add a row to the combinations table

        Args:
            control_name: Name of the control for this combo
            action: Action string
            comment: Comment text
            select: Whether to select the newly added row (default True)
        """
        row = self.combos_table.rowCount()
        self.combos_table.insertRow(row)

        # Control name
        control_item = QTableWidgetItem(control_name)
        self.combos_table.setItem(row, 0, control_item)

        # Action (display readable, store raw)
        readable_action = self._action_to_readable(action)
        action_item = QTableWidgetItem(readable_action)
        action_item.setData(Qt.UserRole, action)  # Store raw action string
        self.combos_table.setItem(row, 1, action_item)

        # Comment
        comment_item = QTableWidgetItem(comment)
        self.combos_table.setItem(row, 2, comment_item)

        # Buttons
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(2, 2, 2, 2)

        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda: self._on_edit_combo(row))
        button_layout.addWidget(edit_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self._delete_combo_row(row))
        button_layout.addWidget(delete_btn)

        self.combos_table.setCellWidget(row, 3, button_widget)

        # Select the newly added row if requested
        if select:
            self.combos_table.selectRow(row)

    def _delete_combo_row(self, row: int):
        """Delete a combination row"""
        self.combos_table.removeRow(row)

    def _action_to_readable(self, action_str: str) -> str:
        """Convert action string to human-readable format

        Args:
            action_str: Action string like 'KEY_LEFTCTRL+KEY_C'

        Returns:
            Readable string like 'Ctrl+C'
        """
        if not action_str or action_str == "none":
            return "(none)"

        # Handle mouse wheel
        if action_str.startswith("REL_WHEEL:"):
            value = action_str.split(":")[1]
            return f"Wheel {'Up' if int(value) > 0 else 'Down'}"
        elif action_str.startswith("REL_HWHEEL:"):
            value = action_str.split(":")[1]
            return f"Wheel {'Right' if int(value) > 0 else 'Left'}"

        # Symbol key mapping
        SYMBOL_MAP = {
            'LEFTBRACE': '[',
            'RIGHTBRACE': ']',
            'SEMICOLON': ';',
            'APOSTROPHE': "'",
            'GRAVE': '`',
            'BACKSLASH': '\\',
            'COMMA': ',',
            'DOT': '.',
            'SLASH': '/',
            'MINUS': '-',
            'EQUAL': '=',
        }

        # Parse keyboard action
        parts = action_str.split("+")
        readable_parts = []

        for part in parts:
            part = part.strip()
            # Convert KEY_ names to readable format
            if part.startswith("KEY_"):
                key_name = part[4:]  # Remove "KEY_" prefix

                # Special mappings
                if key_name == "LEFTCTRL" or key_name == "RIGHTCTRL":
                    readable_parts.append("Ctrl")
                elif key_name == "LEFTALT" or key_name == "RIGHTALT":
                    readable_parts.append("Alt")
                elif key_name == "LEFTSHIFT" or key_name == "RIGHTSHIFT":
                    readable_parts.append("Shift")
                elif key_name == "LEFTMETA" or key_name == "RIGHTMETA":
                    readable_parts.append("Super")
                elif key_name == "SPACE":
                    readable_parts.append("Space")
                elif key_name == "ENTER":
                    readable_parts.append("Enter")
                elif key_name == "ESC":
                    readable_parts.append("Esc")
                # Check if it's a symbol key
                elif key_name in SYMBOL_MAP:
                    readable_parts.append(SYMBOL_MAP[key_name])
                elif len(key_name) == 1:
                    readable_parts.append(key_name)
                else:
                    # Capitalize first letter of other keys
                    readable_parts.append(key_name.capitalize())
            else:
                readable_parts.append(part)

        return "+".join(readable_parts)
