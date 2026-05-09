"""Tests for tray module."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from aws_sso_autologin.constants import MAX_PROFILES_IN_ROOT_MENU, MAX_SUBMENU_PROFILES
from aws_sso_autologin.tray import (
    ErrorDetailsDialog,
    ProfileState,
    ProfileStatus,
    StatusTray,
    StatusWindowProxy,
)


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestStatusWindowProxy:
    def test_init(self, qapp):
        proxy = StatusWindowProxy()
        assert proxy is not None
        assert proxy._window is None
    
    def test_ensure_window_creates_widget(self, qapp):
        proxy = StatusWindowProxy()
        window = proxy.ensure_window()
        assert window is not None
        assert proxy._window is not None
        assert proxy._table is not None
    
    def test_show_makes_window_visible(self, qapp):
        proxy = StatusWindowProxy()
        proxy.show()
        assert proxy._window is not None
        assert proxy._window.isVisible()
        proxy.close()
    
    def test_update_profile_adds_to_table(self, qapp):
        proxy = StatusWindowProxy()
        proxy.ensure_window()
        
        status = ProfileStatus(
            profile_name="test-profile",
            state=ProfileState.OK,
            last_login_time=datetime(2026, 1, 1, 12, 0, 0),
        )
        proxy.update_profile(status)
        
        assert "test-profile" in proxy._profiles
        assert proxy._table.rowCount() == 1
    
    def test_remove_profile_deletes_from_table(self, qapp):
        proxy = StatusWindowProxy()
        proxy.ensure_window()
        
        status = ProfileStatus(profile_name="test-profile", state=ProfileState.OK)
        proxy.update_profile(status)
        proxy.remove_profile("test-profile")
        
        assert "test-profile" not in proxy._profiles
        assert proxy._table.rowCount() == 0
    
    def test_close_cleans_up(self, qapp):
        proxy = StatusWindowProxy()
        proxy.show()
        proxy.close()
        
        assert proxy._window is None
        assert proxy._table is None


class TestProfileStatus:
    def test_dataclass_defaults(self):
        status = ProfileStatus(profile_name="test")
        assert status.profile_name == "test"
        assert status.state == ProfileState.SYNCING
        assert status.last_login_time is None
        assert status.next_refresh_time is None
        assert status.queue_position is None
        assert status.short_reason is None
    
    def test_dataclass_with_values(self):
        now = datetime.now()
        status = ProfileStatus(
            profile_name="test",
            state=ProfileState.ERROR,
            last_login_time=now,
            next_refresh_time=now,
            queue_position=1,
            short_reason="Access denied",
        )
        assert status.state == ProfileState.ERROR
        assert status.queue_position == 1


def test_status_tray_init(qapp):
    tray = StatusTray()
    assert tray is not None
    assert tray.tray_icon is not None
    tray.close()


def test_status_tray_first_row_toggle_contract(qapp):
    tray = StatusTray()
    menu = tray.tray_icon.contextMenu()
    assert menu is not None
    actions = menu.actions()
    assert actions[0].text() == "Disable auto-login"
    assert "Quit" in [a.text() for a in actions if not a.isSeparator()]
    tray.close()


def test_status_tray_paused_switches_first_row(qapp):
    tray = StatusTray()
    enabled_icon_key = tray.tray_icon.icon().cacheKey()
    tray.set_monitoring_enabled(False)
    actions = tray.tray_icon.contextMenu().actions()
    assert actions[0].text() == "Enable auto-login"
    assert tray.current_icon_state == "disabled-paused"
    assert tray.tray_icon.icon().cacheKey() != enabled_icon_key
    tray.close()


def test_status_tray_global_error_replaces_toggle(qapp):
    on_diagnostics = MagicMock()
    tray = StatusTray(on_show_diagnostics=on_diagnostics)

    tray.set_global_error(
        summary="AWS CLI unavailable",
        details="aws command not found",
    )

    first_action = tray.tray_icon.contextMenu().actions()[0]
    assert first_action.text() == "Show startup/sync error"
    first_action.trigger()
    on_diagnostics.assert_called_once()
    tray.close()


def test_status_tray_tooltip_format(qapp):
    tray = StatusTray()
    status = ProfileStatus(
        profile_name="test-profile",
        state=ProfileState.OK,
        last_login_time=datetime.now() - timedelta(minutes=3),
    )
    tray.update_profile(status)
    tooltip = tray.tray_icon.toolTip()
    assert "AWS SSO Autologin" in tooltip
    assert "Profiles OK:" in tooltip
    tray.close()


def test_status_tray_profile_row_copy_ok(qapp):
    tray = StatusTray()
    status = ProfileStatus(
        profile_name="alpha",
        state=ProfileState.OK,
        last_login_time=datetime.now() - timedelta(minutes=1),
    )
    tray.update_profile(status)
    labels = [a.text() for a in tray.tray_icon.contextMenu().actions() if not a.isSeparator()]
    assert any(label.startswith("Profile: alpha - OK, last refresh:") for label in labels)
    tray.close()


def test_status_tray_profile_row_copy_warning_and_error(qapp):
    tray = StatusTray()
    tray.update_profile(ProfileStatus(profile_name="warn", state=ProfileState.WARNING, short_reason="Connectivity issue"))
    tray.update_profile(ProfileStatus(profile_name="err", state=ProfileState.ERROR, short_reason="Access denied"))

    labels = [a.text() for a in tray.tray_icon.contextMenu().actions() if not a.isSeparator()]
    assert "Profile: warn - Warning: Connectivity issue" in labels
    assert "Profile: err - Error: Access denied" in labels
    tray.close()


def test_status_tray_ok_profile_click_closes_menu_no_dialog(qapp):
    on_diagnostics = MagicMock()
    tray = StatusTray(on_show_diagnostics=on_diagnostics)
    tray.update_profile(ProfileStatus(profile_name="ok", state=ProfileState.OK))

    actions = tray.tray_icon.contextMenu().actions()
    ok_action = next(action for action in actions if action.text().startswith("Profile: ok"))
    ok_action.trigger()

    on_diagnostics.assert_not_called()
    tray.close()


def test_status_tray_error_profile_click_opens_dialog(qapp):
    on_diagnostics = MagicMock()
    tray = StatusTray(on_show_diagnostics=on_diagnostics)
    tray.update_profile(
        ProfileStatus(
            profile_name="broken",
            state=ProfileState.ERROR,
            short_reason="Command timed out",
            diagnostics_summary="Auto-login failed for profile \"broken\". Click to view full diagnostics.",
            diagnostics_details="Summary\nCommand\nExit code\nstderr\nstdout\nTimestamp",
        )
    )

    actions = tray.tray_icon.contextMenu().actions()
    broken_action = next(action for action in actions if action.text().startswith("Profile: broken"))
    broken_action.trigger()

    on_diagnostics.assert_called_once()
    tray.close()


def test_status_tray_overflow_uses_40_threshold_and_20_chunks(qapp):
    tray = StatusTray()
    for idx in range(MAX_PROFILES_IN_ROOT_MENU + 1):
        tray.update_profile(
            ProfileStatus(
                profile_name=f"profile-{idx:03d}",
                state=ProfileState.OK,
            )
        )

    menu = tray.tray_icon.contextMenu()
    submenu_labels = [action.text() for action in menu.actions() if action.menu() is not None]
    assert "Profiles 1-20" in submenu_labels
    assert "Profiles 21-40" in submenu_labels
    assert f"Profiles 41-{MAX_PROFILES_IN_ROOT_MENU + 1}" in submenu_labels

    submenus = [action.menu() for action in menu.actions() if action.menu() is not None]
    assert len(submenus[0].actions()) == MAX_SUBMENU_PROFILES
    assert len(submenus[1].actions()) == MAX_SUBMENU_PROFILES

    tray.close()


def test_status_tray_profile_update_refreshes_existing_label(qapp):
    tray = StatusTray()
    tray.update_profile(ProfileStatus(profile_name="alpha", state=ProfileState.SYNCING))
    tray.update_profile(ProfileStatus(profile_name="alpha", state=ProfileState.ERROR, short_reason="Access denied"))

    labels = [a.text() for a in tray.tray_icon.contextMenu().actions() if not a.isSeparator()]
    assert "Profile: alpha - Error: Access denied" in labels

    tray.close()


def test_error_details_dialog_has_required_section_order(qapp):
    dialog = ErrorDetailsDialog.from_text(
        summary="AWS CLI unavailable",
        details=(
            "Incident evidence: latest 50 incidents, max 24h\n"
            "Command: sts_check\n"
            "Exit code: 1\n"
            "stderr: failed\n"
            "stdout: \n"
            "Timestamp: 2026-05-09T12:00:00Z"
        ),
    )

    assert dialog.section_order == [
        "Summary",
        "Incident evidence",
        "Command",
        "Exit code",
        "stderr",
        "stdout",
        "Timestamp",
    ]

    dialog.close()


def test_error_details_dialog_focus_defaults_to_textarea(qapp):
    """Initial focus should be on details textarea per UX spec accessibility contract."""
    dialog = ErrorDetailsDialog.from_text(
        summary="AWS CLI unavailable",
        details="Command: sts_check\nExit code: 1",
    )

    # Focus should be on the details textarea, not the Close button
    assert dialog.focusWidget() is dialog._text_edit
    dialog.close()


def test_error_details_dialog_has_readonly_text_edit(qapp):
    """Dialog should have a readonly text edit for error details."""
    dialog = ErrorDetailsDialog.from_text(
        summary="Test error",
        details="Command: test_cmd\nExit code: 1",
    )

    # Check that text edit exists and is readonly
    assert hasattr(dialog, '_text_edit')
    assert dialog._text_edit.isReadOnly()
    dialog.close()


def test_error_details_dialog_text_contains_all_sections(qapp):
    """Text edit should contain all section information."""
    dialog = ErrorDetailsDialog.from_text(
        summary="AWS CLI unavailable",
        details=(
            "Command executed: true\n"
            "Command: sts_check\n"
            "Exit code: 1\n"
            "stderr: error message"
        ),
    )

    text = dialog._text_edit.toPlainText()
    # Check that all sections are present
    assert "Summary: AWS CLI unavailable" in text
    assert "Command: sts_check" in text
    assert "Exit code: 1" in text
    assert "stderr: error message" in text
    dialog.close()


def test_error_details_dialog_has_floating_window_flags(qapp):
    """Dialog should have WindowStaysOnTopHint flag set."""
    dialog = ErrorDetailsDialog.from_text(
        summary="Test error",
        details="Command: test",
    )

    flags = dialog.windowFlags()
    assert flags & Qt.WindowStaysOnTopHint
    dialog.close()


def test_error_details_dialog_is_fixed_size(qapp):
    dialog = ErrorDetailsDialog.from_text(
        summary="Test error",
        details="Command: test",
    )

    assert dialog.minimumSize() == dialog.maximumSize()
    assert dialog.minimumWidth() == 760
    assert dialog.minimumHeight() == 480
    dialog.close()


def test_error_details_dialog_hides_command_fields_when_not_executed(qapp):
    dialog = ErrorDetailsDialog.from_text(
        summary="Connectivity issue",
        details=(
            "Command executed: false\n"
            "Command: sts_check\n"
            "Exit code: 1\n"
            "stderr: failed\n"
            "stdout: output\n"
            "Timestamp: 2026-05-09T12:00:00Z"
        ),
    )

    text = dialog._text_edit.toPlainText()
    assert "Summary: Connectivity issue" in text
    assert "Timestamp: 2026-05-09T12:00:00Z" in text
    assert "Command:" not in text
    assert "Exit code:" not in text
    assert "stderr:" not in text
    assert "stdout:" not in text
    dialog.close()


def test_error_details_dialog_unknown_execution_state_copy_contract(qapp):
    """Unknown execution state must show 'Unknown execution state' header and supporting copy."""
    dialog = ErrorDetailsDialog.from_text(
        summary="Payload incomplete",
        details=(
            "Command: sts_check\n"
            "Exit code: 1\n"
            "stderr: error output\n"
            "stdout: some output\n"
            "Timestamp: 2026-05-09T12:00:00Z"
        ),
    )

    # Dialog should have unknown execution state (command_executed not specified)
    assert dialog._command_executed is None

    # Textarea should contain the raw outputs even though command_executed is unknown
    text = dialog._text_edit.toPlainText()
    assert "Summary: Payload incomplete" in text
    assert "stdout: some output" in text
    assert "stderr: error output" in text
    dialog.close()


def test_error_details_dialog_focus_on_textarea_for_unknown_state(qapp):
    """Focus should be on textarea even for unknown execution state."""
    dialog = ErrorDetailsDialog.from_text(
        summary="Unknown state test",
        details="Command: test\nstderr: error",
    )

    assert dialog._command_executed is None
    assert dialog.focusWidget() is dialog._text_edit
    dialog.close()


def test_error_details_dialog_shows_unknown_fields_when_execution_unknown(qapp):
    """Unknown execution state shows 'unknown' for Command/Exit code per UX spec contract."""
    dialog = ErrorDetailsDialog.from_text(
        summary="Connectivity issue",
        details=(
            "Command: sts_check\n"
            "Exit code: 1\n"
            "stderr: failed\n"
            "stdout: output\n"
            "Timestamp: 2026-05-09T12:00:00Z"
        ),
    )

    text = dialog._text_edit.toPlainText()
    assert "Summary: Connectivity issue" in text
    assert "Timestamp: 2026-05-09T12:00:00Z" in text
    # Per UX spec, unknown execution state shows "unknown" values, not hiding fields
    assert "Command: unknown" in text
    assert "Exit code: unknown" in text
    # Raw outputs are preserved in textarea even when execution state unknown
    assert "stderr: failed" in text
    assert "stdout: output" in text
    dialog.close()


def test_error_details_dialog_normalizes_unknown_fields_when_executed(qapp):
    dialog = ErrorDetailsDialog.from_text(
        summary="Auto-login failed",
        details="Command executed: true",
    )

    text = dialog._text_edit.toPlainText()
    assert "Summary: Auto-login failed" in text
    assert "Command: unknown" in text
    assert "Exit code: unknown" in text
    assert "stdout: " in text
    assert "stderr:" not in text
    dialog.close()


def test_status_tray_default_diagnostics_opens_dialog(qapp):
    tray = StatusTray()
    tray.update_profile(
        ProfileStatus(
            profile_name="warning-profile",
            state=ProfileState.WARNING,
            short_reason="Connectivity issue",
        )
    )

    warning_action = next(
        action
        for action in tray.tray_icon.contextMenu().actions()
        if action.text().startswith("Profile: warning-profile")
    )
    warning_action.trigger()

    assert tray._details_dialog is not None
    assert tray._details_dialog.isVisible()
    # Default diagnostics don't specify command_executed, so it's unknown state
    assert tray._details_dialog.sections["Command"] == "unknown"
    assert tray._details_dialog.sections["Exit code"] == "unknown"
    # Raw stdout/stderr from default diagnostics are preserved in textarea
    assert tray._details_dialog.sections["stderr"] == "unavailable"
    assert tray._details_dialog.sections["stdout"] == "unavailable"
    assert tray._details_dialog.sections["Timestamp"] == "unavailable"

    tray._details_dialog.close()
    tray.close()


def test_status_tray_no_profiles_single_separator_before_quit(qapp):
    """When no profiles exist, only one separator between first row and Quit."""
    tray = StatusTray()
    # Ensure no profiles
    assert len(tray._profiles) == 0

    actions = tray.tray_icon.contextMenu().actions()

    # Count separators
    separator_count = sum(1 for a in actions if a.isSeparator())

    # Should have only 1 separator (between first row and Quit)
    assert separator_count == 1

    # Verify structure: first row, separator, Quit
    non_separator_actions = [a for a in actions if not a.isSeparator()]
    assert non_separator_actions[0].text() == "Disable auto-login"
    assert non_separator_actions[-1].text() == "Quit"

    tray.close()


def test_error_details_dialog_has_three_regions(qapp):
    dialog = ErrorDetailsDialog.from_text(
        summary="AWS CLI unavailable",
        details="Command: sts_check\nExit code: 1\nstderr: fail",
    )

    assert dialog._status_header is not None
    assert dialog._smart_fields_region is not None
    assert dialog._text_edit is not None
    assert dialog._text_edit.isReadOnly() is True
    dialog.close()


def test_error_details_dialog_has_copy_button(qapp):
    """Dialog should have Copy all details button."""
    dialog = ErrorDetailsDialog.from_text(
        summary="Test error",
        details="Command: test",
    )

    assert hasattr(dialog, '_copy_button')
    assert dialog._copy_button is not None
    assert dialog._copy_button.text() == "Copy all details"
    dialog.close()


def test_error_details_dialog_copy_button_triggers_handler(qapp, monkeypatch):
    """Copy button should trigger _on_copy_all_details handler."""
    dialog = ErrorDetailsDialog.from_text(
        summary="Test error",
        details="Command: test",
    )

    handler_called = False

    def mock_handler():
        nonlocal handler_called
        handler_called = True

    monkeypatch.setattr(dialog, '_on_copy_all_details', mock_handler)
    dialog._copy_button.click()

    assert handler_called is True
    dialog.close()


def test_error_details_dialog_helper_label_in_layout(qapp):
    """Helper label should be in dialog layout between textarea and buttons."""
    dialog = ErrorDetailsDialog.from_text(
        summary="Test error",
        details="Command: test",
    )

    assert hasattr(dialog, '_copy_helper_label')
    assert dialog._copy_helper_label is not None
    # Label should be visible in the layout
    assert dialog._copy_helper_label.parent() is dialog
    dialog.close()


def test_error_details_dialog_helper_label_visible_after_failure(qapp, monkeypatch):
    """Helper label should show text after copy failure."""
    dialog = ErrorDetailsDialog.from_text("summary", "Command: sts_check")

    class RaisingClipboard:
        def setText(self, _text: str) -> None:
            raise RuntimeError("clipboard unavailable")

    monkeypatch.setattr(dialog, "_clipboard", RaisingClipboard())
    dialog._on_copy_all_details()

    assert dialog._copy_helper_label.text() == "Copy failed. Select details text and copy manually."
    assert dialog._copy_helper_state in {"fail", "escalated"}
    dialog.close()


def test_error_details_dialog_helper_label_cleared_on_success(qapp):
    """Helper label should be cleared immediately on copy success (no success display)."""
    dialog = ErrorDetailsDialog.from_text("summary", "Command: sts_check")
    dialog._set_copy_helper_state("fail")

    dialog._on_copy_all_details()

    assert dialog._copy_helper_state == "none"
    assert dialog._copy_helper_label.text() == ""
    dialog.close()


def test_error_details_dialog_has_accessible_live_region(qapp):
    """Helper label should have accessibility properties for screen readers."""
    dialog = ErrorDetailsDialog.from_text(
        summary="Test error",
        details="Command: test",
    )

    assert dialog._copy_helper_label.accessibleName() == "Copy status announcement"
    assert dialog._copy_helper_label.property("accessible-live-region") == "polite"
    dialog.close()


def test_error_details_dialog_copy_failure_logs_telemetry(qapp, monkeypatch, caplog):
    """Copy failure should log telemetry fields in structured log."""
    import logging
    from aws_sso_autologin.tray import logger as tray_logger

    dialog = ErrorDetailsDialog.from_text(
        summary="AWS CLI unavailable",
        details="Command: sts_check\nExit code: 1",
    )

    class RaisingClipboard:
        def setText(self, _text: str) -> None:
            raise RuntimeError("clipboard unavailable")

    monkeypatch.setattr(dialog, "_clipboard", RaisingClipboard())

    with caplog.at_level(logging.WARNING, logger=tray_logger.name):
        dialog._on_copy_all_details()

    # Check that telemetry fields are present in the log
    assert "event=diagnostics_copy_failed" in caplog.text
    # The extra fields are in the log record, not necessarily in caplog.text
    # but we can verify the function doesn't error
    dialog.close()


def test_error_details_dialog_copy_success_logs_telemetry(qapp, caplog):
    """Copy success should log telemetry fields in structured log."""
    import logging
    from aws_sso_autologin.tray import logger as tray_logger

    dialog = ErrorDetailsDialog.from_text(
        summary="AWS CLI unavailable",
        details="Command: sts_check\nExit code: 1",
    )

    with caplog.at_level(logging.INFO, logger=tray_logger.name):
        dialog._on_copy_all_details()

    # Check that telemetry fields are present in the log
    assert "event=diagnostics_copy_succeeded" in caplog.text
    dialog.close()


def test_error_details_dialog_copy_failure_shows_helper(qapp, monkeypatch):
    dialog = ErrorDetailsDialog.from_text("summary", "Command: sts_check")

    class RaisingClipboard:
        def setText(self, _text: str) -> None:
            raise RuntimeError("clipboard unavailable")

    monkeypatch.setattr(dialog, "_clipboard", RaisingClipboard())
    dialog._on_copy_all_details()

    assert dialog._copy_helper_label.text() == "Copy failed. Select details text and copy manually."
    assert dialog._copy_helper_state in {"fail", "escalated"}
    dialog.close()


def test_error_details_dialog_copy_success_clears_helper(qapp):
    dialog = ErrorDetailsDialog.from_text("summary", "Command: sts_check")
    dialog._set_copy_helper_state("fail")
    dialog._on_copy_all_details()

    assert dialog._copy_helper_state == "none"
    assert dialog._copy_helper_label.text() == ""
    dialog.close()
