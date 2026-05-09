"""Main entry point for AWS SSO Autologin application."""

import sys
from datetime import datetime
from typing import Optional, List

from PySide6.QtWidgets import QApplication

from aws_sso_autologin.service import detect_tray_host, check_tray_host_available
from aws_sso_autologin.tray import ProfileState, ProfileStatus, StatusTray
from aws_sso_autologin.operator import HealthOperator, SessionOperator, LoginOperator
from aws_sso_autologin.models import ProfileConfig
from aws_sso_autologin.aws import discover_profiles
from aws_sso_autologin.logger import get_logger

logger = get_logger(__name__)

TRAY_HOST_REQUIRED_MESSAGE = (
    "Tray host support is required. Start this app in a Linux session "
    "with a compatible StatusNotifier/system tray host."
)


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
        if not check_tray_host_available():
            print(TRAY_HOST_REQUIRED_MESSAGE)
            logger.error("No compatible tray host detected")
            return False
        
        host_info = detect_tray_host()
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
    
    def _wire_signals(self) -> None:
        """Wire signals between components.
        
        Connects health operator status changes to tray updates.
        """
        if self._health_operator and self._tray:
            # Connect health status changes to tray updates
            self._health_operator.set_status_callback(self._on_status_change)
            logger.debug("AutologinApp: Signals wired")
    
    def _on_status_change(self, profile_name: str, is_healthy: bool) -> None:
        """Handle profile status changes.
        
        Args:
            profile_name: Name of the profile that changed
            is_healthy: True if the profile is healthy, False otherwise
        """
        if self._tray:
            # Create status update for tray
            status = ProfileStatus(
                profile_name=profile_name,
                state=ProfileState.OK if is_healthy else ProfileState.WARNING,
                short_reason=None if is_healthy else "Connectivity issue",
                last_login_time=datetime.now() if is_healthy else None,
            )
            self._tray.update_profile(status)
            logger.debug(f"AutologinApp: Status updated for {profile_name}: healthy={is_healthy}")

    def _on_toggle_monitoring(self, enabled: bool) -> None:
        """Handle first-row enable/disable action from tray menu."""
        if self._health_operator is None:
            return

        if enabled:
            self._health_operator.start()
            if self._tray is not None:
                self._tray.set_syncing(True)
            return

        self._health_operator.stop()
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
        
        # Detect tray host
        if not self._detect_tray_host():
            return 1
        
        # Create tray
        if not self._create_tray():
            return 1
        
        # Create operators
        if not self._create_operators():
            return 1
        
        # Wire signals
        self._wire_signals()
        
        # Load profiles
        if not self._load_profiles():
            if self._tray is not None:
                self._tray.set_global_error(
                    summary="Show startup/sync error",
                    details="No SSO profiles detected. Monitoring profile sources for changes.",
                )
            logger.error("No SSO profiles loaded; exiting")
            return 1

        # Start monitoring
        if not self._start_monitoring():
            if self._tray is not None:
                self._tray.set_global_error(
                    summary="Show startup/sync error",
                    details="Failed to start monitoring loop.",
                )
            logger.error("Health monitoring failed to start; exiting")
            return 1

        if self._tray is not None:
            self._tray.set_syncing(False)
        
        # Run Qt event loop
        logger.info("AutologinApp: Starting Qt event loop")
        return self._app.exec()
    
    def shutdown(self) -> None:
        """Shutdown the application and cleanup resources."""
        logger.info("AutologinApp: Shutting down")
        
        if self._health_operator:
            self._health_operator.stop()
        
        if self._tray:
            self._tray.close()
        
        if self._app:
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
        logger.info("Interrupted by user")
        app.shutdown()
        return 0
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
