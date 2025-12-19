#!/usr/bin/env python3
"""Configuration writer for TourBox Elite profiles

Handles saving profile mappings back to the config file with atomic writes and backups.
"""

import os
import configparser
import logging
import shutil
from typing import Dict, Optional
from datetime import datetime
from evdev import ecodes as e

from tourboxelite.config_loader import get_config_path, BUTTON_CODES, Profile, create_button_mapping
from tourboxelite.haptic import HapticStrength, HapticSpeed
from tourboxelite.profile_io import (
    has_profiles_dir, save_profile_to_file, get_profile_filepath,
    delete_profile_file, rename_profile_file, profile_exists
)

logger = logging.getLogger(__name__)


def _using_new_format() -> bool:
    """Check if we're using the new multi-file profile format"""
    return has_profiles_dir()


def _apply_modifications_to_profile(profile: Profile, modifications: Dict[str, str]) -> None:
    """Apply control mapping modifications to profile.mapping

    Converts control_name -> action_string to the internal hex code -> events
    format and updates the profile's mapping dict.

    Args:
        profile: Profile object to modify
        modifications: Dict of control_name -> action_string changes
    """
    if not modifications:
        return

    # Rotary controls need special handling (events include press+release in one)
    ROTARY_CONTROLS = ('scroll_up', 'scroll_down', 'knob_cw', 'knob_ccw', 'dial_cw', 'dial_ccw')

    for control_name, action_str in modifications.items():
        if control_name not in BUTTON_CODES:
            logger.warning(f"Unknown control in modifications: {control_name}")
            continue

        codes = BUTTON_CODES[control_name]
        if len(codes) != 2:
            logger.warning(f"Invalid button codes for {control_name}")
            continue

        press_code, release_code = codes
        is_rotary = control_name in ROTARY_CONTROLS

        # Handle "none" or empty action
        if not action_str or action_str.lower() == 'none':
            # Remove the mapping
            profile.mapping.pop(bytes([press_code]), None)
            profile.mapping.pop(bytes([release_code]), None)
            continue

        # Create events from action string
        press_events, release_events = create_button_mapping(action_str)

        if is_rotary:
            # Rotary controls: press events include both press+release
            profile.mapping[bytes([press_code])] = press_events + release_events
            profile.mapping[bytes([release_code])] = release_events
        else:
            # Regular buttons: separate press and release
            profile.mapping[bytes([press_code])] = press_events
            profile.mapping[bytes([release_code])] = release_events

    logger.debug(f"Applied {len(modifications)} modification(s) to profile mapping")


# All control names that should be in a profile
ALL_CONTROLS = [
    'side', 'top', 'tall', 'short',
    'c1', 'c2', 'tour',
    'dpad_up', 'dpad_down', 'dpad_left', 'dpad_right',
    'scroll_up', 'scroll_down', 'scroll_click',
    'knob_cw', 'knob_ccw', 'knob_click',
    'dial_cw', 'dial_ccw', 'dial_click',
]


def events_to_action_string(events) -> str:
    """Convert event list to config action string

    Args:
        events: List of (event_type, event_code, value) tuples

    Returns:
        Action string like 'KEY_LEFTCTRL+KEY_C' or 'REL_WHEEL:1'
    """
    if not events:
        return "none"

    parts = []
    for event_type, event_code, value in events:
        if event_type == e.EV_KEY and value == 1:  # Key press
            # Find the KEY_ name
            for name, code in e.__dict__.items():
                if name.startswith('KEY_') and code == event_code:
                    parts.append(name)
                    break
        elif event_type == e.EV_REL:  # Relative movement
            # Find the REL_ name
            for name, code in e.__dict__.items():
                if name.startswith('REL_') and code == event_code:
                    return f"{name}:{value}"  # REL events are standalone

    return "+".join(parts) if parts else "none"


def get_profile_actions(profile: Profile, modifications: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Get all control actions for a profile, applying any modifications

    Args:
        profile: Profile object with existing mappings
        modifications: Dict of control_name -> action_string to apply

    Returns:
        Dict of control_name -> action_string for all controls
    """
    actions = {}

    # Convert existing profile mappings to action strings
    for control_name in ALL_CONTROLS:
        if control_name not in BUTTON_CODES:
            logger.warning(f"Control {control_name} not in BUTTON_CODES")
            actions[control_name] = "none"
            continue

        codes = BUTTON_CODES[control_name]
        if len(codes) == 0:
            actions[control_name] = "none"
            continue

        # Get the press code
        press_code = bytes([codes[0]])

        # Look up in profile mapping
        if press_code in profile.mapping:
            events = profile.mapping[press_code]
            actions[control_name] = events_to_action_string(events)
        else:
            actions[control_name] = "none"

    # Apply modifications
    if modifications:
        for control_name, action_str in modifications.items():
            actions[control_name] = action_str

    return actions


def save_profile(profile: Profile, modifications: Dict[str, str]) -> bool:
    """Save profile modifications to config file (preserves comments and formatting)

    Args:
        profile: Profile object to save
        modifications: Dict of control_name -> action_string changes

    Returns:
        True if save succeeded, False otherwise
    """
    # Use new format if profiles directory exists
    if _using_new_format():
        # Apply modifications to profile mapping before saving
        _apply_modifications_to_profile(profile, modifications)
        filepath = get_profile_filepath(profile.name)
        return save_profile_to_file(profile, filepath)

    # Legacy format handling
    config_path = get_config_path()

    if not config_path:
        logger.error("No config file found")
        return False

    try:
        # Create backup first
        backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created backup: {backup_path}")

        # Read file as lines to preserve comments and formatting
        with open(config_path, 'r') as f:
            lines = f.readlines()

        # Find the profile section
        section_name = f"[profile:{profile.name}]"
        section_start = -1
        section_end = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == section_name:
                section_start = i
            elif section_start >= 0 and stripped.startswith('[') and stripped.endswith(']'):
                # Found next section
                section_end = i
                break

        if section_start < 0:
            logger.error(f"Profile section {section_name} not found in config")
            return False

        if section_end < 0:
            section_end = len(lines)  # Profile section goes to end of file

        # Update only the modified controls within the section
        for control_name, action_str in modifications.items():
            # Skip controls set to "none" - we'll remove them from config
            if action_str.lower() == "none":
                # Find and remove the control line if it exists
                for i in range(section_start + 1, section_end):
                    line = lines[i]
                    stripped = line.strip()

                    # Skip empty lines and comments
                    if not stripped or stripped.startswith('#'):
                        continue

                    # Check if this line is for our control
                    if '=' in line:
                        key = line.split('=')[0].strip()
                        if key == control_name:
                            # Remove this line
                            del lines[i]
                            section_end -= 1  # Adjust section end since we deleted a line
                            logger.debug(f"Removed {control_name} (set to none)")
                            break
                # Don't add it if it doesn't exist
                continue

            # Find the control line within this section
            found = False
            for i in range(section_start + 1, section_end):
                line = lines[i]
                stripped = line.strip()

                # Skip empty lines and comments
                if not stripped or stripped.startswith('#'):
                    continue

                # Check if this line is for our control
                if '=' in line:
                    key = line.split('=')[0].strip()
                    if key == control_name:
                        # Preserve indentation
                        indent = len(line) - len(line.lstrip())
                        lines[i] = ' ' * indent + f"{control_name} = {action_str}\n"
                        found = True
                        logger.debug(f"Updated {control_name} = {action_str}")
                        break

            if not found:
                # Control not found in section, add it before next section
                # Find a good place to insert (after last control mapping)
                insert_pos = section_end
                for i in range(section_end - 1, section_start, -1):
                    stripped = lines[i].strip()
                    if stripped and not stripped.startswith('#') and '=' in stripped:
                        insert_pos = i + 1
                        break

                # Add the new control mapping
                lines.insert(insert_pos, f"{control_name} = {action_str}\n")
                logger.debug(f"Added new control: {control_name} = {action_str}")
                section_end += 1  # Adjust section end since we inserted a line

        # Ensure there's a blank line before next section
        if section_end < len(lines):
            next_line = lines[section_end].strip()
            if next_line.startswith('[') and next_line.endswith(']'):
                # Next line is a section header - ensure blank line before it
                if section_end > 0 and lines[section_end - 1].strip() != '':
                    lines.insert(section_end, "\n")
                    section_end += 1

        # Write to temporary file first (atomic write)
        temp_path = f"{config_path}.tmp"
        with open(temp_path, 'w') as f:
            f.writelines(lines)

        # Rename temp file to actual config (atomic on POSIX systems)
        os.replace(temp_path, config_path)

        logger.info(f"Successfully saved profile: {profile.name}")
        return True

    except Exception as e:
        logger.error(f"Error saving profile: {e}", exc_info=True)
        # Try to restore from backup if save failed
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, config_path)
                logger.info("Restored config from backup after error")
            except Exception as restore_error:
                logger.error(f"Failed to restore backup: {restore_error}")
        return False


def save_modifier_config(profile: Profile) -> bool:
    """Save modifier button configurations to config file

    Args:
        profile: Profile object with modifier configuration

    Returns:
        True if save succeeded, False otherwise
    """
    # Use new format if profiles directory exists
    if _using_new_format():
        filepath = get_profile_filepath(profile.name)
        return save_profile_to_file(profile, filepath)

    # Legacy format handling
    config_path = get_config_path()

    if not config_path:
        logger.error("No config file found")
        return False

    try:
        # Create backup first
        backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created backup: {backup_path}")

        # Read file as lines to preserve comments and formatting
        with open(config_path, 'r') as f:
            lines = f.readlines()

        # Find the profile section
        section_name = f"[profile:{profile.name}]"
        section_start = -1
        section_end = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == section_name:
                section_start = i
            elif section_start >= 0 and stripped.startswith('[') and stripped.endswith(']'):
                section_end = i
                break

        if section_start < 0:
            logger.error(f"Profile section {section_name} not found in config")
            return False

        if section_end < 0:
            section_end = len(lines)

        # First pass: Remove old modifier declarations, base actions, combos,
        # and regular mappings for buttons that are now modifiers
        i = section_start + 1
        while i < section_end:
            line = lines[i]
            stripped = line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith('#'):
                i += 1
                continue

            if '=' in line:
                key = line.split('=')[0].strip()
                value = line.split('=', 1)[1].strip()

                # Remove old modifier declarations
                if value == 'modifier':
                    del lines[i]
                    section_end -= 1
                    continue

                # Remove old base actions and combos (anything with a dot that's not a comment)
                if '.' in key and not key.endswith('.comment'):
                    del lines[i]
                    section_end -= 1
                    continue

                # Remove regular mappings for buttons that are now modifiers
                # (they'll use base_action instead)
                if key in profile.modifier_buttons and '.' not in key:
                    del lines[i]
                    section_end -= 1
                    continue

            i += 1

        # Clean up multiple consecutive blank lines within the section
        i = section_start + 1
        while i < section_end:
            # If this line and the previous line are both blank, remove this one
            if i > section_start + 1 and lines[i].strip() == '' and lines[i - 1].strip() == '':
                del lines[i]
                section_end -= 1
            else:
                i += 1

        # Second pass: Add new modifier configuration
        # Find insertion point (after regular mappings, before next section)
        insert_pos = section_end

        # Add blank line before modifier section if we have modifiers and one doesn't already exist
        if profile.modifier_buttons or profile.modifier_base_actions or profile.modifier_mappings:
            # Check if there's already a blank line before insert_pos
            if insert_pos > 0 and lines[insert_pos - 1].strip() != '':
                lines.insert(insert_pos, "\n")
                insert_pos += 1
                section_end += 1

        # Add modifier declarations
        for modifier_name in sorted(profile.modifier_buttons):
            lines.insert(insert_pos, f"{modifier_name} = modifier\n")
            logger.debug(f"Added modifier declaration: {modifier_name}")
            insert_pos += 1
            section_end += 1

        # Add base actions
        for modifier_name in sorted(profile.modifier_base_actions.keys()):
            action_str = profile.modifier_base_actions[modifier_name]
            lines.insert(insert_pos, f"{modifier_name}.base_action = {action_str}\n")
            logger.debug(f"Added base action: {modifier_name}.base_action = {action_str}")
            insert_pos += 1
            section_end += 1

        # Add combos (maintain insertion order - don't sort)
        for (modifier_name, control_name), action_str in profile.modifier_mappings.items():
            lines.insert(insert_pos, f"{modifier_name}.{control_name} = {action_str}\n")
            logger.debug(f"Added combo: {modifier_name}.{control_name} = {action_str}")
            insert_pos += 1
            section_end += 1

        # Ensure there's a blank line after modifier section before next section
        # Check if section_end points to a section header (another profile)
        if section_end < len(lines):
            next_line = lines[section_end].strip()
            if next_line.startswith('[') and next_line.endswith(']'):
                # Next line is a section header - check if we need a blank line before it
                # Only add if the previous line is not already blank
                if section_end > 0 and lines[section_end - 1].strip() != '':
                    lines.insert(section_end, "\n")
                    section_end += 1

        # Write to temporary file first (atomic write)
        temp_path = f"{config_path}.tmp"
        with open(temp_path, 'w') as f:
            f.writelines(lines)

        # Rename temp file to actual config (atomic on POSIX systems)
        os.replace(temp_path, config_path)

        logger.info(f"Successfully saved modifier config for profile: {profile.name}")
        return True

    except Exception as e:
        logger.error(f"Error saving modifier config: {e}", exc_info=True)
        return False


def save_mapping_comments(profile: Profile) -> bool:
    """Save comments for all mappings to config file

    Handles multiline comments by converting newlines to \\n escape sequences

    Args:
        profile: Profile object with comment configuration

    Returns:
        True if save succeeded, False otherwise
    """
    # Use new format if profiles directory exists
    if _using_new_format():
        filepath = get_profile_filepath(profile.name)
        return save_profile_to_file(profile, filepath)

    # Legacy format handling
    config_path = get_config_path()

    if not config_path:
        logger.error("No config file found")
        return False

    try:
        # Create backup first
        backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created backup: {backup_path}")

        # Read file as lines to preserve comments and formatting
        with open(config_path, 'r') as f:
            lines = f.readlines()

        # Find the profile section
        section_name = f"[profile:{profile.name}]"
        section_start = -1
        section_end = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == section_name:
                section_start = i
            elif section_start >= 0 and stripped.startswith('[') and stripped.endswith(']'):
                section_end = i
                break

        if section_start < 0:
            logger.error(f"Profile section {section_name} not found in config")
            return False

        if section_end < 0:
            section_end = len(lines)

        # First pass: Remove all old .comment lines
        i = section_start + 1
        while i < section_end:
            line = lines[i]
            if '=' in line:
                key = line.split('=')[0].strip()
                if key.endswith('.comment'):
                    del lines[i]
                    section_end -= 1
                    continue
            i += 1

        # Second pass: Add new comments
        insert_pos = section_end

        # Add regular mapping comments
        for control_name in sorted(profile.mapping_comments.keys()):
            comment_text = profile.mapping_comments[control_name]
            # Convert newlines to \n escape sequences for storage
            comment_text_escaped = comment_text.replace('\n', '\\n')
            lines.insert(insert_pos, f"{control_name}.comment = {comment_text_escaped}\n")
            logger.debug(f"Added comment: {control_name}.comment")
            insert_pos += 1
            section_end += 1

        # Add modifier combo comments (maintain insertion order - don't sort)
        for (modifier_name, control_name), comment_text in profile.modifier_combo_comments.items():
            # Convert newlines to \n escape sequences for storage
            comment_text_escaped = comment_text.replace('\n', '\\n')
            lines.insert(insert_pos, f"{modifier_name}.{control_name}.comment = {comment_text_escaped}\n")
            logger.debug(f"Added combo comment: {modifier_name}.{control_name}.comment")
            insert_pos += 1
            section_end += 1

        # Ensure there's a blank line before next section
        if section_end < len(lines):
            next_line = lines[section_end].strip()
            if next_line.startswith('[') and next_line.endswith(']'):
                # Next line is a section header - ensure blank line before it
                if section_end > 0 and lines[section_end - 1].strip() != '':
                    lines.insert(section_end, "\n")
                    section_end += 1

        # Write to temporary file first (atomic write)
        temp_path = f"{config_path}.tmp"
        with open(temp_path, 'w') as f:
            f.writelines(lines)

        # Rename temp file to actual config (atomic on POSIX systems)
        os.replace(temp_path, config_path)

        logger.info(f"Successfully saved comments for profile: {profile.name}")
        return True

    except Exception as e:
        logger.error(f"Error saving comments: {e}", exc_info=True)
        return False


def save_haptic_config(profile: Profile) -> bool:
    """Save haptic configuration to config file

    Handles global, per-dial, and per-combo haptic settings.

    Args:
        profile: Profile object with haptic configuration

    Returns:
        True if save succeeded, False otherwise
    """
    # Use new format if profiles directory exists
    if _using_new_format():
        filepath = get_profile_filepath(profile.name)
        return save_profile_to_file(profile, filepath)

    # Legacy format handling
    config_path = get_config_path()

    if not config_path:
        logger.error("No config file found")
        return False

    try:
        # Create backup first
        backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created backup: {backup_path}")

        # Read file as lines to preserve comments and formatting
        with open(config_path, 'r') as f:
            lines = f.readlines()

        # Find the profile section
        section_name = f"[profile:{profile.name}]"
        section_start = -1
        section_end = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == section_name:
                section_start = i
            elif section_start >= 0 and stripped.startswith('[') and stripped.endswith(']'):
                section_end = i
                break

        if section_start < 0:
            logger.error(f"Profile section {section_name} not found in config")
            return False

        if section_end < 0:
            section_end = len(lines)

        # First pass: Remove all old haptic lines (strength and speed, global and per-dial/per-combo)
        i = section_start + 1
        while i < section_end:
            line = lines[i]
            if '=' in line:
                key = line.split('=')[0].strip()
                # Remove global and per-dial/per-combo haptic strength and speed settings
                if (key == 'haptic' or key == 'haptic_speed' or
                    key.startswith('haptic.') or key.startswith('haptic_speed.')):
                    del lines[i]
                    section_end -= 1
                    continue
            i += 1

        # Second pass: Add new haptic configuration
        # Find insertion point (after section header and matchers, before mappings)
        insert_pos = section_start + 1

        # Skip over window matching fields (app_id, window_class, etc.)
        while insert_pos < section_end:
            line = lines[insert_pos].strip()
            if not line or line.startswith('#'):
                insert_pos += 1
                continue
            if '=' in line:
                key = line.split('=')[0].strip()
                if key in ('app_id', 'window_class', 'window_title'):
                    insert_pos += 1
                    continue
            break

        # Add global haptic setting if set (Phase 1)
        if profile.haptic_config.global_setting is not None:
            haptic_value = str(profile.haptic_config.global_setting)
            lines.insert(insert_pos, f"haptic = {haptic_value}\n")
            logger.debug(f"Added haptic = {haptic_value}")
            insert_pos += 1
            section_end += 1

        # Add global haptic speed if set (Phase 1)
        if profile.haptic_config.global_speed is not None:
            speed_value = str(profile.haptic_config.global_speed)
            lines.insert(insert_pos, f"haptic_speed = {speed_value}\n")
            logger.debug(f"Added haptic_speed = {speed_value}")
            insert_pos += 1
            section_end += 1

        # Add per-dial strength settings
        for dial, strength in profile.haptic_config.dial_settings.items():
            lines.insert(insert_pos, f"haptic.{dial} = {strength}\n")
            logger.debug(f"Added haptic.{dial} = {strength}")
            insert_pos += 1
            section_end += 1

        # Add per-dial speed settings
        for dial, speed in profile.haptic_config.dial_speed_settings.items():
            lines.insert(insert_pos, f"haptic_speed.{dial} = {speed}\n")
            logger.debug(f"Added haptic_speed.{dial} = {speed}")
            insert_pos += 1
            section_end += 1

        # Add per-combo strength settings
        for (dial, modifier), strength in profile.haptic_config.combo_settings.items():
            if modifier:
                lines.insert(insert_pos, f"haptic.{dial}.{modifier} = {strength}\n")
                logger.debug(f"Added haptic.{dial}.{modifier} = {strength}")
                insert_pos += 1
                section_end += 1

        # Add per-combo speed settings
        for (dial, modifier), speed in profile.haptic_config.combo_speed_settings.items():
            if modifier:
                lines.insert(insert_pos, f"haptic_speed.{dial}.{modifier} = {speed}\n")
                logger.debug(f"Added haptic_speed.{dial}.{modifier} = {speed}")
                insert_pos += 1
                section_end += 1

        # Write to temporary file first (atomic write)
        temp_path = f"{config_path}.tmp"
        with open(temp_path, 'w') as f:
            f.writelines(lines)

        # Rename temp file to actual config (atomic on POSIX systems)
        os.replace(temp_path, config_path)

        logger.info(f"Successfully saved haptic config for profile: {profile.name}")
        return True

    except Exception as e:
        logger.error(f"Error saving haptic config: {e}", exc_info=True)
        return False


def save_profile_metadata(profile: Profile, old_name: Optional[str] = None) -> bool:
    """Save profile metadata changes (name, window matching rules)

    Args:
        profile: Profile object with updated metadata
        old_name: Original profile name if it was renamed (None if just updating matching rules)

    Returns:
        True if save succeeded, False otherwise
    """
    # Use new format if profiles directory exists
    if _using_new_format():
        # If renaming, we need to rename the file first
        if old_name and old_name != profile.name:
            if not rename_profile_file(old_name, profile.name):
                logger.error(f"Failed to rename profile file from {old_name} to {profile.name}")
                return False

        # Save the profile with updated metadata
        filepath = get_profile_filepath(profile.name)
        return save_profile_to_file(profile, filepath)

    # Legacy format handling
    config_path = get_config_path()

    if not config_path:
        logger.error("No config file found")
        return False

    try:
        # Create backup first
        backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created backup: {backup_path}")

        # Read file as lines to preserve comments and formatting
        with open(config_path, 'r') as f:
            lines = f.readlines()

        # Find the profile section (use old_name if renaming)
        search_name = old_name if old_name else profile.name
        section_name = f"[profile:{search_name}]"
        section_start = -1
        section_end = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == section_name:
                section_start = i
            elif section_start >= 0 and stripped.startswith('[') and stripped.endswith(']'):
                # Found next section
                section_end = i
                break

        if section_start < 0:
            logger.error(f"Profile section {section_name} not found in config")
            return False

        if section_end < 0:
            section_end = len(lines)  # Profile section goes to end of file

        # Update section header if name changed
        if old_name and old_name != profile.name:
            lines[section_start] = f"[profile:{profile.name}]\n"
            logger.debug(f"Renamed profile section: {old_name} -> {profile.name}")

        # Update or add window matching fields
        # Find if these fields already exist
        window_class_line = -1
        app_id_line = -1
        window_title_line = -1

        for i in range(section_start + 1, section_end):
            line = lines[i]
            stripped = line.strip()

            # Skip comments
            if stripped.startswith('#'):
                continue

            # Check what field this is
            if '=' in line:
                key = line.split('=')[0].strip()
                if key == 'window_class':
                    window_class_line = i
                elif key == 'app_id':
                    app_id_line = i
                elif key == 'window_title':
                    window_title_line = i

        # Delete old window_title line if it exists (we no longer use this field)
        if window_title_line >= 0:
            del lines[window_title_line]
            section_end -= 1
            # Adjust other line numbers if they come after the deleted line
            if app_id_line > window_title_line:
                app_id_line -= 1
            if window_class_line > window_title_line:
                window_class_line -= 1

        # Helper function to update or add a field
        def update_or_add_field(field_name, field_value, existing_line_num):
            nonlocal lines, section_end

            if field_value:
                # Value is set - update or add
                if existing_line_num >= 0:
                    # Update existing line
                    indent = len(lines[existing_line_num]) - len(lines[existing_line_num].lstrip())
                    lines[existing_line_num] = ' ' * indent + f"{field_name} = {field_value}\n"
                    logger.debug(f"Updated {field_name} = {field_value}")
                else:
                    # Add new line after section header
                    insert_pos = section_start + 1
                    lines.insert(insert_pos, f"{field_name} = {field_value}\n")
                    logger.debug(f"Added {field_name} = {field_value}")
                    section_end += 1
                    # Adjust other line numbers if they come after insert
                    return 1  # Inserted 1 line
            else:
                # Value is None/empty - remove if exists
                if existing_line_num >= 0:
                    del lines[existing_line_num]
                    logger.debug(f"Removed {field_name} (empty value)")
                    section_end -= 1
                    return -1  # Deleted 1 line
            return 0  # No change

        # Update fields in order (must track line number adjustments)
        adjustment = 0
        adjustment += update_or_add_field('app_id', profile.app_id,
                                          app_id_line + adjustment if app_id_line >= 0 else -1)
        adjustment += update_or_add_field('window_class', profile.window_class,
                                          window_class_line + adjustment if window_class_line >= 0 else -1)

        # Write to temporary file first (atomic write)
        temp_path = f"{config_path}.tmp"
        with open(temp_path, 'w') as f:
            f.writelines(lines)

        # Rename temp file to actual config (atomic on POSIX systems)
        os.replace(temp_path, config_path)

        logger.info(f"Successfully saved profile metadata: {profile.name}")
        return True

    except Exception as e:
        logger.error(f"Error saving profile metadata: {e}", exc_info=True)
        # Try to restore from backup if save failed
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, config_path)
                logger.info("Restored config from backup after error")
            except Exception as restore_error:
                logger.error(f"Failed to restore backup: {restore_error}")
        return False


def profile_exists_in_config(profile_name: str) -> bool:
    """Check if a profile exists in the config file or profiles directory

    Args:
        profile_name: Name of the profile to check

    Returns:
        True if profile exists, False otherwise
    """
    # Use new format if profiles directory exists
    if _using_new_format():
        return profile_exists(profile_name)

    # Legacy format handling
    config_path = get_config_path()

    if not config_path:
        return False

    try:
        with open(config_path, 'r') as f:
            for line in f:
                stripped = line.strip()
                if stripped == f"[profile:{profile_name}]":
                    return True
        return False
    except Exception as e:
        logger.error(f"Error checking if profile exists: {e}")
        return False


def create_new_profile(profile: Profile) -> bool:
    """Create a new profile in the config file or profiles directory

    Args:
        profile: Profile object to add

    Returns:
        True if creation succeeded, False otherwise
    """
    # Use new format if profiles directory exists
    if _using_new_format():
        filepath = get_profile_filepath(profile.name)
        return save_profile_to_file(profile, filepath)

    # Legacy format handling
    config_path = get_config_path()

    if not config_path:
        logger.error("No config file found")
        return False

    try:
        # Create backup first
        backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created backup: {backup_path}")

        # Read file as lines
        with open(config_path, 'r') as f:
            lines = f.readlines()

        # Add new profile section at the end
        lines.append(f"\n[profile:{profile.name}]\n")

        # Add window matching fields if set
        if profile.app_id:
            lines.append(f"app_id = {profile.app_id}\n")
        if profile.window_class:
            lines.append(f"window_class = {profile.window_class}\n")

        # Add control mappings
        actions = get_profile_actions(profile, None)
        for control_name, action_str in actions.items():
            # Skip controls set to "none" for new profiles
            if action_str.lower() != "none":
                lines.append(f"{control_name} = {action_str}\n")

        # Write to temporary file first (atomic write)
        temp_path = f"{config_path}.tmp"
        with open(temp_path, 'w') as f:
            f.writelines(lines)

        # Rename temp file to actual config (atomic on POSIX systems)
        os.replace(temp_path, config_path)

        logger.info(f"Successfully created new profile: {profile.name}")
        return True

    except Exception as e:
        logger.error(f"Error creating profile: {e}", exc_info=True)
        # Try to restore from backup if creation failed
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, config_path)
                logger.info("Restored config from backup after error")
            except Exception as restore_error:
                logger.error(f"Failed to restore backup: {restore_error}")
        return False


def delete_profile(profile_name: str) -> bool:
    """Delete a profile from the config file or profiles directory

    Args:
        profile_name: Name of the profile to delete

    Returns:
        True if deletion succeeded, False otherwise
    """
    # Don't allow deleting default profile
    if profile_name == 'default':
        logger.error("Cannot delete default profile")
        return False

    # Use new format if profiles directory exists
    if _using_new_format():
        return delete_profile_file(profile_name)

    # Legacy format handling
    config_path = get_config_path()

    if not config_path:
        logger.error("No config file found")
        return False

    try:
        # Create backup first
        backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created backup: {backup_path}")

        # Read file as lines
        with open(config_path, 'r') as f:
            lines = f.readlines()

        # Find the profile section
        section_name = f"[profile:{profile_name}]"
        section_start = -1
        section_end = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == section_name:
                section_start = i
            elif section_start >= 0 and stripped.startswith('[') and stripped.endswith(']'):
                # Found next section
                section_end = i
                break

        if section_start < 0:
            logger.error(f"Profile section {section_name} not found in config")
            return False

        if section_end < 0:
            # This is the last profile - find where its actual content ends
            # (before any trailing comments/examples)
            section_end = len(lines)

            # Walk backwards from end to find last actual mapping line
            for i in range(len(lines) - 1, section_start, -1):
                stripped = lines[i].strip()
                # If we find a line with '=' that's not commented, this is content
                if '=' in stripped and not stripped.startswith('#'):
                    # The content ends after this line, include one trailing blank if present
                    section_end = i + 1
                    # Include one blank line after the last mapping if it exists
                    if section_end < len(lines) and lines[section_end].strip() == '':
                        section_end += 1
                    break

        # Find where to start deletion - include comments and blank lines before this profile
        delete_start = section_start

        # Walk backwards from section_start to find comments/blanks that belong to this profile
        i = section_start - 1
        while i >= 0:
            stripped = lines[i].strip()

            # If we hit actual content from previous section (not blank, not comment), stop
            if stripped and not stripped.startswith('#'):
                break

            # If we hit another section header, stop
            if stripped.startswith('[') and stripped.endswith(']'):
                break

            # This line is a comment or blank - include it in deletion
            delete_start = i
            i -= 1

        # Find where to end deletion - DON'T include comments for the next profile
        delete_end = section_end

        # Walk backwards from section_end to find where next profile's comments begin
        # We want to preserve those comments
        if section_end < len(lines):  # If there's a next section
            i = section_end - 1
            while i > section_start:  # Don't go past our own section
                stripped = lines[i].strip()

                # If we hit a comment, this is where next profile's comments start
                if stripped.startswith('#'):
                    delete_end = i
                    i -= 1
                    # Keep walking back to find ALL comments for next profile
                    continue

                # If we hit a blank line after finding comments, include it
                if not stripped and delete_end < section_end:
                    delete_end = i
                    i -= 1
                    continue

                # If we hit actual content, stop
                if stripped:
                    break

                i -= 1

        # Delete the section (from this profile's comments through its content,
        # but NOT including next profile's comments)
        del lines[delete_start:delete_end]

        # Ensure there's a blank line between the previous profile and next profile
        if delete_start > 0 and delete_start < len(lines):
            # Check if the line before delete_start has content (not blank)
            # and the line at delete_start is not blank
            prev_line_has_content = lines[delete_start - 1].strip() != ''
            current_line_not_blank = delete_start < len(lines) and lines[delete_start].strip() != ''

            # If previous line has content AND current line is not blank (e.g., it's a comment or section header),
            # then we need a blank line between them
            if prev_line_has_content and current_line_not_blank:
                lines.insert(delete_start, '\n')

        # Write to temporary file first (atomic write)
        temp_path = f"{config_path}.tmp"
        with open(temp_path, 'w') as f:
            f.writelines(lines)

        # Rename temp file to actual config (atomic on POSIX systems)
        os.replace(temp_path, config_path)

        logger.info(f"Successfully deleted profile: {profile_name}")
        return True

    except Exception as e:
        logger.error(f"Error deleting profile: {e}", exc_info=True)
        # Try to restore from backup if deletion failed
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, config_path)
                logger.info("Restored config from backup after error")
            except Exception as restore_error:
                logger.error(f"Failed to restore backup: {restore_error}")
        return False


def cleanup_old_backups(config_path: Optional[str] = None, keep_count: int = 5):
    """Clean up old backup files, keeping only the most recent ones

    Args:
        config_path: Path to config file (uses default if None)
        keep_count: Number of recent backups to keep
    """
    if config_path is None:
        config_path = get_config_path()

    if not config_path:
        return

    try:
        config_dir = os.path.dirname(config_path)
        config_name = os.path.basename(config_path)

        # Find all backup files
        backups = []
        for filename in os.listdir(config_dir):
            if filename.startswith(f"{config_name}.backup."):
                backup_path = os.path.join(config_dir, filename)
                backups.append((os.path.getmtime(backup_path), backup_path))

        # Sort by modification time (newest first)
        backups.sort(reverse=True)

        # Delete old backups
        for _, backup_path in backups[keep_count:]:
            try:
                os.remove(backup_path)
                logger.info(f"Deleted old backup: {backup_path}")
            except Exception as e:
                logger.warning(f"Failed to delete backup {backup_path}: {e}")

    except Exception as e:
        logger.warning(f"Error cleaning up backups: {e}")


def export_profile(profile: Profile, destination_path: str) -> bool:
    """Export a profile to a file

    Args:
        profile: Profile object to export
        destination_path: Path to save the profile to

    Returns:
        True if export succeeded, False otherwise
    """
    from pathlib import Path
    return save_profile_to_file(profile, Path(destination_path))


def import_profile(source_path: str) -> tuple:
    """Import a profile from a file

    Args:
        source_path: Path to the profile file to import

    Returns:
        Tuple of (Profile or None, error_message)
    """
    from pathlib import Path
    from tourboxelite.profile_io import import_profile_from_file
    return import_profile_from_file(Path(source_path))


def install_imported_profile(profile: Profile) -> bool:
    """Install an imported profile to the profiles directory

    Args:
        profile: Profile object to install

    Returns:
        True if installation succeeded, False otherwise
    """
    filepath = get_profile_filepath(profile.name)
    return save_profile_to_file(profile, filepath)
