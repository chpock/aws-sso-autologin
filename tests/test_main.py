"""Tests for the main entry point module."""

import signal
from io import StringIO
from unittest.mock import MagicMock, Mock, patch


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


def test_initialize_qt_disables_quit_on_last_window_closed():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])
    mock_qapp = MagicMock()

    with patch("aws_sso_autologin.__main__.QApplication", return_value=mock_qapp):
        ok = app._initialize_qt()

    assert ok is True
    mock_qapp.setQuitOnLastWindowClosed.assert_called_once_with(False)


def test_handle_system_signal_logs_and_requests_graceful_shutdown():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])

    with patch.object(app, "shutdown") as mock_shutdown:
        with patch("aws_sso_autologin.__main__.logger.info") as mock_info:
            app._handle_system_signal(signal.SIGINT, None)

    mock_shutdown.assert_called_once_with(reason="signal:SIGINT")
    assert app._signal_shutdown_requested is True
    assert any(
        call.kwargs.get("extra", {}).get("event") == "system_signal_received"
        and call.kwargs.get("extra", {}).get("signal") == "SIGINT"
        for call in mock_info.call_args_list
    )


def test_handle_system_signal_second_interrupt_forces_exit():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])
    app._signal_shutdown_requested = True
    app._force_exit = Mock()

    with patch("aws_sso_autologin.__main__.logger.warning") as mock_warning:
        app._handle_system_signal(signal.SIGINT, None)

    app._force_exit.assert_called_once_with(130)
    assert any(
        call.kwargs.get("extra", {}).get("event") == "system_signal_force_exit"
        and call.kwargs.get("extra", {}).get("signal") == "SIGINT"
        for call in mock_warning.call_args_list
    )


def test_shutdown_is_idempotent_and_logs_duplicate_request():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])
    app._health_operator = Mock()
    app._tray_host_timer = Mock()
    app._tray = Mock()
    app._app = Mock()

    with patch("aws_sso_autologin.__main__.logger.info") as mock_info:
        app.shutdown(reason="signal:SIGTERM")
        app.shutdown(reason="signal:SIGTERM")

    app._health_operator.stop.assert_called_once()
    app._tray_host_timer.stop.assert_called_once()
    app._tray.close.assert_called_once()
    app._app.quit.assert_called_once()
    assert any(
        call.kwargs.get("extra", {}).get("event") == "shutdown_already_in_progress"
        for call in mock_info.call_args_list
    )


def test_autologin_app_detect_tray_host_success():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp()

    with patch(
        "aws_sso_autologin.__main__.check_tray_host_available", return_value=True
    ):
        with patch("aws_sso_autologin.__main__.detect_tray_host") as mock_detect:
            mock_host_info = Mock()
            mock_host_info.name = "Test Desktop"
            mock_detect.return_value = mock_host_info
            result = app._detect_tray_host()

    assert result is True


def test_autologin_app_detect_tray_host_failure():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp()

    with patch(
        "aws_sso_autologin.__main__.check_tray_host_available", return_value=False
    ):
        result = app._detect_tray_host()

    assert result is False


def test_autologin_app_detect_tray_host_failure_logs_preflight_details():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp()

    with patch(
        "aws_sso_autologin.__main__.check_tray_host_available", return_value=False
    ):
        with patch("aws_sso_autologin.__main__.detect_tray_host") as mock_detect:
            mock_host_info = Mock()
            mock_host_info.name = "Unknown Desktop Environment"
            mock_host_info.host_type.value = "unknown"
            mock_host_info.supports_status_notifier = False
            mock_host_info.supports_xembed = False
            mock_detect.return_value = mock_host_info
            with patch("aws_sso_autologin.__main__.logger.error") as mock_error:
                app._detect_tray_host()

    assert any(
        call.kwargs.get("extra", {}).get("event") == "tray_host_preflight_failed"
        for call in mock_error.call_args_list
    )


def test_autologin_app_detect_tray_host_failure_emits_stdout_guidance():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp()
    with patch(
        "aws_sso_autologin.__main__.check_tray_host_available", return_value=False
    ):
        with patch("builtins.print") as mock_print:
            result = app._detect_tray_host()

    assert result is False
    mock_print.assert_called_once()
    assert "tray host support is required" in mock_print.call_args[0][0].lower()


def test_autologin_app_create_operators():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp()

    with patch("aws_sso_autologin.__main__.LoginOperator"):
        with patch("aws_sso_autologin.__main__.SessionOperator"):
            with patch("aws_sso_autologin.__main__.HealthOperator"):
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
        error_message="AWS command timed out after 10s and was terminated",
    )

    app._on_status_change("test-profile", RenewalStatus.UNKNOWN, info)

    status = app._tray.update_profile.call_args.args[0]
    assert status.state == ProfileState.WARNING
    assert status.short_reason == "Command timed out"


def test_on_status_change_active_without_remaining_time_stays_ok():
    from aws_sso_autologin.__main__ import AutologinApp
    from aws_sso_autologin.models import RenewalStatus, SessionFailureType, SessionInfo
    from aws_sso_autologin.tray import ProfileState

    app = AutologinApp()
    app._tray = Mock()

    info = SessionInfo(
        profile_name="test-profile",
        is_active=True,
        seconds_remaining=None,
        failure_type=SessionFailureType.NONE,
    )

    app._on_status_change("test-profile", RenewalStatus.NOT_NEEDED, info)

    status = app._tray.update_profile.call_args.args[0]
    assert status.state == ProfileState.OK


def test_on_status_change_permission_denied_sets_error_state():
    from aws_sso_autologin.__main__ import AutologinApp
    from aws_sso_autologin.models import RenewalStatus, SessionFailureType, SessionInfo
    from aws_sso_autologin.tray import ProfileState

    app = AutologinApp()
    app._tray = Mock()

    info = SessionInfo(
        profile_name="test-profile",
        is_active=False,
        seconds_remaining=0,
        failure_type=SessionFailureType.PERMISSION_DENIED,
        error_message="AccessDenied: User is not authorized",
    )

    app._on_status_change("test-profile", RenewalStatus.UNKNOWN, info)

    status = app._tray.update_profile.call_args.args[0]
    assert status.state == ProfileState.ERROR
    assert status.short_reason == "Access denied"
    assert status.diagnostics_summary == "Access denied"


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


def test_on_status_change_other_failure_uses_connectivity_copy():
    from aws_sso_autologin.__main__ import AutologinApp
    from aws_sso_autologin.models import RenewalStatus, SessionFailureType, SessionInfo
    from aws_sso_autologin.tray import ProfileState

    app = AutologinApp()
    app._tray = Mock()

    info = SessionInfo(
        profile_name="test-profile",
        is_active=False,
        seconds_remaining=0,
        failure_type=SessionFailureType.OTHER,
        error_message="Could not connect to endpoint URL",
    )

    app._on_status_change("test-profile", RenewalStatus.UNKNOWN, info)

    status = app._tray.update_profile.call_args.args[0]
    assert status.state == ProfileState.WARNING
    assert status.short_reason == "Connectivity issue"


def test_paused_status_overrides_error_icon():
    from aws_sso_autologin.__main__ import AutologinApp
    from aws_sso_autologin.tray import ProfileState, ProfileStatus

    app = AutologinApp([])
    app._monitoring_enabled = False
    app._profile_status["dev"] = ProfileStatus("dev", state=ProfileState.ERROR)

    assert app._aggregate_app_state() == "paused"


def test_indeterminate_failure_does_not_clear_error_state():
    from aws_sso_autologin.__main__ import AutologinApp
    from aws_sso_autologin.models import RenewalStatus, SessionFailureType, SessionInfo
    from aws_sso_autologin.tray import ProfileState, ProfileStatus

    app = AutologinApp([])
    app._tray = Mock()
    app._profile_status["dev"] = ProfileStatus("dev", state=ProfileState.ERROR)

    info = SessionInfo(
        profile_name="dev",
        is_active=False,
        seconds_remaining=0,
        failure_type=SessionFailureType.OTHER,
        error_message="Could not connect to endpoint URL",
    )

    app._on_status_change("dev", RenewalStatus.UNKNOWN, info)

    status = app._tray.update_profile.call_args.args[0]
    assert status.state == ProfileState.ERROR


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

        result = main([])

        assert result == 0
        mock_app.run.assert_called_once()


def test_main_logs_app_version_on_startup():
    from aws_sso_autologin.__main__ import main

    with patch("aws_sso_autologin.__main__.__version__", "2.3.4"):
        with patch("aws_sso_autologin.__main__.VERSION_SOURCE", "embedded"):
            with patch("aws_sso_autologin.__main__.AutologinApp") as mock_app_class:
                with patch("aws_sso_autologin.__main__.logger.info"):
                    mock_app = Mock()
                    mock_app.run.return_value = 0
                    mock_app_class.return_value = mock_app

                    result = main([])

    assert result == 0


def test_main_prints_version_and_exits_for_long_flag():
    from aws_sso_autologin.__main__ import main

    with patch("aws_sso_autologin.__main__.__version__", "9.9.9"):
        with patch("sys.stdout", new_callable=StringIO) as stdout:
            result = main(["--version"])

    assert result == 0
    assert stdout.getvalue().strip() == "9.9.9"


def test_main_prints_version_and_exits_for_short_flag():
    from aws_sso_autologin.__main__ import main

    with patch("aws_sso_autologin.__main__.__version__", "9.9.9"):
        with patch("sys.stdout", new_callable=StringIO) as stdout:
            result = main(["-V"])

    assert result == 0
    assert stdout.getvalue().strip() == "9.9.9"


def test_main_returns_2_for_invalid_log_level():
    from aws_sso_autologin.__main__ import main

    with patch("sys.stderr", new_callable=StringIO) as stderr:
        result = main(["--log-level", "verbose"])

    assert result == 2
    assert "Invalid log level" in stderr.getvalue()


def test_main_returns_2_for_invalid_log_format():
    from aws_sso_autologin.__main__ import main

    with patch("sys.stderr", new_callable=StringIO) as stderr:
        result = main(["--log-format", "xml"])

    assert result == 2
    assert "Invalid log format" in stderr.getvalue()


def test_main_help_exits_without_starting_app():
    """Test that --help shows help and exits without starting the application."""
    from aws_sso_autologin.__main__ import main

    with patch("sys.stdout", new_callable=StringIO) as stdout:
        with patch("aws_sso_autologin.__main__.AutologinApp") as mock_app_class:
            result = main(["--help"])

    # Should exit cleanly
    assert result == 0
    # Should show help
    assert "Usage:" in stdout.getvalue()
    assert "AWS SSO tray autologin" in stdout.getvalue()
    # Should NOT start the application
    mock_app_class.assert_not_called()


def test_run_continues_when_profiles_do_not_load():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])
    mock_qapp = Mock()
    mock_qapp.exec.return_value = 0

    with patch.object(app, "_initialize_qt", return_value=True):
        with patch.object(app, "_detect_tray_host", return_value=True):
            with patch.object(app, "_create_tray", return_value=True):
                with patch.object(app, "_create_operators", return_value=True):
                    with patch.object(
                        app, "_create_tray_host_monitor", return_value=True
                    ):
                        with patch.object(app, "_wire_signals"):
                            with patch.object(
                                app, "_load_profiles", return_value=False
                            ):
                                with patch.object(
                                    app, "_start_monitoring", return_value=True
                                ):
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
                    with patch.object(
                        app, "_create_tray_host_monitor", return_value=True
                    ):
                        with patch.object(app, "_wire_signals"):
                            with patch.object(app, "_load_profiles", return_value=True):
                                with patch.object(
                                    app, "_start_monitoring", return_value=False
                                ):
                                    app._app = mock_qapp
                                    app._tray = Mock()
                                    result = app.run()

    assert result == 1


def test_run_starts_signal_pump_timer_for_sigint_responsiveness():
    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])
    mock_qapp = Mock()
    mock_qapp.exec.return_value = 0
    mock_timer = Mock()

    with patch.object(app, "_initialize_qt", return_value=True):
        with patch.object(app, "_detect_tray_host", return_value=True):
            with patch.object(app, "_create_tray", return_value=True):
                with patch.object(app, "_create_operators", return_value=True):
                    with patch.object(
                        app, "_create_tray_host_monitor", return_value=True
                    ):
                        with patch.object(app, "_wire_signals"):
                            with patch.object(app, "_load_profiles", return_value=True):
                                with patch.object(
                                    app, "_start_monitoring", return_value=True
                                ):
                                    with patch(
                                        "aws_sso_autologin.__main__.QTimer",
                                        return_value=mock_timer,
                                    ):
                                        app._app = mock_qapp
                                        app._tray = Mock()
                                        app.run()

    mock_timer.start.assert_called_once()


def test_tray_host_loss_pauses_monitoring_by_default():
    from aws_sso_autologin.__main__ import TRAY_HOST_LOST_SUMMARY, AutologinApp

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

    with patch(
        "aws_sso_autologin.__main__.discover_profiles", return_value=[profile_info]
    ):
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


def test_on_show_diagnostics_displays_error_dialog():
    """Test that _on_show_diagnostics shows ErrorDetailsDialog to user."""
    from unittest.mock import patch

    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])

    with patch("aws_sso_autologin.__main__.ErrorDetailsDialog") as mock_dialog_class:
        mock_dialog = MagicMock()
        mock_dialog_class.from_text.return_value = mock_dialog

        # Call the method that should show the dialog
        app._on_show_diagnostics("Test error summary", "Test error details")

        # Verify the dialog was created, stored, and executed
        mock_dialog_class.from_text.assert_called_once()
        assert app._details_dialog is mock_dialog
        mock_dialog.exec.assert_called_once()


def test_on_show_diagnostics_sets_recoverable_global_error_on_failure():
    from PySide6.QtWidgets import QMessageBox

    from aws_sso_autologin.__main__ import AutologinApp

    app = AutologinApp([])
    app._tray = Mock()

    with patch("aws_sso_autologin.__main__.ErrorDetailsDialog") as mock_dialog_class:
        mock_dialog_class.from_text.side_effect = RuntimeError("dialog failed")
        with patch("aws_sso_autologin.__main__.QMessageBox") as mock_qmb:
            mock_box = MagicMock()
            mock_box.exec.return_value = QMessageBox.StandardButton.Close
            mock_qmb.return_value = mock_box

            app._on_show_diagnostics("Test error summary", "Test error details")

    mock_qmb.assert_called_once()
    called_box = mock_qmb.return_value
    assert called_box.setText.call_args.args[0] == (
        "Could not open details. Try again."
    )
