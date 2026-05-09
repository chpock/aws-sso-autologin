"""Session checker for AWS SSO."""

import logging
from typing import Optional

from aws_sso_autologin.aws import _run_subprocess_with_escalation
from aws_sso_autologin.models import ProfileConfig, SessionFailureType, SessionInfo

logger = logging.getLogger(__name__)


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
        try:
            # Try to get caller identity to check if session is active
            returncode, stdout, stderr = _run_subprocess_with_escalation(
                [self._cli_path, "sts", "get-caller-identity", "--profile", profile.name],
                timeout=10,
            )

            is_active = returncode == 0

            if is_active:
                # Try to get session expiration
                remaining = self._get_remaining_time(profile)
                return SessionInfo(
                    profile_name=profile.name,
                    is_active=True,
                    seconds_remaining=remaining,
                )

            error_text = (stderr or stdout or "").strip()
            failure_type = SessionFailureType.OTHER
            if self._is_expired_or_invalid_error(error_text):
                failure_type = SessionFailureType.EXPIRED_OR_INVALID

            return SessionInfo(
                profile_name=profile.name,
                is_active=False,
                seconds_remaining=0,
                failure_type=failure_type,
                error_message=error_text or "Session check failed",
            )

        except Exception as exc:
            message = str(exc)
            if "timed out" in message.lower():
                logger.warning(f"Timeout checking session for {profile.name}")
                return SessionInfo(
                    profile_name=profile.name,
                    is_active=False,
                    seconds_remaining=0,
                    failure_type=SessionFailureType.TIMEOUT,
                    error_message="Command timed out",
                )

            logger.error(f"Error checking session for {profile.name}: {exc}")
            return SessionInfo(
                profile_name=profile.name,
                is_active=False,
                seconds_remaining=None,
                failure_type=SessionFailureType.CHECK_ERROR,
                error_message=str(exc),
            )

    def _get_remaining_time(self, profile: ProfileConfig) -> Optional[int]:
        """Get remaining session time in seconds.

        Args:
            profile: Profile configuration.

        Returns:
            Seconds remaining or None if unknown.
        """
        # This is a simplified implementation
        # In reality, we'd parse the SSO token expiration
        try:
            # Try to get credentials expiration
            _run_subprocess_with_escalation(
                [
                    self._cli_path,
                    "configure",
                    "get",
                    "sso_role_name",
                    "--profile",
                    profile.name,
                ],
                timeout=10,
            )
            # For now, return a default value
            # In production, we'd parse the actual expiration
            return 3600  # Default 1 hour
        except Exception:
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
