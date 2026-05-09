"""Tests for tray module."""

import pytest
from datetime import datetime

from PySide6.QtWidgets import QApplication, QTableWidget
from PySide6.QtCore import Qt

from aws_sso_autologin.tray import StatusWindowProxy, ProfileStatus


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
            is_logged_in=True,
            last_login_time=datetime(2026, 1, 1, 12, 0, 0),
        )
        proxy.update_profile(status)
        
        assert "test-profile" in proxy._profiles
        assert proxy._table.rowCount() == 1
    
    def test_remove_profile_deletes_from_table(self, qapp):
        proxy = StatusWindowProxy()
        proxy.ensure_window()
        
        status = ProfileStatus(profile_name="test-profile", is_logged_in=True)
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
        assert status.is_logged_in is False
        assert status.last_login_time is None
        assert status.next_refresh_time is None
        assert status.queue_position is None
        assert status.error_message is None
    
    def test_dataclass_with_values(self):
        now = datetime.now()
        status = ProfileStatus(
            profile_name="test",
            is_logged_in=True,
            last_login_time=now,
            next_refresh_time=now,
            queue_position=1,
            error_message="Test error"
        )
        assert status.is_logged_in is True
        assert status.queue_position == 1
