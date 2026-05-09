"""CLI executor for AWS SSO commands."""

import logging
import subprocess
from typing import Optional

from aws_sso_autologin.aws import run_sso_login
from aws_sso_autologin.constants import SSO_LOGIN_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class CLIExecutor:
    """Executes AWS CLI commands for SSO operations."""

    def __init__(self, cli_path: str = "aws") -> None:
        """Initialize the CLI executor.

        Args:
            cli_path: Path to the AWS CLI executable.
        """
        self._cli_path = cli_path

    def execute_login(
        self,
        profile_name: str,
        browser: Optional[str | list[str]] = None,
        timeout: int = SSO_LOGIN_TIMEOUT_SECONDS,
    ) -> tuple[str, str, int]:
        """Execute AWS SSO login for a profile.

        Args:
            profile_name: Name of the profile to log in.
            browser: Optional browser override command.
            timeout: Login timeout in seconds.

        Returns:
            Tuple of (stdout, stderr, returncode).
        """
        logger.info(f"Executing login for profile {profile_name}")

        try:
            success, error = run_sso_login(
                profile=profile_name,
                browser=browser,
                timeout=timeout,
            )
            if success:
                return ("", "", 0)
            return ("", error or "Login failed", 1)
        except Exception as e:
            logger.error(f"Error executing login for {profile_name}: {e}")
            return ("", str(e), -1)

    def execute_command(
        self, args: list[str], timeout: Optional[int] = None
    ) -> tuple[str, str, int]:
        """Execute a generic AWS CLI command.

        Args:
            args: Command arguments (without 'aws' prefix).
            timeout: Command timeout in seconds.

        Returns:
            Tuple of (stdout, stderr, returncode).
        """
        try:
            result = subprocess.run(
                [self._cli_path] + args,
                capture_output=True,
                text=True,
                timeout=timeout or 30,
            )
            return (result.stdout, result.stderr, result.returncode)
        except subprocess.TimeoutExpired:
            return ("", "Command timed out", -1)
        except Exception as e:
            return ("", str(e), -1)
