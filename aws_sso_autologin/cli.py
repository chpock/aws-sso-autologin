"""CLI executor for AWS SSO commands."""

import subprocess
from typing import Optional

from aws_sso_autologin.aws import run_sso_login
from aws_sso_autologin.constants import SSO_LOGIN_TIMEOUT_SECONDS
from aws_sso_autologin.logger import get_logger, sanitize_trace_payload

logger = get_logger(__name__)


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
        logger.info(
            "execute login requested",
            extra={"event": "login_execute_requested", "profile": profile_name, "timeout_s": timeout},
        )

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
            logger.error(
                "execute login failed",
                extra={"event": "login_execute_failed", "profile": profile_name, "error": str(e)},
            )
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
        command = [self._cli_path] + args
        logger.debug(
            "cli command started",
            extra={"event": "cli_command_started", "command": command, "timeout_s": timeout or 30},
        )
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout or 30,
            )
            stdout_payload = sanitize_trace_payload(result.stdout)
            stderr_payload = sanitize_trace_payload(result.stderr)
            logger.log(
                5,
                "cli command trace",
                extra={
                    "event": "cli_command_trace",
                    "command": command,
                    "stdout": stdout_payload["value"],
                    "stderr": stderr_payload["value"],
                    "stdout_payload_size_bytes": stdout_payload["payload_size_bytes"],
                    "stderr_payload_size_bytes": stderr_payload["payload_size_bytes"],
                    "stdout_payload_truncated": stdout_payload["payload_truncated"],
                    "stderr_payload_truncated": stderr_payload["payload_truncated"],
                    "stdout_redaction_applied": stdout_payload["redaction_applied"],
                    "stderr_redaction_applied": stderr_payload["redaction_applied"],
                    "stdout_detail_unavailable_reason": stdout_payload.get("detail_unavailable_reason"),
                    "stderr_detail_unavailable_reason": stderr_payload.get("detail_unavailable_reason"),
                    "exit_code": result.returncode,
                },
            )
            logger.debug(
                "cli command completed",
                extra={"event": "cli_command_completed", "status": "completed", "exit_code": result.returncode},
            )
            return (result.stdout, result.stderr, result.returncode)
        except subprocess.TimeoutExpired:
            logger.error(
                "cli command timeout",
                extra={"event": "cli_command_failed", "status": "failed", "reason": "timeout"},
            )
            return ("", "Command timed out", -1)
        except Exception as e:
            logger.error(
                "cli command failed",
                extra={"event": "cli_command_failed", "status": "failed", "error": str(e)},
            )
            return ("", str(e), -1)
