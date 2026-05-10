"""Session checker for AWS SSO."""

import time

from aws_sso_autologin.aws import _run_aws_command
from aws_sso_autologin.logger import get_logger, sanitize_trace_payload
from aws_sso_autologin.models import ProfileConfig, SessionFailureType, SessionInfo

logger = get_logger(__name__)


class SessionChecker:
    """Checks AWS SSO session status using AWS CLI."""

    def __init__(self, cli_path: str = "aws") -> None:
        """Initialize the session checker.

        Args:
            cli_path: Path to the AWS CLI executable.
        """
        self._cli_path = cli_path

    def get_session_info(self, profile: ProfileConfig) -> SessionInfo:
        """Get session information for a profile.

        Args:
            profile: Profile configuration to check.

        Returns:
            SessionInfo with current session status.
        """
        logger.debug(
            "session check started",
            extra={"event": "session_check_started", "profile": profile.name},
        )
        try:
            # Try to get caller identity to check if session is active
            returncode, stdout, stderr = _run_aws_command(
                ["sts", "get-caller-identity", "--profile", profile.name],
                timeout=10,
                operation_context="validate_session",
            )

            is_active = returncode == 0
            stdout_payload = sanitize_trace_payload(stdout)
            stderr_payload = sanitize_trace_payload(stderr)
            logger.log(
                5,
                "session check command result",
                extra={
                    "event": "session_check_trace",
                    "profile": profile.name,
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

            if is_active:
                # Try to get session expiration
                remaining = self._get_remaining_time(profile)
                session_info = SessionInfo(
                    profile_name=profile.name,
                    is_active=True,
                    seconds_remaining=remaining,
                )
                logger.debug(
                    "session check completed",
                    extra={
                        "event": "session_check_completed",
                        "profile": profile.name,
                        "status": "active",
                        "seconds_remaining": remaining,
                    },
                )
                return session_info

            error_text = (stderr or stdout or "").strip()
            failure_type = SessionFailureType.OTHER
            if self._is_expired_or_invalid_error(error_text):
                failure_type = SessionFailureType.EXPIRED_OR_INVALID
            elif self._is_permission_denied_error(error_text):
                failure_type = SessionFailureType.PERMISSION_DENIED
            elif "timed out" in error_text.lower():
                failure_type = SessionFailureType.TIMEOUT

            session_info = SessionInfo(
                profile_name=profile.name,
                is_active=False,
                seconds_remaining=0,
                failure_type=failure_type,
                error_message=error_text or "Session check failed",
            )
            logger.debug(
                "session check completed",
                extra={
                    "event": "session_check_completed",
                    "profile": profile.name,
                    "status": "inactive",
                    "failure_type": failure_type.value,
                },
            )
            return session_info

        except Exception as exc:
            message = str(exc)
            if "timed out" in message.lower():
                logger.warning(
                    "session check timeout",
                    extra={
                        "event": "session_check_completed",
                        "profile": profile.name,
                        "status": "failed",
                        "reason": "timeout",
                    },
                )
                return SessionInfo(
                    profile_name=profile.name,
                    is_active=False,
                    seconds_remaining=0,
                    failure_type=SessionFailureType.TIMEOUT,
                    error_message="Command timed out",
                )

            logger.error(
                "session check error",
                extra={
                    "event": "session_check_completed",
                    "profile": profile.name,
                    "status": "failed",
                    "error": str(exc),
                },
            )
            return SessionInfo(
                profile_name=profile.name,
                is_active=False,
                seconds_remaining=None,
                failure_type=SessionFailureType.CHECK_ERROR,
                error_message=str(exc),
            )

    def _get_remaining_time(self, profile: ProfileConfig) -> int | None:
        """Get remaining session time in seconds.

        Args:
            profile: Profile configuration.

        Returns:
            Seconds remaining or None if unknown.
        """
        # This is a simplified implementation
        # In reality, we'd parse the SSO token expiration
        started_at = time.time()
        try:
            logger.debug(
                "session remaining time probe started",
                extra={
                    "event": "session_remaining_probe_started",
                    "profile": profile.name,
                },
            )
            # Try to get credentials expiration
            _run_aws_command(
                ["configure", "get", "sso_role_name", "--profile", profile.name],
                timeout=10,
                operation_context="check_sso_config",
            )
            # For now, return a default value
            # In production, we'd parse the actual expiration
            logger.debug(
                "session remaining time probe completed",
                extra={
                    "event": "session_remaining_probe_completed",
                    "profile": profile.name,
                    "status": "passed",
                    "seconds_remaining": 3600,
                    "duration_ms": int((time.time() - started_at) * 1000),
                },
            )
            return 3600  # Default 1 hour
        except Exception as exc:
            logger.debug(
                "session remaining time probe failed",
                extra={
                    "event": "session_remaining_probe_completed",
                    "profile": profile.name,
                    "status": "failed",
                    "error": str(exc),
                    "duration_ms": int((time.time() - started_at) * 1000),
                },
            )
            return None

    def is_session_valid(self, profile: ProfileConfig) -> bool:
        """Check if a session is currently valid.

        Args:
            profile: Profile configuration to check.

        Returns:
            True if session is valid, False otherwise.
        """
        info = self.get_session_info(profile)
        return info.is_active

    def _is_expired_or_invalid_error(self, error_message: str) -> bool:
        """Return True when CLI output explicitly indicates expired/invalid SSO."""
        if not error_message:
            return False

        lowered = error_message.lower()
        explicit_patterns = (
            "token has expired",
            "sso token has expired",
            "the sso session associated with this profile has expired",
            "session has expired",
            "expired token",
            "invalid_grant",
            "invalid grant",
            "invalid_request",
            "invalid request",
        )
        return any(pattern in lowered for pattern in explicit_patterns)

    def _is_permission_denied_error(self, error_message: str) -> bool:
        """Return True when output indicates profile permission denial."""
        if not error_message:
            return False

        lowered = error_message.lower()
        explicit_patterns = (
            "access denied",
            "accessdenied",
            "not authorized",
            "unauthorized",
            "forbidden",
        )
        return any(pattern in lowered for pattern in explicit_patterns)
