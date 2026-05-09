"""Service module for tray host abstraction and environment detection."""

import json
import os
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from aws_sso_autologin.logger import get_logger

logger = get_logger(__name__)


class TrayHostType(Enum):
    """Enumeration of supported tray host types."""
    GNOME = "gnome"
    KDE = "kde"
    XFCE = "xfce"
    MATE = "mate"
    CINNAMON = "cinnamon"
    UNITY = "unity"
    PANTHEON = "pantheon"
    BUDGIE = "budgie"
    LXQT = "lxqt"
    GENERIC = "generic"
    UNKNOWN = "unknown"


@dataclass
class TrayHostInfo:
    """Information about the detected tray host environment.
    
    Attributes:
        host_type: The type of tray host detected
        name: Human-readable name of the tray host
        version: Optional version string of the tray host
        supports_status_notifier: Whether StatusNotifier is supported
        supports_xembed: Whether XEmbed is supported
    """
    host_type: TrayHostType
    name: str
    version: Optional[str] = None
    supports_status_notifier: bool = False
    supports_xembed: bool = False


class TrayHost(ABC):
    """Abstract interface for tray host operations.
    
    This abstract base class defines the interface for interacting with
    different system tray hosts. Concrete implementations handle the
    specifics of each desktop environment.
    """
    
    @abstractmethod
    def ping(self) -> bool:
        """Check if the tray host is responsive.
        
        Returns:
            True if the tray host responds to ping, False otherwise
        """
        pass
    
    @abstractmethod
    def get_info(self) -> TrayHostInfo:
        """Get information about the tray host.
        
        Returns:
            TrayHostInfo with details about the tray host
        """
        pass


# Mapping of desktop environment identifiers to tray host types
_DESKTOP_ENV_MAP = {
    # GNOME variants
    'gnome': TrayHostType.GNOME,
    'gnome-shell': TrayHostType.GNOME,
    'gnome-classic': TrayHostType.GNOME,
    'ubuntu': TrayHostType.GNOME,  # Ubuntu uses GNOME Shell
    
    # KDE variants
    'kde': TrayHostType.KDE,
    'plasma': TrayHostType.KDE,
    'kde-plasma': TrayHostType.KDE,
    
    # XFCE
    'xfce': TrayHostType.XFCE,
    'xfce4': TrayHostType.XFCE,
    'xfce-session': TrayHostType.XFCE,
    
    # MATE
    'mate': TrayHostType.MATE,
    'mate-session': TrayHostType.MATE,
    
    # Cinnamon
    'cinnamon': TrayHostType.CINNAMON,
    'cinnamon-session': TrayHostType.CINNAMON,
    
    # Unity
    'unity': TrayHostType.UNITY,
    'unity-session': TrayHostType.UNITY,
    
    # Pantheon (Elementary OS)
    'pantheon': TrayHostType.PANTHEON,
    'elementary': TrayHostType.PANTHEON,
    
    # Budgie
    'budgie': TrayHostType.BUDGIE,
    'budgie-desktop': TrayHostType.BUDGIE,
    
    # LXQt
    'lxqt': TrayHostType.LXQT,
    'lxqt-session': TrayHostType.LXQT,
}


def _detect_from_env_var(env_var: str) -> Optional[TrayHostType]:
    """Detect tray host type from an environment variable.
    
    Args:
        env_var: Name of the environment variable to check
        
    Returns:
        TrayHostType if detected, None otherwise
    """
    value = os.environ.get(env_var, '').lower()
    if not value:
        return None
    
    # Handle colon-separated values (e.g., "ubuntu:GNOME")
    for part in value.split(':'):
        part = part.strip().lower()
        if part in _DESKTOP_ENV_MAP:
            return _DESKTOP_ENV_MAP[part]
    
    return None


def detect_tray_host() -> TrayHostInfo:
    """Detect the current tray host environment.
    
    This function checks environment variables to determine which desktop
    environment is running and whether it supports system tray operations.
    
    Returns:
        TrayHostInfo with details about the detected tray host.
        Returns UNKNOWN type if no recognized environment is detected.
    """
    # Try DESKTOP_SESSION first
    host_type = _detect_from_env_var('DESKTOP_SESSION')
    
    # Fall back to XDG_CURRENT_DESKTOP
    if host_type is None:
        host_type = _detect_from_env_var('XDG_CURRENT_DESKTOP')
    
    # Check for StatusNotifier support (modern Linux desktops)
    if host_type is None:
        # No recognized desktop environment
        logger.debug("No recognized desktop environment detected")
        return TrayHostInfo(
            host_type=TrayHostType.UNKNOWN,
            name="Unknown Desktop Environment",
            supports_status_notifier=False,
            supports_xembed=False,
        )
    
    # Determine capabilities based on desktop type
    # Most modern Linux desktops support StatusNotifier
    supports_status_notifier = host_type in [
        TrayHostType.GNOME, TrayHostType.KDE, TrayHostType.XFCE,
        TrayHostType.MATE, TrayHostType.CINNAMON, TrayHostType.PANTHEON,
        TrayHostType.BUDGIE, TrayHostType.LXQT,
    ]
    
    # XEmbed is legacy support - fewer desktops support it now
    supports_xembed = host_type in [
        TrayHostType.XFCE, TrayHostType.MATE, TrayHostType.LXQT,
    ]
    
    # Get human-readable name
    host_names = {
        TrayHostType.GNOME: "GNOME Shell",
        TrayHostType.KDE: "KDE Plasma",
        TrayHostType.XFCE: "XFCE",
        TrayHostType.MATE: "MATE",
        TrayHostType.CINNAMON: "Cinnamon",
        TrayHostType.UNITY: "Unity",
        TrayHostType.PANTHEON: "Pantheon",
        TrayHostType.BUDGIE: "Budgie",
        TrayHostType.LXQT: "LXQt",
        TrayHostType.GENERIC: "Generic Desktop",
        TrayHostType.UNKNOWN: "Unknown",
    }
    
    info = TrayHostInfo(
        host_type=host_type,
        name=host_names.get(host_type, "Unknown"),
        supports_status_notifier=supports_status_notifier,
        supports_xembed=supports_xembed,
    )
    
    logger.debug(f"Detected tray host: {info.name} (StatusNotifier: {supports_status_notifier})")
    return info


def check_tray_host_available() -> bool:
    """Check if a compatible tray host is available.
    
    This function performs a preflight check to determine if the current
    desktop environment supports the required system tray functionality.
    
    Returns:
        True if a compatible tray host is detected, False otherwise.
    """
    info = detect_tray_host()
    
    # A tray host is available if:
    # 1. We detected a known desktop environment
    # 2. It supports at least one tray protocol (StatusNotifier or XEmbed)
    if info.host_type == TrayHostType.UNKNOWN:
        logger.warning("No compatible tray host detected")
        return False
    
    if not info.supports_status_notifier and not info.supports_xembed:
        logger.warning(f"Detected desktop {info.name} does not support required tray protocols")
        return False
    
    logger.debug(f"Compatible tray host available: {info.name}")
    return True


class ConcreteTrayHost(TrayHost):
    """Concrete implementation of TrayHost interface.
    
    This implementation provides actual tray host operations for the
    detected desktop environment.
    """
    
    def __init__(
        self,
        info: Optional[TrayHostInfo] = None,
        ping_runner: Optional[Callable[..., subprocess.CompletedProcess]] = None,
    ):
        """Initialize with tray host info.
        
        Args:
            info: TrayHostInfo instance. If None, detect_tray_host() is called.
        """
        self._info = info or detect_tray_host()
        self._last_ping_time: Optional[float] = None
        self._consecutive_failures = 0
        self._is_lost = False
        self._ping_runner = ping_runner or subprocess.run

    @property
    def consecutive_failures(self) -> int:
        """Current consecutive tray-host ping failure count."""
        return self._consecutive_failures

    @property
    def is_lost(self) -> bool:
        """Whether tray host is considered lost by failure threshold."""
        return self._is_lost
    
    def ping(self) -> bool:
        """Check if the tray host is responsive.

        Returns:
            True if tray-host D-Bus probe succeeds, False otherwise.
        """
        self._last_ping_time = time.time()
        command = [
            "dbus-send",
            "--session",
            "--dest=org.freedesktop.DBus",
            "--type=method_call",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus.ListNames",
        ]

        try:
            result = self._ping_runner(
                command,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                self._consecutive_failures = 0
                self._is_lost = False
                return True

            self._record_failure(result.stderr or "dbus probe failed")
            return False
        except Exception as exc:  # pragma: no cover - defensive
            self._record_failure(str(exc))
            return False

    def _record_failure(self, reason: str) -> None:
        self._consecutive_failures += 1
        logger.warning(
            "Tray host ping failed (%d consecutive): %s",
            self._consecutive_failures,
            reason,
        )

        if self._consecutive_failures < 3:
            return

        if not self._is_lost:
            payload = {
                "event": "tray_host_lost",
                "host": self._info.name,
                "consecutive_failures": self._consecutive_failures,
            }
            print(json.dumps(payload, sort_keys=True))
        self._is_lost = True
    
    def get_info(self) -> TrayHostInfo:
        """Get information about the tray host.
        
        Returns:
            TrayHostInfo with details about the tray host
        """
        return self._info


def create_tray_host() -> Optional[TrayHost]:
    """Create a TrayHost instance for the current environment.
    
    Returns:
        TrayHost instance if a compatible host is available, None otherwise.
    """
    if not check_tray_host_available():
        return None
    
    info = detect_tray_host()
    return ConcreteTrayHost(info)
