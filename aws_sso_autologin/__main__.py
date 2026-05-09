"""Main entry point for AWS SSO Autologin application."""

import os
import signal
import sys
from datetime import datetime
from typing import Optional, List

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from aws_sso_autologin.constants import CHECK_INTERVAL_SECONDS
from aws_sso_autologin.service import (
    TrayHost,
    check_tray_host_available,
    create_tray_host,
    detect_tray_host,
)
from aws_sso_autologin.tray import ProfileState, ProfileStatus, StatusTray
from aws_sso_autologin.operator import HealthOperator, SessionOperator, LoginOperator
from aws_sso_autologin.models import (
    ProfileConfig,
    RenewalStatus,
    SessionFailureType,
    SessionInfo,
)
from aws_sso_autologin.aws import discover_profiles
from aws_sso_autologin.logger import get_logger

logger = get_logger(__name__)

TRAY_HOST_REQUIRED_MESSAGE = (
    "Tray host support is required. Start this app in a Linux session "
    "with a compatible StatusNotifier/system tray host."
)
NO_PROFILES_SUMMARY = "No SSO profiles detected"
MONITORING_START_FAILED_SUMMARY = "Monitoring startup failed"
TRAY_HOST_LOST_SUMMARY = "Tray host heartbeat lost"


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
    
    def __init__(self, args: Optional[List[str]] = None) -> None:
        """Initialize the autologin application.
        
        Args:
            args: Command line arguments (defaults to sys.argv)
        """
        self._args = args or sys.argv
        self._app: Optional[QApplication] = None
        self._tray: Optional[StatusTray] = None
        self._health_operator: Optional[HealthOperator] = None
        self._session_operator: Optional[SessionOperator] = None
        self._login_operator: Optional[LoginOperator] = None
        self._profiles: List[ProfileConfig] = []
        self._tray_host: Optional[TrayHost] = None
        self._tray_host_timer: Optional[QTimer] = None
        self._tray_host_loss_announced = False
        self._global_error_source: Optional[str] = None
        self._awaiting_initial_status = False
        self._is_shutting_down = False
        self._signal_shutdown_requested = False
        self._signal_handlers_installed = False
        self._previous_signal_handlers = {}
        self._force_exit = os._exit
        self._tray_loss_behavior = os.getenv(
            "AWS_SSO_AUTOLOGIN_TRAY_LOSS_BEHAVIOR", "pause"
        ).strip().lower()
        
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
            logger.warning("Tray host lost; continuing monitoring per tray-loss behavior")
            return

        if self._tray is not None:
            self._tray.set_monitoring_enabled(False)

        logger.error("Tray host lost; monitoring paused")

    def _set_tray_global_error(self, summary: str, details: str, source: str) -> None:
        if self._tray is None:
            return
        self._tray.set_global_error(summary=summary, details=details)
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
            # Connect health status changes to tray updates
            self._health_operator.set_status_callback(self._on_status_change)
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
            if session_info.seconds_remaining is None:
                return ProfileStatus(
                    profile_name=profile_name,
                    state=ProfileState.WARNING,
                    short_reason="Session remaining time unavailable",
                    diagnostics_summary="Session status warning",
                    diagnostics_details=self._build_diagnostics_details(session_info),
                )

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
                state=ProfileState.ERROR,
                short_reason="Command timed out",
                diagnostics_summary="Command timed out",
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
            self._tray.update_profile(status)
            if self._awaiting_initial_status:
                self._tray.set_syncing(False)
                self._awaiting_initial_status = False
            logger.debug(
                "AutologinApp: Status updated for %s: renewal=%s failure_type=%s",
                profile_name,
                renewal_status.value,
                session_info.failure_type.value,
            )

    def _on_toggle_monitoring(self, enabled: bool) -> None:
        """Handle first-row enable/disable action from tray menu."""
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

    def _on_show_diagnostics(self, summary: str, details: str) -> None:
        """Handle diagnostics action from tray menu."""
        logger.error("Diagnostics requested: %s", summary)
        if details:
            logger.debug("Diagnostics details: %s", details)
    
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
                config = ProfileConfig(
                    name=info.name,
                    sso_start_url=info.sso_start_url,
                    sso_region=info.sso_region,
                )
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
                details="No SSO profiles detected. Monitoring profile sources for changes.",
                source="startup-no-profiles",
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


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the application.
    
    Args:
        args: Command line arguments (defaults to sys.argv)
        
    Returns:
        Exit code
    """
    app = AutologinApp(args)
    
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
