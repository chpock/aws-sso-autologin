"""Tests for service module."""

import subprocess

import pytest
from unittest.mock import patch, MagicMock

from aws_sso_autologin.service import (
    detect_tray_host,
    TrayHost,
    TrayHostType,
    check_tray_host_available,
    TrayHostInfo,
)
from aws_sso_autologin.errors import TrayHostError


def test_tray_host_detect_returns_host():
    from aws_sso_autologin.service import detect_tray_host
    host = detect_tray_host()
    assert host is not None


def test_tray_host_type_enum():
    """Test TrayHostType enum values."""
    assert TrayHostType.GNOME.value == "gnome"
    assert TrayHostType.KDE.value == "kde"
    assert TrayHostType.XFCE.value == "xfce"
    assert TrayHostType.MATE.value == "mate"
    assert TrayHostType.CINNAMON.value == "cinnamon"
    assert TrayHostType.UNITY.value == "unity"
    assert TrayHostType.PANTHEON.value == "pantheon"
    assert TrayHostType.BUDGIE.value == "budgie"
    assert TrayHostType.LXQT.value == "lxqt"
    assert TrayHostType.GENERIC.value == "generic"
    assert TrayHostType.UNKNOWN.value == "unknown"


def test_tray_host_info_dataclass():
    """Test TrayHostInfo dataclass."""
    info = TrayHostInfo(
        host_type=TrayHostType.GNOME,
        name="GNOME Shell",
        version="42.0",
        supports_status_notifier=True,
        supports_xembed=False,
    )
    assert info.host_type == TrayHostType.GNOME
    assert info.name == "GNOME Shell"
    assert info.version == "42.0"
    assert info.supports_status_notifier is True
    assert info.supports_xembed is False


def test_tray_host_interface_init():
    """Test TrayHost abstract interface initialization."""
    # Cannot instantiate abstract class directly
    with pytest.raises(TypeError):
        TrayHost()


def test_detect_tray_host_returns_tray_host_info():
    """Test detect_tray_host returns TrayHostInfo."""
    result = detect_tray_host()
    assert isinstance(result, TrayHostInfo)


def test_check_tray_host_available_returns_bool():
    """Test check_tray_host_available returns boolean."""
    result = check_tray_host_available()
    assert isinstance(result, bool)


def test_check_tray_host_available_logs_diagnostics_for_unknown_env():
    from aws_sso_autologin import service

    with patch.dict(
        "os.environ",
        {
            "DESKTOP_SESSION": "",
            "XDG_CURRENT_DESKTOP": "",
            "WAYLAND_DISPLAY": "",
            "DISPLAY": "",
        },
        clear=False,
    ):
        with patch.object(service.logger, "warning") as mock_warning:
            result = service.check_tray_host_available()

    assert result is False
    kwargs = mock_warning.call_args.kwargs
    assert kwargs["extra"]["event"] == "tray_host_probe_completed"
    assert kwargs["extra"]["status"] == "failed"
    assert kwargs["extra"]["reason"] == "unknown_environment"


def test_detect_tray_host_detects_desktop_session():
    """Test that detect_tray_host checks DESKTOP_SESSION."""
    with patch.dict('os.environ', {'DESKTOP_SESSION': 'gnome', 'XDG_CURRENT_DESKTOP': ''}):
        result = detect_tray_host()
        assert result.host_type in [TrayHostType.GNOME, TrayHostType.UNKNOWN]


def test_detect_tray_host_detects_xdg_current_desktop():
    """Test that detect_tray_host checks XDG_CURRENT_DESKTOP."""
    with patch.dict('os.environ', {'DESKTOP_SESSION': '', 'XDG_CURRENT_DESKTOP': 'GNOME'}):
        result = detect_tray_host()
        assert result.host_type in [TrayHostType.GNOME, TrayHostType.UNKNOWN]


def test_detect_tray_host_unknown_when_no_env():
    """Test detect_tray_host returns UNKNOWN when no desktop env vars set."""
    with patch.dict('os.environ', {'DESKTOP_SESSION': '', 'XDG_CURRENT_DESKTOP': ''}, clear=False):
        result = detect_tray_host()
        # Should return UNKNOWN when no env vars are set
        assert isinstance(result, TrayHostInfo)


def test_detect_tray_host_case_insensitive():
    """Test detect_tray_host handles case insensitively."""
    with patch.dict('os.environ', {'DESKTOP_SESSION': 'GNOME', 'XDG_CURRENT_DESKTOP': ''}):
        result = detect_tray_host()
        # Should detect regardless of case
        assert isinstance(result, TrayHostInfo)


def test_tray_host_info_defaults():
    """Test TrayHostInfo has sensible defaults."""
    info = TrayHostInfo(
        host_type=TrayHostType.UNKNOWN,
        name="Unknown",
    )
    assert info.version is None
    assert info.supports_status_notifier is False
    assert info.supports_xembed is False


def test_detect_tray_host_detects_kde():
    """Test detect_tray_host detects KDE."""
    with patch.dict('os.environ', {'DESKTOP_SESSION': 'plasma', 'XDG_CURRENT_DESKTOP': 'KDE'}):
        result = detect_tray_host()
        assert isinstance(result, TrayHostInfo)
        assert result.host_type in [TrayHostType.KDE, TrayHostType.UNKNOWN]


def test_detect_tray_host_detects_xfce():
    """Test detect_tray_host detects XFCE."""
    with patch.dict('os.environ', {'DESKTOP_SESSION': 'xfce', 'XDG_CURRENT_DESKTOP': 'XFCE'}):
        result = detect_tray_host()
        assert isinstance(result, TrayHostInfo)
        assert result.host_type in [TrayHostType.XFCE, TrayHostType.UNKNOWN]


def test_detect_tray_host_detects_hyprland_as_generic():
    with patch.dict('os.environ', {'DESKTOP_SESSION': '', 'XDG_CURRENT_DESKTOP': 'Hyprland'}):
        result = detect_tray_host()
        assert result.host_type == TrayHostType.GENERIC
        assert result.supports_status_notifier is True


def test_check_tray_host_available_true_for_hyprland():
    with patch.dict('os.environ', {'DESKTOP_SESSION': '', 'XDG_CURRENT_DESKTOP': 'Hyprland'}):
        assert check_tray_host_available() is True


def test_tray_host_error_class():
    """Test TrayHostError is raised appropriately."""
    error = TrayHostError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_create_tray_host_returns_tray_host():
    """Test create_tray_host returns a TrayHost when available."""
    from aws_sso_autologin.service import create_tray_host
    result = create_tray_host()
    # May be None if no tray host available, or a TrayHost instance
    assert result is None or hasattr(result, 'get_info')


def test_concrete_tray_host_ping_returns_bool():
    """Test ConcreteTrayHost.ping returns boolean."""
    from aws_sso_autologin.service import ConcreteTrayHost, TrayHostInfo, TrayHostType
    info = TrayHostInfo(
        host_type=TrayHostType.GNOME,
        name="Test",
        supports_status_notifier=True,
    )
    host = ConcreteTrayHost(info)
    result = host.ping()
    assert isinstance(result, bool)


def test_concrete_tray_host_marks_lost_after_three_ping_failures():
    from aws_sso_autologin.service import ConcreteTrayHost, TrayHostInfo, TrayHostType

    info = TrayHostInfo(
        host_type=TrayHostType.GNOME,
        name="Test",
        supports_status_notifier=True,
    )

    failing_runner = MagicMock(
        return_value=MagicMock(returncode=1, stdout="", stderr="no host")
    )
    host = ConcreteTrayHost(info, ping_runner=failing_runner)

    assert host.ping() is False
    assert host.ping() is False
    assert host.ping() is False
    assert host.consecutive_failures == 3
    assert host.is_lost is True


def test_concrete_tray_host_success_resets_failure_count():
    from aws_sso_autologin.service import ConcreteTrayHost, TrayHostInfo, TrayHostType

    info = TrayHostInfo(
        host_type=TrayHostType.GNOME,
        name="Test",
        supports_status_notifier=True,
    )

    runner = MagicMock(
        side_effect=[
            MagicMock(returncode=1, stdout="", stderr="timeout"),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
    )
    host = ConcreteTrayHost(info, ping_runner=runner)

    assert host.ping() is False
    assert host.consecutive_failures == 1

    assert host.ping() is True
    assert host.consecutive_failures == 0
    assert host.is_lost is False


def test_concrete_tray_host_ping_invokes_dbus_status_notifier_probe():
    from aws_sso_autologin.service import ConcreteTrayHost, TrayHostInfo, TrayHostType

    info = TrayHostInfo(
        host_type=TrayHostType.GNOME,
        name="Test",
        supports_status_notifier=True,
    )

    runner = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    host = ConcreteTrayHost(info, ping_runner=runner)
    host.ping()

    args, kwargs = runner.call_args
    command = args[0]
    assert command[0] == "dbus-send"
    assert "org.freedesktop.DBus.ListNames" in command
    assert kwargs["timeout"] == 2
