# aws_sso_autologin/watchdog.py
"""
Automation watchdog for preventing AI agent hangs.

Provides timeout enforcement for long-running operations in automation
contexts, with structured logging for observability.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional
import time

logger = logging.getLogger(__name__)


class WatchdogTimeout(Exception):
    """Raised when automation watchdog detects timeout condition."""
    
    def __init__(self, timeout_seconds: int, message: Optional[str] = None):
        self.timeout_seconds = timeout_seconds
        self.message = message or (
            f"Automation run exceeded {timeout_seconds}s timeout and was "
            f"terminated safely."
        )
        super().__init__(self.message)


@dataclass
class WatchdogConfig:
    """Configuration for automation watchdog."""
    timeout_seconds: int
    enabled: bool
    automation_detected: bool


def get_watchdog_config() -> WatchdogConfig:
    """
    Determine watchdog configuration from environment.
    
    Returns:
        WatchdogConfig with resolved settings.
    """
    # Check for explicit watchdog enable/disable
    watchdog_env = os.environ.get("AWS_SSO_AUTOLOGIN_WATCHDOG", "").strip().lower()
    
    # Check for automation signals
    automation_signals = [
        os.environ.get("CI"),
        os.environ.get("AI_AGENT"),
        os.environ.get("PYTEST_CURRENT_TEST"),
    ]
    automation_detected = any(automation_signals)
    
    # Determine if watchdog should be enabled
    if watchdog_env in ("0", "false", "no"):
        enabled = False
    elif watchdog_env in ("1", "true", "yes"):
        enabled = True
    else:
        # Default: enabled in automation, disabled otherwise
        enabled = automation_detected
    
    # Get timeout value (default 60s, overridable via env)
    try:
        timeout = int(os.environ.get("AWS_SSO_AUTOLOGIN_TIMEOUT", "60"))
    except ValueError:
        timeout = 60
    
    # Enforce minimum timeout of 5 seconds to prevent accidental immediate kills
    timeout = max(timeout, 5)
    
    config = WatchdogConfig(
        timeout_seconds=timeout,
        enabled=enabled,
        automation_detected=automation_detected,
    )
    logger.debug(
        "watchdog config resolved",
        extra={
            "event": "watchdog_config_resolved",
            "enabled": config.enabled,
            "timeout_s": config.timeout_seconds,
            "automation_detected": config.automation_detected,
        },
    )
    return config


class AutomationWatchdog:
    """
    Watchdog timer for preventing automation hangs.
    
    Usage:
        watchdog = AutomationWatchdog(timeout_seconds=60)
        with watchdog:
            # Your long-running code here
            pass  # Watchdog auto-disarms on exit
    """
    
    def __init__(self, timeout_seconds: Optional[int] = None):
        """Initialize watchdog with configuration from environment."""
        config = get_watchdog_config()
        
        self._enabled = config.enabled
        self._timeout_seconds = timeout_seconds if timeout_seconds is not None else config.timeout_seconds
        self._automation_detected = config.automation_detected
        
        self._armed = False
        self._start_time: Optional[float] = None
        self._timeout_triggered = False
        
        # Auto-arm if enabled (arms automatically in automation contexts)
        if self._enabled:
            self.arm()
    
    @property
    def is_armed(self) -> bool:
        """Whether watchdog is currently armed and monitoring."""
        return self._armed
    
    @property
    def timeout_seconds(self) -> int:
        """Current timeout value in seconds."""
        return self._timeout_seconds
    
    def arm(self) -> None:
        """Arm the watchdog if enabled in current context."""
        if not self._enabled:
            logger.debug(
                "watchdog arm skipped",
                extra={"event": "watchdog_arm_skipped", "reason": "disabled"},
            )
            return
        
        if self._armed:
            logger.warning(
                "watchdog arm skipped",
                extra={"event": "watchdog_arm_skipped", "reason": "already_armed"},
            )
            return
        
        self._armed = True
        self._start_time = time.time()
        self._timeout_triggered = False
        
        logger.info(
            "watchdog armed",
            extra={
                "event": "watchdog_started",
                "timeout_s": self._timeout_seconds,
                "automation_detected": self._automation_detected,
            },
        )
    
    def disarm(self) -> None:
        """Disarm the watchdog, canceling any pending timeout."""
        if not self._armed:
            return
        
        elapsed = time.time() - self._start_time if self._start_time else 0
        self._armed = False
        
        logger.info(
            "watchdog disarmed",
            extra={
                "event": "watchdog_disarmed",
                "elapsed_s": round(elapsed, 1),
                "timeout_triggered": self._timeout_triggered,
            },
        )
    
    def check(self) -> None:
        """
        Check if watchdog timeout has occurred.
        
        Raises:
            WatchdogTimeout: If timeout has elapsed since arming.
        """
        if not self._armed or self._start_time is None:
            return
        
        elapsed = time.time() - self._start_time
        
        if elapsed >= self._timeout_seconds:
            self._timeout_triggered = True
            self._emit_timeout_event(elapsed)
            raise WatchdogTimeout(
                timeout_seconds=self._timeout_seconds,
                message=(
                    f"Automation run exceeded {self._timeout_seconds}s timeout "
                    f"(elapsed: {elapsed:.1f}s) and was terminated safely."
                )
            )
    
    def _emit_timeout_event(self, elapsed: float) -> None:
        """Emit structured timeout event for observability."""
        logger.error(
            "event=agent_watchdog_timeout exit_code=124 watchdog timeout",
            extra={
                "event": "watchdog_timeout",
                "timeout_s": self._timeout_seconds,
                "elapsed_s": round(elapsed, 1),
                "exit_code": 124,
                "reason": "automation_timeout",
                "status": "failed",
            },
        )
    
    def __enter__(self) -> "AutomationWatchdog":
        """Context manager entry - arms the watchdog."""
        self.arm()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - disarms the watchdog."""
        self.disarm()
