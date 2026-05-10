"""Main entry point for AWS SSO Autologin application."""

import os
import signal
import sys
from datetime import datetime
from typing import Any

import typer
from click.exceptions import ClickException
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from aws_sso_autologin import VERSION_SOURCE, __version__
from aws_sso_autologin.aws import discover_profiles
from aws_sso_autologin.constants import CHECK_INTERVAL_SECONDS
from aws_sso_autologin.logger import (
    configure_logging,
    get_logger,
    install_qt_message_handler,
)
from aws_sso_autologin.mode_policy import (
    ExecutionMode,
    get_execution_mode,
)
from aws_sso_autologin.models import (
    ProfileConfig,
    RenewalStatus,
    SessionFailureType,
    SessionInfo,
)
from aws_sso_autologin.operator import (
    HealthOperator,
    LoginOperator,
    SessionOperator,
)
from aws_sso_autologin.service import (
    TrayHost,
    check_tray_host_available,
    create_tray_host,
    detect_tray_host,
)
from aws_sso_autologin.settings import RuntimeSettingsResolver
from aws_sso_autologin.tray import (
    ErrorDetailsDialog,
    ProfileState,
    ProfileStatus,
    StatusTray,
)
from aws_sso_autologin.watchdog import AutomationWatchdog, WatchdogTimeout

logger = get_logger(__name__)


class _StatusUpdateBridge(QObject):
    """Bridge status updates from worker threads to the Qt main thread."""

    status_update = Signal(str, object, object)


TRAY_HOST_REQUIRED_MESSAGE = (
    "Tray host support is required. Start this app in a Linux session "
    "with a compatible StatusNotifier/system tray host."
)
NO_PROFILES_SUMMARY = "No SSO profiles detected"
MONITORING_START_FAILED_SUMMARY = "Monitoring startup failed"
TRAY_HOST_LOST_SUMMARY = "Tray host heartbeat lost"

VALID_LOG_LEVELS = ["error", "warning", "info", "debug", "trace"]
VALID_LOG_FORMATS = ["text", "json"]


def _build_cli_app(state: dict[str, Any]) -> typer.Typer:
    app = typer.Typer(
        add_completion=False,
        help="AWS SSO tray autologin",
        rich_markup_mode=None,
        pretty_exceptions_enable=False,
    )

    @app.callback(invoke_without_command=True)
    def entry(
        version: bool = typer.Option(
            False,
            "--version",
            "-V",
            is_eager=True,
            help="Show app version and exit",
        ),
        log_level: str = typer.Option("", "--log-level", help="Log level"),
        log_format: str = typer.Option("", "--log-format", help="Log format"),
        safe_mode: bool = typer.Option(False, "--safe-mode", help="Start paused"),
        tray_loss_behavior: str = typer.Option(
            "", "--tray-loss-behavior", help="Tray-loss behavior"
        ),
        check_only: bool = typer.Option(
            False, "--check-only", help="Run preflight only"
        ),
        profiles: str = typer.Option("", "--profiles", help="Comma-separated profiles"),
    ) -> None:
        if log_level and log_level not in VALID_LOG_LEVELS:
            raise typer.BadParameter(
                "Invalid log level. Use one of: error, warning, info, debug, trace."
            )
        if log_format and log_format not in VALID_LOG_FORMATS:
            raise typer.BadParameter("Invalid log format. Use one of: text, json.")
        state.update(
            {
                "version": version,
                "log_level": log_level or None,
                "log_format": log_format or None,
                "safe_mode": safe_mode,
                "tray_loss_behavior": tray_loss_behavior or None,
                "check_only": check_only,
                "profiles": profiles or None,
            }
        )

    return app


def _run_preflight_check() -> int:
    host_info = detect_tray_host()
    if not check_tray_host_available():
        logger.error(
            "Preflight failed",
            extra={
                "event": "tray_host_preflight_failed",
                "detected_host": host_info.name,
                "host_type": host_info.host_type.value,
            },
        )
        print(TRAY_HOST_REQUIRED_MESSAGE)
        return 1

    discover_profiles()
    logger.info("Startup preflight passed", extra={"event": "preflight_passed"})
    return 0


class AutologinApp:
    """Main application class that wires all components together.

    This class:
    - Initializes QApplication
    - Detects tray host
    - Creates StatusTray
    - Creates operators (HealthOperator, SessionOperator, LoginOperator)
    - Wires signals between components
    - Loads profiles from AWS config
    - Runs Qt event loop
    """

    def __init__(self, args: list[str] | None = None) -> None:
        """Initialize the autologin application.

        Args:
            args: Command line arguments (defaults to sys.argv)
        """
        self._args = args or sys.argv
        self._app: QApplication | None = None
        self._tray: StatusTray | None = None
        self._health_operator: HealthOperator | None = None
        self._session_operator: SessionOperator | None = None
        self._login_operator: LoginOperator | None = None
        self._profiles: list[ProfileConfig] = []
        self._tray_host: TrayHost | None = None
        self._tray_host_timer: QTimer | None = None
        self._signal_pump_timer: QTimer | None = None
        self._status_update_bridge: _StatusUpdateBridge | None = None
        self._tray_host_loss_announced = False
        self._global_error_source: str | None = None
        self._awaiting_initial_status = False
        self._is_shutting_down = False
        self._signal_shutdown_requested = False
        self._signal_handlers_installed = False
        self._previous_signal_handlers: dict[int, Any] = {}
        self._force_exit = os._exit
        self._tray_loss_behavior = (
            os.getenv("AWS_SSO_AUTOLOGIN_TRAY_LOSS_BEHAVIOR", "pause").strip().lower()
        )
        self._details_dialog: Any | None = None
        self._monitoring_enabled = True
        self._profile_status: dict[str, ProfileStatus] = {}

        logger.debug("AutologinApp: Initialized")

    def _initialize_qt(self) -> bool:
        """Initialize QApplication.

        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            self._app = QApplication(self._args)
            self._app.setApplicationName("AWS SSO Autologin")
            self._app.setOrganizationName("aws-sso-autologin")
            self._app.setQuitOnLastWindowClosed(False)
            logger.debug("AutologinApp: QApplication initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize QApplication: {e}")
            return False

    def _detect_tray_host(self) -> bool:
        """Detect and validate tray host environment.

        Returns:
            True if a compatible tray host is available, False otherwise
        """
        host_info = detect_tray_host()

        if not check_tray_host_available():
            logger.error(
                "Tray host preflight failed",
                extra={
                    "event": "tray_host_preflight_failed",
                    "detected_host": host_info.name,
                    "host_type": host_info.host_type.value,
                    "supports_status_notifier": host_info.supports_status_notifier,
                    "supports_xembed": host_info.supports_xembed,
                },
            )
            print(TRAY_HOST_REQUIRED_MESSAGE)
            logger.error("No compatible tray host detected")
            return False

        logger.info(f"Detected tray host: {host_info.name}")
        return True

    def _create_tray(self) -> bool:
        """Create the system tray icon and menu.

        Returns:
            True if tray was created successfully, False otherwise
        """
        try:
            self._tray = StatusTray(
                on_toggle_monitoring=self._on_toggle_monitoring,
                on_quit=self.shutdown,
                on_show_diagnostics=self._on_show_diagnostics,
            )
            logger.debug("AutologinApp: StatusTray created")
            return True
        except Exception as e:
            logger.error(f"Failed to create StatusTray: {e}")
            return False

    def _create_operators(self) -> bool:
        """Create all operators and wire them together.

        Returns:
            True if operators were created successfully, False otherwise
        """
        try:
            # Create login operator first (bottom of the stack)
            self._login_operator = LoginOperator()
            logger.debug("AutologinApp: LoginOperator created")

            # Create session operator that uses login operator
            self._session_operator = SessionOperator(
                login_operator=self._login_operator
            )
            logger.debug("AutologinApp: SessionOperator created")

            # Create health operator that uses session operator
            self._health_operator = HealthOperator(
                session_operator=self._session_operator
            )
            logger.debug("AutologinApp: HealthOperator created")

            return True
        except Exception as e:
            logger.error(f"Failed to create operators: {e}")
            return False

    def _create_tray_host_monitor(self) -> bool:
        """Create tray-host monitor resources for runtime heartbeat checks."""
        self._tray_host = create_tray_host()
        if self._tray_host is None:
            logger.error("Failed to create tray-host monitor")
            return False

        self._tray_host_timer = QTimer()
        self._tray_host_timer.setInterval(CHECK_INTERVAL_SECONDS * 1000)
        self._tray_host_timer.timeout.connect(self._on_tray_host_heartbeat)
        return True

    def _on_tray_host_heartbeat(self) -> None:
        """Handle periodic tray-host runtime heartbeat checks."""
        if self._tray_host is None:
            return

        if self._tray_host.ping():
            if self._tray_host_loss_announced:
                self._clear_tray_global_error_if_source("tray-host")
                self._tray_host_loss_announced = False
            return

        if not getattr(self._tray_host, "is_lost", False):
            return

        details = (
            f"Tray host '{self._tray_host.get_info().name}' failed heartbeat checks "
            f"({self._tray_host.consecutive_failures} consecutive failures)."
        )

        self._set_tray_global_error(
            summary=TRAY_HOST_LOST_SUMMARY,
            details=details,
            source="tray-host",
        )

        self._tray_host_loss_announced = True

        if self._tray_loss_behavior == "continue":
            logger.warning(
                "Tray host lost; continuing monitoring per tray-loss behavior"
            )
            return

        if self._tray is not None:
            self._tray.set_monitoring_enabled(False)

        logger.error("Tray host lost; monitoring paused")

    def _set_tray_global_error(
        self, summary: str, details: str, source: str, is_config_error: bool = False
    ) -> None:
        if self._tray is None:
            return
        self._tray.set_global_error(
            summary=summary, details=details, is_config_error=is_config_error
        )
        self._global_error_source = source

    def _clear_tray_global_error_if_source(self, source: str) -> None:
        if self._tray is None:
            return
        if self._global_error_source != source:
            return
        self._tray.set_global_error(None, "")
        self._global_error_source = None

    def _wire_signals(self) -> None:
        """Wire signals between components.

        Connects health operator status changes to tray updates.
        """
        if self._health_operator and self._tray:
            # Route worker-thread status updates through Qt signal queue so
            # tray mutations always run in the GUI thread.
            self._status_update_bridge = _StatusUpdateBridge()
            self._status_update_bridge.status_update.connect(self._on_status_change)
            self._health_operator.set_status_callback(
                self._status_update_bridge.status_update.emit
            )
            logger.debug("AutologinApp: Signals wired")

    def _build_diagnostics_details(self, status: SessionInfo) -> str:
        message = status.error_message or "Session status unavailable"
        return "\n".join(
            [
                "Incident evidence: Session check result",
                "Command: aws sts get-caller-identity --profile <name>",
                f"Exit code: {'0' if status.is_active else 'non-zero'}",
                f"stderr: {message}",
                "stdout:",
                f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
            ]
        )

    def _status_from_session(
        self,
        profile_name: str,
        renewal_status: RenewalStatus,
        session_info: SessionInfo,
    ) -> ProfileStatus:
        if session_info.is_active:
            return ProfileStatus(
                profile_name=profile_name,
                state=ProfileState.OK,
                short_reason=None,
                last_login_time=datetime.now(),
            )

        if (
            renewal_status == RenewalStatus.TRIGGERED
            or session_info.failure_type == SessionFailureType.EXPIRED_OR_INVALID
        ):
            return ProfileStatus(
                profile_name=profile_name,
                state=ProfileState.SYNCING,
                short_reason="Re-authentication in progress",
                diagnostics_summary="Session expired or invalid",
                diagnostics_details=self._build_diagnostics_details(session_info),
            )

        if session_info.failure_type == SessionFailureType.TIMEOUT:
            return ProfileStatus(
                profile_name=profile_name,
                state=ProfileState.WARNING,
                short_reason="Command timed out",
                diagnostics_summary="Connectivity warning",
                diagnostics_details=self._build_diagnostics_details(session_info),
            )

        if session_info.failure_type == SessionFailureType.PERMISSION_DENIED:
            return ProfileStatus(
                profile_name=profile_name,
                state=ProfileState.ERROR,
                short_reason="Access denied",
                diagnostics_summary="Access denied",
                diagnostics_details=self._build_diagnostics_details(session_info),
            )

        if session_info.failure_type == SessionFailureType.OTHER:
            return ProfileStatus(
                profile_name=profile_name,
                state=ProfileState.WARNING,
                short_reason="Connectivity issue",
                diagnostics_summary="Connectivity warning",
                diagnostics_details=self._build_diagnostics_details(session_info),
            )

        reason = session_info.error_message or "Session check failed"
        return ProfileStatus(
            profile_name=profile_name,
            state=ProfileState.ERROR,
            short_reason=reason,
            diagnostics_summary="Session check error",
            diagnostics_details=self._build_diagnostics_details(session_info),
        )

    def _on_status_change(
        self,
        profile_name: str,
        renewal_status: RenewalStatus,
        session_info: SessionInfo,
    ) -> None:
        """Handle profile status changes.

        Args:
            profile_name: Name of the profile that changed.
            renewal_status: Renewal action outcome from SessionOperator.
            session_info: Classified session check details for taxonomy mapping.
        """
        if self._tray:
            status = self._status_from_session(
                profile_name=profile_name,
                renewal_status=renewal_status,
                session_info=session_info,
            )
            current = self._profile_status.get(profile_name)
            if (
                current is not None
                and current.state is ProfileState.ERROR
                and not session_info.is_active
            ):
                status = current
            self._profile_status[profile_name] = status
            self._tray.update_profile(status)
            app_state = self._aggregate_app_state()
            logger.info(
                "app state aggregated event=app_state_aggregated "
                "monitoring_enabled=%s profile_error_count=%s profile_sync_count=%s "
                "app_state=%s icon_state=%s",
                self._monitoring_enabled,
                sum(
                    1
                    for profile_status in self._profile_status.values()
                    if profile_status.state is ProfileState.ERROR
                ),
                sum(
                    1
                    for profile_status in self._profile_status.values()
                    if profile_status.state is ProfileState.SYNCING
                ),
                app_state,
                self._tray.current_icon_state,
            )
            if self._awaiting_initial_status:
                self._tray.set_syncing(False)
                self._awaiting_initial_status = False
            logger.debug(
                "AutologinApp: Status updated for %s: renewal=%s failure_type=%s",
                profile_name,
                renewal_status.value,
                session_info.failure_type.value,
            )

    def _aggregate_app_state(self) -> str:
        if not self._monitoring_enabled:
            return "paused"
        if any(
            status.state is ProfileState.ERROR
            for status in self._profile_status.values()
        ):
            return "error"
        return "working"

    def _on_toggle_monitoring(self, enabled: bool) -> None:
        """Handle first-row enable/disable action from tray menu."""
        self._monitoring_enabled = enabled
        if self._health_operator is None:
            return

        if enabled:
            self._health_operator.start()
            if self._tray_host_timer is not None:
                self._tray_host_timer.start()
            if self._tray is not None:
                self._tray.set_syncing(True)
            return

        self._health_operator.stop()
        if self._tray_host_timer is not None:
            self._tray_host_timer.stop()
        if self._tray is not None:
            self._tray.set_syncing(False)

    def _on_show_diagnostics(
        self, summary: str, details: str, is_config_error: bool = False
    ) -> None:
        """Handle diagnostics action from tray menu."""
        logger.info("Diagnostics requested: %s", summary)
        if details:
            logger.log(5, "Diagnostics details: %s", details)

        logger.info(
            "Creating ErrorDetailsDialog for summary: %s (config_error=%s)",
            summary,
            is_config_error,
        )
        try:
            # Show the error details dialog to the user
            self._details_dialog = ErrorDetailsDialog.from_text(
                summary=summary,
                details=details,
                parent=self._app.activeWindow() if self._app else None,
                is_config_error=is_config_error,
            )
            logger.info("ErrorDetailsDialog created, showing dialog...")
            self._details_dialog.exec()
            logger.info("ErrorDetailsDialog closed")
        except Exception as e:
            logger.error("Failed to show diagnostics dialog: %s", e, exc_info=True)
            if self._tray is not None:
                self._tray.set_global_error(
                    "Could not open details. Try again.",
                    "Could not open details. Try again.",
                )

    def _load_profiles(self) -> bool:
        """Load SSO profiles from AWS config.

        Returns:
            True if profiles were loaded, False otherwise
        """
        try:
            profile_infos = discover_profiles()

            if not profile_infos:
                logger.warning("No SSO profiles found in AWS config")
                return False

            # Convert ProfileInfo to ProfileConfig
            self._profiles = []
            for info in profile_infos:
                config = ProfileConfig(name=info.name)
                self._profiles.append(config)

            logger.info(f"Loaded {len(self._profiles)} SSO profiles")

            # Register profiles with health operator
            if self._health_operator:
                self._health_operator.register_profiles(self._profiles)

            # Initialize tray with profiles
            if self._tray:
                self._awaiting_initial_status = True
                self._tray.set_syncing(True)
                for config in self._profiles:
                    status = ProfileStatus(
                        profile_name=config.name,
                        state=ProfileState.SYNCING,
                    )
                    self._tray.update_profile(status)

            return True
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")
            return False

    def _start_monitoring(self) -> bool:
        """Start the health monitoring loop.

        Returns:
            True if monitoring started, False otherwise
        """
        if self._health_operator:
            try:
                self._health_operator.start()
                logger.info("AutologinApp: Health monitoring started")
                return True
            except Exception as e:
                logger.error(f"Failed to start health monitoring: {e}")
                return False
        return False

    def _start_signal_pump_timer(self) -> None:
        if self._app is None or self._signal_pump_timer is not None:
            return

        timer = QTimer()
        timer.setInterval(200)
        timer.timeout.connect(lambda: None)
        timer.start()
        self._signal_pump_timer = timer

    def run(self) -> int:
        """Run the application.

        Returns:
            Exit code (0 for success, non-zero for errors)
        """
        # Initialize Qt
        if not self._initialize_qt():
            return 1

        self._install_signal_handlers()

        # Detect tray host
        if not self._detect_tray_host():
            return 1

        # Create tray
        if not self._create_tray():
            return 1

        # Create operators
        if not self._create_operators():
            return 1

        # Create tray-host runtime monitor
        if not self._create_tray_host_monitor():
            return 1

        # Wire signals
        self._wire_signals()

        # Load profiles
        if not self._load_profiles():
            self._set_tray_global_error(
                summary=NO_PROFILES_SUMMARY,
                details=(
                    "No SSO profiles found in AWS config. Add a profile with"
                    " sso_session to enable auto-login."
                ),
                source="startup-no-profiles",
                is_config_error=True,
            )
            logger.warning("No SSO profiles loaded; continuing in empty-state mode")

        # Start monitoring
        if not self._start_monitoring():
            self._set_tray_global_error(
                summary=MONITORING_START_FAILED_SUMMARY,
                details="Failed to start monitoring loop.",
                source="startup-monitoring",
            )
            logger.error("Health monitoring failed to start; exiting")
            return 1

        self._start_signal_pump_timer()

        if self._tray_host_timer is not None:
            self._tray_host_timer.start()

        if self._tray is not None and not self._awaiting_initial_status:
            self._tray.set_syncing(False)

        # Run Qt event loop
        logger.info("AutologinApp: Starting Qt event loop")
        try:
            return self._app.exec()
        finally:
            self._restore_signal_handlers()

    def _install_signal_handlers(self) -> None:
        if self._signal_handlers_installed:
            return

        for sig in (signal.SIGINT, signal.SIGTERM):
            self._previous_signal_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, self._handle_system_signal)

        self._signal_handlers_installed = True
        logger.debug(
            "Installed system signal handlers",
            extra={
                "event": "signal_handlers_installed",
                "signals": ["SIGINT", "SIGTERM"],
            },
        )

    def _restore_signal_handlers(self) -> None:
        if not self._signal_handlers_installed:
            return

        for sig, handler in self._previous_signal_handlers.items():
            signal.signal(sig, handler)

        self._previous_signal_handlers.clear()
        self._signal_handlers_installed = False
        logger.debug(
            "Restored previous system signal handlers",
            extra={"event": "signal_handlers_restored"},
        )

    def _handle_system_signal(self, signum: int, _frame: object) -> None:
        signal_name = signal.Signals(signum).name

        if self._signal_shutdown_requested:
            logger.warning(
                "Second termination signal received; forcing immediate exit",
                extra={
                    "event": "system_signal_force_exit",
                    "signal": signal_name,
                    "action": "force_exit",
                    "exit_code": 130,
                },
            )
            self._force_exit(130)
            return

        self._signal_shutdown_requested = True
        logger.info(
            "Termination signal received; starting graceful shutdown",
            extra={
                "event": "system_signal_received",
                "signal": signal_name,
                "action": "graceful_shutdown",
            },
        )
        self.shutdown(reason=f"signal:{signal_name}")

    def shutdown(self, reason: str = "user_request") -> None:
        """Shutdown the application and cleanup resources."""
        if self._is_shutting_down:
            logger.info(
                "Shutdown already in progress",
                extra={
                    "event": "shutdown_already_in_progress",
                    "reason": reason,
                    "action": "ignore_duplicate_request",
                },
            )
            return

        self._is_shutting_down = True
        logger.info(
            "AutologinApp: Shutting down",
            extra={
                "event": "shutdown_started",
                "reason": reason,
            },
        )

        if self._health_operator:
            logger.info(
                "Stopping health monitoring",
                extra={"event": "shutdown_action", "action": "stop_health_monitoring"},
            )
            self._health_operator.stop()

        if self._tray_host_timer is not None:
            logger.info(
                "Stopping tray-host heartbeat timer",
                extra={"event": "shutdown_action", "action": "stop_tray_host_timer"},
            )
            self._tray_host_timer.stop()

        if self._signal_pump_timer is not None:
            logger.info(
                "Stopping signal pump timer",
                extra={"event": "shutdown_action", "action": "stop_signal_pump_timer"},
            )
            self._signal_pump_timer.stop()

        if self._details_dialog is not None:
            logger.info(
                "Closing diagnostics dialog",
                extra={
                    "event": "shutdown_action",
                    "action": "close_diagnostics_dialog",
                },
            )
            self._details_dialog.close()
            self._details_dialog = None

        if self._tray:
            logger.info(
                "Closing tray surface",
                extra={"event": "shutdown_action", "action": "close_tray"},
            )
            self._tray.close()

        if self._app:
            logger.info(
                "Requesting Qt event loop exit",
                extra={"event": "shutdown_action", "action": "quit_qt_event_loop"},
            )
            self._app.quit()


def run_with_mode(mode: ExecutionMode, check_only: bool = False) -> int:
    """
    Execute application logic based on determined mode.

    Args:
        mode: Execution mode determined by policy layer
        check_only: Whether --check-only flag was explicitly passed

    Returns:
        Exit code (0=success, 1=check failure, 124=watchdog timeout)
    """
    if mode == ExecutionMode.CHECK_ONLY or check_only:
        return run_check_only()
    else:  # NORMAL mode
        return run_normal()


def run_check_only() -> int:
    """
    Run preflight checks without entering daemon loop.

    This is the safe mode for automation and tests.
    """
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(message)s")
    logger = _logging.getLogger(__name__)

    logger.info("event=check_only_start mode=check_only")

    try:
        # Run preflight checks
        tray_available = check_tray_host_available()

        if tray_available:
            logger.info("event=check_only_completed mode=check_only status=passed")
            print(
                "Startup preflight passed. Tray host and AWS prerequisites"
                " are available."
            )
            return 0
        else:
            logger.error("event=check_only_completed mode=check_only status=failed")
            print("Startup preflight failed. See logs for details.", file=sys.stderr)
            return 1

    except Exception as e:
        logger.error(f"event=check_only_error error={e}")
        return 1


def run_normal() -> int:
    """
    Run in normal mode (daemon with event loop).

    This is the standard operation mode for interactive use.
    """
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(message)s")
    logger = _logging.getLogger(__name__)

    logger.info("event=normal_start mode=normal")

    try:
        # Import and run the actual daemon application
        from aws_sso_autologin.tray import run_tray_application

        run_tray_application()
        return 0
    except Exception as e:
        logger.error(f"event=normal_error error={e}")
        return 1


def main_entrypoint(check_only: bool = False) -> int:
    """
    Main entrypoint with policy enforcement and watchdog protection.

    Args:
        check_only: Whether --check-only flag was passed

    Returns:
        Exit code (0=success, 1=check failure, 124=watchdog timeout)
    """
    import logging as _logging

    # Setup basic logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(message)s",
    )
    logger = _logging.getLogger(__name__)

    try:
        # Determine mode (respects CLI flags and automation context)
        mode = get_execution_mode(cli_check_only=check_only)

        # Run with watchdog protection in automation contexts
        watchdog = AutomationWatchdog()

        with watchdog:
            exit_code = run_with_mode(mode, check_only=check_only)

        return exit_code

    except WatchdogTimeout as e:
        logger.error(str(e))
        return 124

    except Exception as e:
        logger.error(f"event=main_error error={e}")
        return 1


def main(args: list[str] | None = None) -> int:
    """Main entry point for the application.

    Args:
        args: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code
    """
    raw_args = list(args) if args is not None else sys.argv[1:]

    # Handle --help early to avoid starting the application
    # (typer with standalone_mode=False doesn't auto-exit after showing help)
    if "--help" in raw_args or "-h" in raw_args:
        cli_state: dict[str, Any] = {}
        cli_app = _build_cli_app(cli_state)
        try:
            cli_app(standalone_mode=False, args=raw_args)
        except typer.Exit:
            pass
        return 0

    cli_state: dict[str, Any] = {}
    cli_app = _build_cli_app(cli_state)

    try:
        cli_app(standalone_mode=False, args=raw_args)
    except typer.Exit as exc:
        return int(exc.exit_code)
    except ClickException as exc:
        print(f"Error: {exc.format_message()}", file=sys.stderr)
        return 2
    except Exception as exc:
        if isinstance(exc, SystemExit):
            return int(exc.code)
        raise

    resolver = RuntimeSettingsResolver()
    settings = resolver.resolve(cli=cli_state)
    configure_logging(level_name=settings.log_level, log_format=settings.log_format)
    install_qt_message_handler()

    if cli_state.get("version"):
        print(__version__)
        return 0

    if settings.tray_loss_behavior:
        os.environ["AWS_SSO_AUTOLOGIN_TRAY_LOSS_BEHAVIOR"] = settings.tray_loss_behavior
    if settings.safe_mode:
        os.environ["AWS_SSO_AUTOLOGIN_SAFE_MODE"] = "1"

    if cli_state.get("check_only"):
        return _run_preflight_check()

    app = AutologinApp(["aws-sso-autologin", *raw_args])

    logger.info(
        "Application startup",
        extra={
            "event": "app_started",
            "version": __version__,
            "source": VERSION_SOURCE,
        },
    )

    try:
        return app.run()
    except KeyboardInterrupt:
        logger.info(
            "Interrupted by user",
            extra={
                "event": "system_signal_received",
                "signal": "SIGINT",
                "action": "graceful_shutdown",
            },
        )
        app.shutdown(reason="signal:SIGINT")
        return 0
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
