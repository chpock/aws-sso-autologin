"""Operator classes for managing SSO session lifecycle."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from aws_sso_autologin.checker import SessionChecker
from aws_sso_autologin.cli import CLIExecutor
from aws_sso_autologin.constants import (
    CHECK_INTERVAL_SECONDS,
    HEARTBEAT_TIMEOUT_SECONDS,
    LOGIN_LOCK_SECONDS,
)
from aws_sso_autologin.logger import get_logger, sanitize_trace_payload
from aws_sso_autologin.models import (
    ProfileConfig,
    RenewalStatus,
    SessionFailureType,
    SessionInfo,
)

logger = get_logger(__name__)


class LoginStatus(Enum):
    """Status of a login operation."""

    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    LOCKED = "locked"


@dataclass
class LoginResult:
    """Result of a login operation."""

    profile_name: str
    status: LoginStatus
    message: str
    timestamp: float


class LoginOperator:
    """Manages serial login queue with 5-minute lock per profile."""

    def __init__(self, cli_executor: CLIExecutor | None = None) -> None:
        """Initialize the login operator.

        Args:
            cli_executor: CLI executor for running aws sso login commands.
        """
        self._cli_executor = cli_executor or CLIExecutor()
        self._lock = threading.Lock()
        self._profile_locks: dict[str, float] = {}
        self._browser_overrides: dict[str, list[str]] = {}
        self._queue: list[str] = []
        self._processing = False
        self._worker_thread: threading.Thread | None = None

    def _is_profile_locked(self, profile_name: str) -> bool:
        """Check if a profile is currently locked.

        Must be called while holding self._lock.

        Args:
            profile_name: Name of the profile to check.

        Returns:
            True if the profile is locked, False otherwise.
        """
        if profile_name not in self._profile_locks:
            return False
        lock_time = self._profile_locks[profile_name]
        if time.time() - lock_time >= LOGIN_LOCK_SECONDS:
            # Lock has expired
            del self._profile_locks[profile_name]
            return False
        return True

    def _acquire_profile_lock(self, profile_name: str) -> bool:
        """Acquire a lock for a profile.

        Args:
            profile_name: Name of the profile to lock.

        Returns:
            True if lock was acquired, False if already locked.
        """
        with self._lock:
            if profile_name in self._profile_locks:
                lock_time = self._profile_locks[profile_name]
                if time.time() - lock_time < LOGIN_LOCK_SECONDS:
                    return False
            self._profile_locks[profile_name] = time.time()
            return True

    def _release_profile_lock(self, profile_name: str) -> None:
        """Release the lock for a profile.

        Args:
            profile_name: Name of the profile to unlock.
        """
        with self._lock:
            self._profile_locks.pop(profile_name, None)

    def enqueue(
        self,
        profile_name: str,
        browser: list[str] | None = None,
    ) -> LoginStatus:
        """Enqueue a profile for login.

        Args:
            profile_name: Name of the profile to log in.
            browser: Optional browser override command.

        Returns:
            Status indicating if the profile was queued or locked.
        """
        with self._lock:
            if self._is_profile_locked(profile_name):
                logger.info(
                    "login enqueue skipped for locked profile",
                    extra={
                        "event": "login_enqueue_skipped",
                        "profile": profile_name,
                        "reason": "profile_locked",
                    },
                )
                return LoginStatus.LOCKED
            if browser is not None:
                self._browser_overrides[profile_name] = browser
            if profile_name not in self._queue:
                self._queue.append(profile_name)
                logger.info(
                    "login enqueue accepted",
                    extra={
                        "event": "login_enqueued",
                        "profile": profile_name,
                        "queue_length": len(self._queue),
                    },
                )
            if not self._processing:
                self._start_worker()
            return LoginStatus.PENDING

    def _start_worker(self) -> None:
        """Start the background worker thread."""
        self._processing = True
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()

    def _process_queue(self) -> None:
        """Process the login queue serially."""
        while True:
            with self._lock:
                if not self._queue:
                    self._processing = False
                    break
                profile_name = self._queue.pop(0)

            # Process outside the lock to allow other operations
            self._process_login(profile_name)

    def _process_login(self, profile_name: str) -> LoginResult:
        """Process a single login operation.

        Args:
            profile_name: Name of the profile to log in.

        Returns:
            Result of the login operation.
        """
        if not self._acquire_profile_lock(profile_name):
            return LoginResult(
                profile_name=profile_name,
                status=LoginStatus.LOCKED,
                message="Profile is locked by another login attempt",
                timestamp=time.time(),
            )

        try:
            logger.info(
                "login processing started",
                extra={"event": "login_processing_started", "profile": profile_name},
            )
            browser = self._browser_overrides.get(profile_name)
            stdout, stderr, returncode = self._cli_executor.execute_login(
                profile_name, browser=browser
            )
            stdout_payload = sanitize_trace_payload(stdout)
            stderr_payload = sanitize_trace_payload(stderr)
            logger.log(
                5,
                "login execution trace",
                extra={
                    "event": "login_processing_trace",
                    "profile": profile_name,
                    "exit_code": returncode,
                    "stdout": stdout_payload["value"],
                    "stderr": stderr_payload["value"],
                    "stdout_payload_size_bytes": stdout_payload["payload_size_bytes"],
                    "stderr_payload_size_bytes": stderr_payload["payload_size_bytes"],
                    "stdout_payload_truncated": stdout_payload["payload_truncated"],
                    "stderr_payload_truncated": stderr_payload["payload_truncated"],
                    "stdout_redaction_applied": stdout_payload["redaction_applied"],
                    "stderr_redaction_applied": stderr_payload["redaction_applied"],
                    "stdout_detail_unavailable_reason": stdout_payload.get(
                        "detail_unavailable_reason"
                    ),
                    "stderr_detail_unavailable_reason": stderr_payload.get(
                        "detail_unavailable_reason"
                    ),
                },
            )

            status = self._classify_output(stdout, stderr, returncode)

            if status == LoginStatus.SUCCESS:
                message = f"Login successful for {profile_name}"
                logger.info(message)
            else:
                message = f"Login failed for {profile_name}: {stderr or stdout}"
                logger.error(message)

            return LoginResult(
                profile_name=profile_name,
                status=status,
                message=message,
                timestamp=time.time(),
            )

        finally:
            # Keep lock for LOGIN_LOCK_SECONDS to prevent immediate retry
            pass  # Lock will expire naturally

    def _classify_output(
        self, stdout: str, stderr: str, returncode: int
    ) -> LoginStatus:
        """Classify the output of a login command.

        Args:
            stdout: Standard output from the command.
            stderr: Standard error from the command.
            returncode: Return code from the command.

        Returns:
            Classified status of the login attempt.
        """
        if returncode == 0:
            return LoginStatus.SUCCESS

        error_text = (stderr or stdout or "").lower()

        if "already logged in" in error_text or "active session" in error_text:
            return LoginStatus.SUCCESS

        return LoginStatus.FAILURE

    def wait_for_completion(self, timeout: float | None = None) -> bool:
        """Wait for all queued logins to complete.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if queue completed, False if timeout reached.
        """
        if not self._processing:
            return True

        start_time = time.time()
        while self._processing:
            if timeout and (time.time() - start_time) >= timeout:
                return False
            time.sleep(0.1)
        return True


class SessionOperator:
    """Tracks sessions and queues renewal only on explicit expiry/invalidity."""

    def __init__(
        self,
        checker: SessionChecker | None = None,
        login_operator: LoginOperator | None = None,
    ) -> None:
        """Initialize the session operator.

        Args:
            checker: Session checker for getting session info.
            login_operator: Login operator for triggering renewals.
        """
        self._checker = checker or SessionChecker()
        self._login_operator = login_operator or LoginOperator()

    def check_and_renew(self, profile: ProfileConfig) -> RenewalStatus:
        """Check session and trigger renewal if needed.

        Args:
            profile: Profile configuration to check.

        Returns:
            Status of the renewal check.
        """
        info = self._checker.get_session_info(profile)
        return self.check_and_renew_with_info(profile, info)

    def check_and_renew_with_info(
        self,
        profile: ProfileConfig,
        info: SessionInfo,
    ) -> RenewalStatus:
        """Check session and trigger renewal using pre-fetched session info."""

        if not info.is_active:
            if info.failure_type == SessionFailureType.EXPIRED_OR_INVALID:
                logger.info(
                    "session %s classified as expired/invalid; triggering login",
                    profile.name,
                )
                self._login_operator.enqueue(profile.name, browser=profile.browser)
                return RenewalStatus.TRIGGERED

            logger.warning(
                "session %s inactive without explicit expired/invalid classification; "
                "skipping auto-login (failure_type=%s)",
                profile.name,
                info.failure_type.value,
            )
            return RenewalStatus.UNKNOWN

        return RenewalStatus.NOT_NEEDED

    def get_all_profiles_needing_renewal(
        self, profiles: list[ProfileConfig]
    ) -> list[str]:
        """Get list of profiles that need renewal.

        Args:
            profiles: List of profile configurations to check.

        Returns:
            List of profile names that need renewal.
        """
        needs_renewal = []
        for profile in profiles:
            info = self._checker.get_session_info(profile)
            if (
                not info.is_active
                and info.failure_type == SessionFailureType.EXPIRED_OR_INVALID
            ):
                needs_renewal.append(profile.name)
        return needs_renewal


class HealthOperator:
    """Monitors session health with 30-second checks and 5-minute heartbeat timeout."""

    def __init__(
        self,
        session_operator: SessionOperator | None = None,
        checker: SessionChecker | None = None,
    ) -> None:
        """Initialize the health operator.

        Args:
            session_operator: Session operator for triggering renewals.
            checker: Session checker for getting session info.
        """
        self._session_operator = session_operator or SessionOperator(checker=checker)
        self._checker = checker or SessionChecker()
        self._profiles: list[ProfileConfig] = []
        self._paused_profiles: set[str] = set()
        self._last_heartbeat: float = time.time()
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self._on_status_change: (
            Callable[[str, RenewalStatus, SessionInfo], None] | None
        ) = None

    def register_profiles(self, profiles: list[ProfileConfig]) -> None:
        """Register profiles to monitor.

        Args:
            profiles: List of profiles to monitor.
        """
        self._profiles = profiles
        active_names = {p.name for p in profiles}
        self._paused_profiles = {
            name for name in self._paused_profiles if name in active_names
        }

    def set_profile_monitoring_enabled(self, profile_name: str, enabled: bool) -> None:
        """Enable or disable checks for a single profile."""
        if enabled:
            self._paused_profiles.discard(profile_name)
        else:
            self._paused_profiles.add(profile_name)
        logger.info(
            "profile monitoring state changed",
            extra={
                "event": "profile_monitoring_state_changed",
                "profile": profile_name,
                "monitoring_enabled": enabled,
            },
        )

    def set_status_callback(
        self,
        callback: Callable[[str, RenewalStatus, SessionInfo], None],
    ) -> None:
        """Set callback for status changes.

        Args:
            callback: Function called with (profile_name, renewal_status, session_info).
        """
        self._on_status_change = callback

    def start(self) -> None:
        """Start the health monitoring loop."""
        if self._running:
            return

        self._running = True
        self._last_heartbeat = time.time()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("health monitor started")

    def stop(self) -> None:
        """Stop the health monitoring loop."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("health monitor stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop running every 30 seconds."""
        while self._running:
            self._check_all_profiles()
            self._update_heartbeat()

            # Sleep with periodic checks for shutdown
            slept = 0
            while slept < CHECK_INTERVAL_SECONDS and self._running:
                time.sleep(1)
                slept += 1

    def _check_all_profiles(self) -> None:
        """Check health of all registered profiles."""
        for profile in self._profiles:
            if profile.name in self._paused_profiles:
                logger.debug(
                    "profile health check skipped because profile monitoring is paused",
                    extra={
                        "event": "profile_health_check_skipped",
                        "profile": profile.name,
                        "reason": "profile_paused",
                    },
                )
                continue
            try:
                info = self._checker.get_session_info(profile)
                status = self._session_operator.check_and_renew_with_info(profile, info)
                self._emit_status(profile.name, status, info)

            except Exception as e:
                logger.error(
                    "profile health check failed",
                    extra={
                        "event": "profile_health_check_failed",
                        "profile": profile.name,
                        "error": str(e),
                    },
                )
                fallback_info = SessionInfo(
                    profile_name=profile.name,
                    is_active=False,
                    failure_type=SessionFailureType.CHECK_ERROR,
                    error_message=str(e),
                )
                self._emit_status(profile.name, RenewalStatus.UNKNOWN, fallback_info)

    def _emit_status(
        self,
        profile_name: str,
        status: RenewalStatus,
        info: SessionInfo,
    ) -> None:
        """Emit a status update without destabilizing the monitor loop."""
        if not self._on_status_change:
            return

        try:
            self._on_status_change(profile_name, status, info)
        except Exception as callback_exc:
            logger.error(
                "Status callback failed for %s: %s",
                profile_name,
                callback_exc,
            )

    def _update_heartbeat(self) -> None:
        """Update the heartbeat timestamp."""
        self._last_heartbeat = time.time()

    def is_heartbeat_valid(self) -> bool:
        """Check if the heartbeat is still valid (within timeout).

        Returns:
            True if heartbeat is within HEARTBEAT_TIMEOUT_SECONDS.
        """
        elapsed = time.time() - self._last_heartbeat
        return elapsed < HEARTBEAT_TIMEOUT_SECONDS

    def get_last_heartbeat(self) -> float:
        """Get the timestamp of the last heartbeat.

        Returns:
            Unix timestamp of last heartbeat.
        """
        return self._last_heartbeat

    def force_check(self) -> dict[str, RenewalStatus]:
        """Force an immediate check of all profiles.

        Returns:
            Dictionary mapping profile names to their renewal status.
        """
        results = {}
        for profile in self._profiles:
            if profile.name in self._paused_profiles:
                results[profile.name] = RenewalStatus.NOT_NEEDED
                continue
            try:
                status = self._session_operator.check_and_renew(profile)
                results[profile.name] = status
            except Exception as e:
                logger.error(
                    "forced profile check failed",
                    extra={
                        "event": "profile_force_check_failed",
                        "profile": profile.name,
                        "error": str(e),
                    },
                )
                results[profile.name] = RenewalStatus.UNKNOWN
        self._update_heartbeat()
        return results
