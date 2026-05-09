"""Tests for the main entry point module."""

import pytest
from unittest.mock import Mock, patch, MagicMock


def test_main_imports():
    from aws_sso_autologin.__main__ import main
    assert callable(main)


def test_autologin_app_initialization():
    from aws_sso_autologin.__main__ import AutologinApp
    app = AutologinApp()
    assert app._app is None
    assert app._tray is None
    assert app._health_operator is None
    assert app._session_operator is None
    assert app._login_operator is None
    assert app._profiles == []


def test_autologin_app_with_args():
    from aws_sso_autologin.__main__ import AutologinApp
    args = ["--test"]
    app = AutologinApp(args)
    assert app._args == args


def test_autologin_app_detect_tray_host_success():
    from aws_sso_autologin.__main__ import AutologinApp
    app = AutologinApp()
    
    with patch("aws_sso_autologin.__main__.check_tray_host_available", return_value=True):
        with patch("aws_sso_autologin.__main__.detect_tray_host") as mock_detect:
            mock_host_info = Mock()
            mock_host_info.name = "Test Desktop"
            mock_detect.return_value = mock_host_info
            result = app._detect_tray_host()
    
    assert result is True


def test_autologin_app_detect_tray_host_failure():
    from aws_sso_autologin.__main__ import AutologinApp
    app = AutologinApp()

    with patch("aws_sso_autologin.__main__.check_tray_host_available", return_value=False):
        result = app._detect_tray_host()

    assert result is False


def test_autologin_app_detect_tray_host_failure_emits_stdout_guidance():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp()
    with patch("aws_sso_autologin.__main__.check_tray_host_available", return_value=False):
        with patch("builtins.print") as mock_print:
            result = app._detect_tray_host()

    assert result is False
    mock_print.assert_called_once()
    assert "tray host support is required" in mock_print.call_args[0][0].lower()


def test_autologin_app_create_operators():
    from aws_sso_autologin.__main__ import AutologinApp
    app = AutologinApp()
    
    with patch("aws_sso_autologin.__main__.LoginOperator") as mock_login:
        with patch("aws_sso_autologin.__main__.SessionOperator") as mock_session:
            with patch("aws_sso_autologin.__main__.HealthOperator") as mock_health:
                result = app._create_operators()
    
    assert result is True
    assert app._login_operator is not None
    assert app._session_operator is not None
    assert app._health_operator is not None


def test_autologin_app_wire_signals():
    from aws_sso_autologin.__main__ import AutologinApp
    app = AutologinApp()
    
    app._health_operator = Mock()
    app._tray = Mock()
    
    app._wire_signals()
    
    app._health_operator.set_status_callback.assert_called_once()


def test_autologin_app_on_status_change():
    from aws_sso_autologin.__main__ import AutologinApp
    from aws_sso_autologin.models import RenewalStatus, SessionFailureType, SessionInfo

    app = AutologinApp()
    
    app._tray = Mock()
    app._profiles = []
    
    with patch("aws_sso_autologin.__main__.ProfileStatus") as mock_status:
        info = SessionInfo(
            profile_name="test-profile",
            is_active=True,
            seconds_remaining=300,
            failure_type=SessionFailureType.NONE,
        )
        app._on_status_change("test-profile", RenewalStatus.NOT_NEEDED, info)
        mock_status.assert_called_once()


def test_on_status_change_expired_invalid_sets_syncing_state():
    from aws_sso_autologin.__main__ import AutologinApp
    from aws_sso_autologin.models import RenewalStatus, SessionFailureType, SessionInfo
    from aws_sso_autologin.tray import ProfileState

    app = AutologinApp()
    app._tray = Mock()

    info = SessionInfo(
        profile_name="test-profile",
        is_active=False,
        seconds_remaining=0,
        failure_type=SessionFailureType.EXPIRED_OR_INVALID,
        error_message="The SSO session has expired",
    )

    app._on_status_change("test-profile", RenewalStatus.TRIGGERED, info)

    status = app._tray.update_profile.call_args.args[0]
    assert status.state == ProfileState.SYNCING
    assert status.diagnostics_summary == "Session expired or invalid"


def test_on_status_change_timeout_sets_warning_state():
    from aws_sso_autologin.__main__ import AutologinApp
    from aws_sso_autologin.models import RenewalStatus, SessionFailureType, SessionInfo
    from aws_sso_autologin.tray import ProfileState

    app = AutologinApp()
    app._tray = Mock()

    info = SessionInfo(
        profile_name="test-profile",
        is_active=False,
        seconds_remaining=0,
        failure_type=SessionFailureType.TIMEOUT,
        error_message="Command timed out",
    )

    app._on_status_change("test-profile", RenewalStatus.UNKNOWN, info)

    status = app._tray.update_profile.call_args.args[0]
    assert status.state == ProfileState.WARNING
    assert status.short_reason == "Command timed out"


def test_on_status_change_check_error_sets_error_state():
    from aws_sso_autologin.__main__ import AutologinApp
    from aws_sso_autologin.models import RenewalStatus, SessionFailureType, SessionInfo
    from aws_sso_autologin.tray import ProfileState

    app = AutologinApp()
    app._tray = Mock()

    info = SessionInfo(
        profile_name="test-profile",
        is_active=False,
        seconds_remaining=None,
        failure_type=SessionFailureType.CHECK_ERROR,
        error_message="subprocess failure",
    )

    app._on_status_change("test-profile", RenewalStatus.UNKNOWN, info)

    status = app._tray.update_profile.call_args.args[0]
    assert status.state == ProfileState.ERROR
    assert status.short_reason == "subprocess failure"


def test_autologin_app_load_profiles_empty():
    from aws_sso_autologin.__main__ import AutologinApp
    app = AutologinApp()
    
    with patch("aws_sso_autologin.__main__.discover_profiles", return_value=[]):
        result = app._load_profiles()
    
    assert result is False
    assert app._profiles == []


def test_main_function():
    from aws_sso_autologin.__main__ import main
    
    with patch("aws_sso_autologin.__main__.AutologinApp") as mock_app_class:
        mock_app = Mock()
        mock_app.run.return_value = 0
        mock_app_class.return_value = mock_app
        
        result = main()
        
        assert result == 0
        mock_app.run.assert_called_once()


def test_run_continues_when_profiles_do_not_load():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])
    mock_qapp = Mock()
    mock_qapp.exec.return_value = 0

    with patch.object(app, "_initialize_qt", return_value=True):
        with patch.object(app, "_detect_tray_host", return_value=True):
            with patch.object(app, "_create_tray", return_value=True):
                with patch.object(app, "_create_operators", return_value=True):
                    with patch.object(app, "_create_tray_host_monitor", return_value=True):
                        with patch.object(app, "_wire_signals"):
                            with patch.object(app, "_load_profiles", return_value=False):
                                with patch.object(app, "_start_monitoring", return_value=True):
                                    app._app = mock_qapp
                                    app._tray = Mock()
                                    result = app.run()

    assert result == 0


def test_run_fails_when_monitoring_does_not_start():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])
    mock_qapp = Mock()
    mock_qapp.exec.return_value = 0

    with patch.object(app, "_initialize_qt", return_value=True):
        with patch.object(app, "_detect_tray_host", return_value=True):
            with patch.object(app, "_create_tray", return_value=True):
                with patch.object(app, "_create_operators", return_value=True):
                    with patch.object(app, "_create_tray_host_monitor", return_value=True):
                        with patch.object(app, "_wire_signals"):
                            with patch.object(app, "_load_profiles", return_value=True):
                                with patch.object(app, "_start_monitoring", return_value=False):
                                    app._app = mock_qapp
                                    app._tray = Mock()
                                    result = app.run()

    assert result == 1


def test_tray_host_loss_pauses_monitoring_by_default():
    from aws_sso_autologin.__main__ import AutologinApp, TRAY_HOST_LOST_SUMMARY

    app = AutologinApp([])
    app._tray = Mock()
    app._tray_loss_behavior = "pause"

    host = Mock()
    host.ping.return_value = False
    host.is_lost = True
    host.consecutive_failures = 3
    host.get_info.return_value = Mock(name="GNOME")
    host.get_info.return_value.name = "GNOME"
    app._tray_host = host

    app._on_tray_host_heartbeat()

    app._tray.set_global_error.assert_called_once()
    kwargs = app._tray.set_global_error.call_args.kwargs
    assert kwargs["summary"] == TRAY_HOST_LOST_SUMMARY
    app._tray.set_monitoring_enabled.assert_called_once_with(False)


def test_tray_host_loss_continue_mode_keeps_monitoring():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])
    app._tray = Mock()
    app._tray_loss_behavior = "continue"

    host = Mock()
    host.ping.return_value = False
    host.is_lost = True
    host.consecutive_failures = 3
    host.get_info.return_value = Mock(name="GNOME")
    host.get_info.return_value.name = "GNOME"
    app._tray_host = host

    app._on_tray_host_heartbeat()

    app._tray.set_global_error.assert_called_once()
    app._tray.set_monitoring_enabled.assert_not_called()


def test_tray_host_recovery_clears_global_error():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])
    app._tray = Mock()
    app._tray_host_loss_announced = True
    app._global_error_source = "tray-host"

    host = Mock()
    host.ping.return_value = True
    app._tray_host = host

    app._on_tray_host_heartbeat()

    app._tray.set_global_error.assert_called_once_with(None, "")


def test_tray_host_recovery_does_not_clear_unrelated_global_error():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])
    app._tray = Mock()
    app._tray_host_loss_announced = True
    app._global_error_source = "startup-monitoring"

    host = Mock()
    host.ping.return_value = True
    app._tray_host = host

    app._on_tray_host_heartbeat()

    app._tray.set_global_error.assert_not_called()


def test_load_profiles_sets_syncing_until_first_status_update():
    from aws_sso_autologin.__main__ import AutologinApp
    from aws_sso_autologin.models import RenewalStatus, SessionFailureType, SessionInfo

    app = AutologinApp([])
    app._tray = Mock()
    app._health_operator = Mock()

    profile_info = Mock()
    profile_info.name = "example"
    profile_info.sso_start_url = "https://start"
    profile_info.sso_region = "us-east-1"

    with patch("aws_sso_autologin.__main__.discover_profiles", return_value=[profile_info]):
        loaded = app._load_profiles()

    assert loaded is True
    app._tray.set_syncing.assert_called_once_with(True)
    assert app._awaiting_initial_status is True

    info = SessionInfo(
        profile_name="example",
        is_active=True,
        seconds_remaining=300,
        failure_type=SessionFailureType.NONE,
    )
    app._on_status_change("example", RenewalStatus.NOT_NEEDED, info)
    assert app._awaiting_initial_status is False
    app._tray.set_syncing.assert_called_with(False)
