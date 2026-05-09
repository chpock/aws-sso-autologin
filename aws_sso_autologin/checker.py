"""Session checker for AWS SSO."""

import logging
import subprocess
from typing import Optional

from aws_sso_autologin.models import ProfileConfig, SessionInfo

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
            result = subprocess.run(
                [self._cli_path, "sts", "get-caller-identity", "--profile", profile.name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            is_active = result.returncode == 0

            if is_active:
                # Try to get session expiration
                remaining = self._get_remaining_time(profile)
                return SessionInfo(
                    profile_name=profile.name,
                    is_active=True,
                    seconds_remaining=remaining,
                )
            else:
                return SessionInfo(
                    profile_name=profile.name,
                    is_active=False,
                    seconds_remaining=0,
                )

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout checking session for {profile.name}")
            return SessionInfo(
                profile_name=profile.name,
                is_active=False,
                seconds_remaining=0,
            )
        except Exception as e:
            logger.error(f"Error checking session for {profile.name}: {e}")
            return SessionInfo(
                profile_name=profile.name,
                is_active=False,
                seconds_remaining=None,
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
            result = subprocess.run(
                [
                    self._cli_path,
                    "configure",
                    "get",
                    "sso_role_name",
                    "--profile",
                    profile.name,
                ],
                capture_output=True,
                text=True,
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
