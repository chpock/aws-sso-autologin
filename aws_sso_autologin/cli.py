"""CLI executor for AWS SSO commands."""

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class CLIExecutor:
    """Executes AWS CLI commands for SSO operations."""

    def __init__(self, cli_path: str = "aws") -> None:
        """Initialize the CLI executor.

        Args:
            cli_path: Path to the AWS CLI executable.
        """
        self._cli_path = cli_path

    def execute_login(self, profile_name: str) -> tuple[str, str, int]:
        """Execute AWS SSO login for a profile.

        Args:
            profile_name: Name of the profile to log in.

        Returns:
            Tuple of (stdout, stderr, returncode).
        """
        logger.info(f"Executing login for profile {profile_name}")

        try:
            result = subprocess.run(
                [self._cli_path, "sso", "login", "--profile", profile_name],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for login
            )

            return (result.stdout, result.stderr, result.returncode)

        except subprocess.TimeoutExpired:
            logger.error(f"Login timed out for profile {profile_name}")
            return ("", "Login timed out after 5 minutes", -1)
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
