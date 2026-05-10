"""AWS CLI integration module for SSO session management.

This module provides functions to interact with AWS CLI for:
- Checking SSO session validity
- Running SSO login
- Discovering AWS profiles
"""

import json
import os
import shlex
import stat
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import NamedTuple

from aws_sso_autologin.constants import SESSION_DURATION_SECONDS
from aws_sso_autologin.errors import AWSCliError
from aws_sso_autologin.logger import get_logger, sanitize_trace_payload

logger = get_logger(__name__)


def _run_subprocess_with_escalation(
    command: list[str],
    timeout: int,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run command with terminate->grace->kill timeout escalation."""
    started_at = time.time()
    logger.log(
        5,
        "subprocess started",
        extra={"event": "subprocess_started", "command": command, "timeout_s": timeout},
    )
    logger.log(
        5,
        "subprocess input trace",
        extra={
            "event": "subprocess_trace",
            "command": command,
            "timeout_s": timeout,
            "env_overridden": env is not None,
        },
    )
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout)
        stdout_payload = sanitize_trace_payload(stdout)
        stderr_payload = sanitize_trace_payload(stderr)
        logger.log(
            5,
            "subprocess output trace",
            extra={
                "event": "subprocess_trace",
                "command": command,
                "exit_code": process.returncode,
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
        logger.log(
            5,
            "subprocess completed",
            extra={
                "event": "subprocess_completed",
                "status": "completed",
                "command": command,
                "exit_code": process.returncode,
                "duration_ms": int((time.time() - started_at) * 1000),
            },
        )
        return process.returncode, stdout or "", stderr or ""
    except subprocess.TimeoutExpired:
        logger.warning(
            "subprocess timeout reached",
            extra={
                "event": "subprocess_timeout",
                "command": command,
                "timeout_s": timeout,
            },
        )
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=3)
            logger.error(
                "subprocess terminated after timeout",
                extra={
                    "event": "subprocess_failed",
                    "status": "failed",
                    "reason": "timeout_terminated",
                    "command": command,
                },
            )
            raise AWSCliError(
                f"AWS command timed out after {timeout}s and was terminated"
            )
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            logger.error(
                "subprocess force killed after timeout",
                extra={
                    "event": "subprocess_failed",
                    "status": "failed",
                    "reason": "timeout_force_kill",
                    "command": command,
                },
            )
            raise AWSCliError(
                f"AWS command timed out after {timeout}s and required force kill"
            )


class SessionStatus(Enum):
    """Session status values."""

    UNKNOWN = "unknown"
    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    ERROR = "error"


class SessionCheckResult(NamedTuple):
    """Result of a session validity check.

    Attributes:
        is_valid: Whether the session is currently valid
        expires_at: When the session expires (None if unknown/invalid)
        error_message: Error message if check failed, None otherwise
    """

    is_valid: bool
    expires_at: datetime | None
    error_message: str | None


class ProfileInfo(NamedTuple):
    """Information about an AWS profile.

    Attributes:
        name: Profile name
        is_sso: Whether this is an SSO profile
    """

    name: str
    is_sso: bool = False


def _run_aws_command(
    command: list[str],
    timeout: int = 30,
    capture_output: bool = True,
    operation_context: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run an AWS CLI command with proper error handling.

    Args:
        command: Command arguments (without 'aws')
        timeout: Command timeout in seconds
        capture_output: Whether to capture stdout/stderr
        operation_context: Description of what this command is doing
            (e.g., "check_sso_config", "validate_session", etc.)
        env: Optional environment variables to override for the subprocess

    Returns:
        Tuple of (exit_code, stdout, stderr)

    Raises:
        AWSCliError: If command execution fails
    """
    full_command = ["aws"] + command

    try:
        logger.debug(
            "aws command started",
            extra={
                "event": "aws_command_started",
                "command": full_command,
                "timeout_s": timeout,
                "operation_context": operation_context,
                "env_overridden": env is not None,
            },
        )

        returncode, stdout, stderr = _run_subprocess_with_escalation(
            full_command,
            timeout=timeout,
            env=env,
        )

        if returncode != 0:
            # For SSO config checks, non-zero exit means "not an SSO profile"
            # which is expected and not an error condition
            is_expected_failure = (
                operation_context == "check_sso_config"
                and "configure get sso_session" in " ".join(full_command)
            )

            if is_expected_failure:
                logger.info(
                    "profile is not an SSO profile (no sso_session configured)",
                    extra={
                        "event": "sso_config_check_negative",
                        "status": "not_sso_profile",
                        "command": full_command,
                        "exit_code": returncode,
                        "operation_context": operation_context,
                    },
                )
            else:
                logger.info(
                    "aws command finished with non-zero exit",
                    extra={
                        "event": "aws_command_failed",
                        "status": "failed",
                        "command": full_command,
                        "exit_code": returncode,
                        "stdout_preview": (stdout or "")[:200],
                        "stderr_preview": (stderr or "")[:200],
                        "operation_context": operation_context,
                    },
                )

        logger.debug(
            "aws command completed",
            extra={
                "event": "aws_command_completed",
                "status": "succeeded" if returncode == 0 else "failed",
                "exit_code": returncode,
                "operation_context": operation_context,
            },
        )

        return returncode, stdout, stderr

    except FileNotFoundError:
        error_msg = "AWS CLI not found. Please ensure 'aws' is installed and in PATH"
        logger.error(
            error_msg,
            extra={
                "event": "aws_command_failed",
                "status": "failed",
                "reason": "aws_cli_not_found",
            },
        )
        raise AWSCliError(error_msg)
    except Exception as e:
        error_msg = f"Failed to run AWS command: {e}"
        logger.error(
            error_msg,
            extra={"event": "aws_command_failed", "status": "failed", "error": str(e)},
        )
        raise AWSCliError(error_msg)


def check_session_valid(profile: str) -> tuple[bool, datetime | None, str | None]:
    """Check if an AWS SSO session is valid.

    Uses `aws sts get-caller-identity` to verify session validity.
    If the session is expired or invalid, the command will fail with
    an authorization error.

    Args:
        profile: AWS profile name to check

    Returns:
        Tuple of (is_valid: bool, expires_at: Optional[datetime], error: Optional[str])
        - is_valid: True if session is valid, False otherwise
        - expires_at: Estimated expiration time (now + 1 hour) if valid, None otherwise
        - error: Error message if check failed, None otherwise
    """
    try:
        exit_code, stdout, stderr = _run_aws_command(
            ["sts", "get-caller-identity", "--profile", profile],
            timeout=10,
            operation_context="validate_session",
        )

        if exit_code == 0:
            # Session is valid - parse response to get account info
            try:
                data = json.loads(stdout)
                account = data.get("Account", "unknown")
                arn = data.get("Arn", "unknown")
                logger.debug(
                    "session valid",
                    extra={
                        "event": "session_check_completed",
                        "profile": profile,
                        "status": "valid",
                        "account": account,
                        "arn": arn,
                    },
                )

                # Estimate expiration as now + session duration
                # Note: Actual expiration may vary based on SSO configuration
                expires_at = datetime.now() + timedelta(
                    seconds=SESSION_DURATION_SECONDS
                )

                return True, expires_at, None
            except json.JSONDecodeError:
                # Response wasn't valid JSON, but command succeeded
                logger.debug(
                    "session valid with non-json response",
                    extra={
                        "event": "session_check_completed",
                        "profile": profile,
                        "status": "valid",
                        "response_format": "non_json",
                    },
                )
                expires_at = datetime.now() + timedelta(
                    seconds=SESSION_DURATION_SECONDS
                )
                return True, expires_at, None
        else:
            # Session is invalid or expired
            error_msg = stderr.strip() if stderr else "Unknown error"
            logger.debug(
                "session invalid",
                extra={
                    "event": "session_check_completed",
                    "profile": profile,
                    "status": "invalid",
                    "error_preview": error_msg[:200],
                },
            )

            # Check if this is an SSO expiration error
            if _is_sso_expired_error(error_msg):
                return False, None, "SSO session expired"
            else:
                return False, None, error_msg

    except AWSCliError as e:
        logger.error(
            "session check failed",
            extra={
                "event": "session_check_completed",
                "profile": profile,
                "status": "failed",
                "error": str(e),
            },
        )
        return False, None, str(e)
    except Exception as e:
        logger.error(
            "session check failed with unexpected error",
            extra={
                "event": "session_check_completed",
                "profile": profile,
                "status": "failed",
                "error": str(e),
            },
        )
        return False, None, str(e)


def _is_sso_expired_error(error_message: str) -> bool:
    """Check if an error message indicates an expired SSO session.

    This function looks for common patterns in AWS CLI error messages
    that indicate an SSO session has expired.

    Args:
        error_message: The error message from AWS CLI

    Returns:
        True if the error indicates an expired SSO session
    """
    error_lower = error_message.lower()

    # Common SSO expiration error patterns
    expired_patterns = [
        "token has expired",
        "sso token has expired",
        "session has expired",
        "expired token",
        "unauthorizedexception",
        "invalidaccesskeyid",
        "signature expired",
        "request has expired",
        "credentials have expired",
        "unable to locate credentials",
        "no credentials found",
    ]

    return any(pattern in error_lower for pattern in expired_patterns)


def run_sso_login(
    profile: str,
    browser: str | list[str] | None = None,
    timeout: int = 180,
) -> tuple[bool, str]:
    """Run AWS SSO login for a profile.

    Args:
        profile: AWS profile name to log in
        browser: Optional browser command override
        timeout: Login timeout in seconds (default 3 minutes)

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    wrapper_path: str | None = None
    wrapper_dir: str | None = None

    try:
        command = ["sso", "login", "--profile", profile]

        env = None
        if browser:
            env = os.environ.copy()
            wrapper_path, wrapper_dir = _create_browser_wrapper(browser)
            _validate_wrapper_path(wrapper_path)
            env["BROWSER"] = wrapper_path
            logger.debug(
                "Using browser wrapper for profile '%s': %s", profile, wrapper_path
            )

        logger.info(
            "sso login started",
            extra={
                "event": "sso_login_started",
                "profile": profile,
                "timeout_s": timeout,
            },
        )

        returncode, stdout, stderr = _run_aws_command(
            command,
            timeout=timeout,
            operation_context="sso_login",
            env=env,
        )

        if returncode == 0:
            logger.info(
                "sso login completed",
                extra={
                    "event": "sso_login_completed",
                    "profile": profile,
                    "status": "succeeded",
                },
            )
            return True, ""

        error_msg = stderr.strip() if stderr else "Unknown error"
        if wrapper_path and returncode in (126, 127):
            metadata = _wrapper_metadata(wrapper_path)
            error_msg = f"Browser wrapper failed to execute. {error_msg}. {metadata}"

        logger.error(
            "sso login completed",
            extra={
                "event": "sso_login_completed",
                "profile": profile,
                "status": "failed",
                "error_preview": error_msg[:200],
            },
        )
        return False, error_msg

    except AWSCliError as error:
        error_msg = str(error)
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Failed to run SSO login: {e}"
        logger.error(error_msg)
        return False, error_msg
    finally:
        _cleanup_browser_wrapper(wrapper_path, wrapper_dir)


def _create_browser_wrapper(browser: str | list[str]) -> tuple[str, str]:
    """Create a secure executable wrapper script for browser override."""
    command = _normalize_browser_command(browser)
    if not command:
        raise AWSCliError("Browser override command is empty")

    wrapper_dir = tempfile.mkdtemp(prefix="aws-sso-browser-")
    wrapper_path = os.path.join(wrapper_dir, "browser-wrapper.sh")

    fd = os.open(wrapper_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o700)
    script_lines = [
        "#!/bin/sh",
        "exec " + " ".join(shlex.quote(arg) for arg in command) + ' "$@"',
        "",
    ]

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(script_lines))

    os.chmod(wrapper_path, 0o700)
    return wrapper_path, wrapper_dir


def _normalize_browser_command(browser: str | list[str]) -> list[str]:
    """Normalize browser override to argv list."""
    if isinstance(browser, str):
        return shlex.split(browser)
    return [str(part) for part in browser]


def _validate_wrapper_path(wrapper_path: str) -> None:
    """Reject symlink/race surprises before wrapper execution."""
    if os.path.islink(wrapper_path):
        raise AWSCliError("Browser wrapper path cannot be a symlink")

    stats = os.lstat(wrapper_path)
    if not stat.S_ISREG(stats.st_mode):
        raise AWSCliError("Browser wrapper path must be a regular file")

    mode = stat.S_IMODE(stats.st_mode)
    if mode != 0o700:
        raise AWSCliError(f"Browser wrapper permissions must be 0700, got {oct(mode)}")


def _wrapper_metadata(wrapper_path: str) -> str:
    """Return wrapper diagnostics metadata for execution failures."""
    try:
        stats = os.lstat(wrapper_path)
        mode = stat.S_IMODE(stats.st_mode)
        return (
            f"wrapper path={wrapper_path}, size={stats.st_size} bytes, "
            f"permissions={oct(mode)}"
        )
    except OSError:
        return f"wrapper path={wrapper_path}, permissions=unknown"


def _cleanup_browser_wrapper(wrapper_path: str | None, wrapper_dir: str | None) -> None:
    """Best-effort cleanup for wrapper file and temporary directory."""
    if wrapper_path:
        try:
            if os.path.exists(wrapper_path) or os.path.islink(wrapper_path):
                os.remove(wrapper_path)
        except OSError:
            logger.warning("Failed to remove browser wrapper: %s", wrapper_path)

    if wrapper_dir:
        try:
            os.rmdir(wrapper_dir)
        except OSError:
            logger.debug("Wrapper temp directory not removed: %s", wrapper_dir)


def discover_profiles() -> list[ProfileInfo]:
    """Discover AWS profiles from AWS config and credentials.

    Uses `aws configure list-profiles` to get all profiles, then
    filters to only SSO profiles.

    Returns:
        List of ProfileInfo for discovered profiles
    """
    profiles = []

    try:
        # Get list of all profile names
        exit_code, stdout, stderr = _run_aws_command(
            ["configure", "list-profiles"],
            timeout=20,
        )

        if exit_code != 0:
            logger.error(
                "profile discovery failed listing profiles",
                extra={
                    "event": "profile_discovery_failed",
                    "status": "failed",
                    "step": "list_profiles",
                    "error_preview": stderr[:200],
                },
            )
            return profiles

        # Parse profile names (one per line)
        profile_names = [line.strip() for line in stdout.split("\n") if line.strip()]
        logger.debug(
            "profile names discovered",
            extra={
                "event": "profile_discovery_names_found",
                "count": len(profile_names),
            },
        )

        # Check each profile for SSO configuration
        for name in profile_names:
            try:
                profile_info = _get_profile_info(name)
                if profile_info:
                    profiles.append(profile_info)
            except Exception as e:
                logger.debug(
                    "profile discovery skipped profile due to error",
                    extra={
                        "event": "profile_discovery_profile_skipped",
                        "profile": name,
                        "error": str(e),
                    },
                )
                continue

        logger.info(
            "profile discovery completed",
            extra={
                "event": "profile_discovery_completed",
                "status": "succeeded",
                "sso_profile_count": len(profiles),
            },
        )
        return profiles

    except AWSCliError as e:
        logger.error(
            "profile discovery failed",
            extra={
                "event": "profile_discovery_failed",
                "status": "failed",
                "error": str(e),
            },
        )
        return profiles
    except Exception as e:
        logger.error(
            "profile discovery failed with unexpected error",
            extra={
                "event": "profile_discovery_failed",
                "status": "failed",
                "error": str(e),
            },
        )
        return profiles


def _get_profile_info(profile_name: str) -> ProfileInfo | None:
    """Get profile information, returning None if not an SSO profile.

    Args:
        profile_name: Name of the profile

    Returns:
        ProfileInfo if SSO profile, None otherwise
    """
    try:
        # Check if profile has modern SSO configuration.
        # Non-zero exit means the profile is NOT an SSO profile.
        exit_code, stdout, stderr = _run_aws_command(
            ["configure", "get", "sso_session", "--profile", profile_name],
            timeout=10,
            operation_context="check_sso_config",
        )

        if exit_code != 0 or not stdout.strip():
            # No SSO session found - this profile is not configured for SSO
            # This is expected behavior for non-SSO profiles, not an error
            logger.info(
                "profile skipped - not an SSO profile",
                extra={
                    "event": "profile_discovery_skip",
                    "profile": profile_name,
                    "reason": "no_sso_session",
                    "exit_code": exit_code,
                    "has_output": bool(stdout.strip()),
                },
            )
            return None

        sso_session = stdout.strip()

        logger.debug(
            "profile identified as SSO profile",
            extra={
                "event": "profile_discovery_sso_found",
                "profile": profile_name,
                "sso_session": sso_session,
            },
        )

        return ProfileInfo(
            name=profile_name,
            is_sso=True,
        )

    except Exception as e:
        logger.debug(
            "profile sso info read failed",
            extra={
                "event": "profile_info_read_failed",
                "profile": profile_name,
                "error": str(e),
            },
        )
        return None


def is_sso_profile(profile_name: str) -> bool:
    """Check if a profile is configured for SSO.

    Args:
        profile_name: Name of the profile to check

    Returns:
        True if the profile has SSO configuration
    """
    try:
        # Non-zero exit means the profile does not have SSO configuration
        exit_code, stdout, _ = _run_aws_command(
            ["configure", "get", "sso_session", "--profile", profile_name],
            timeout=10,
            operation_context="check_sso_config",
        )

        return exit_code == 0 and bool(stdout.strip())

    except Exception:
        return False


def get_profile_sso_config(profile_name: str) -> dict:
    """Get SSO configuration for a profile.

    Args:
        profile_name: Name of the profile

    Returns:
        Dictionary with SSO configuration (start_url, region, account_id, role_name)
    """
    config = {}

    try:
        # Get SSO session name
        exit_code, stdout, _ = _run_aws_command(
            ["configure", "get", "sso_session", "--profile", profile_name],
            timeout=10,
        )
        if exit_code == 0 and stdout.strip():
            config["session"] = stdout.strip()

        # Get SSO account ID
        exit_code, stdout, _ = _run_aws_command(
            ["configure", "get", "sso_account_id", "--profile", profile_name],
            timeout=10,
        )
        if exit_code == 0:
            config["account_id"] = stdout.strip()

        # Get SSO role name
        exit_code, stdout, _ = _run_aws_command(
            ["configure", "get", "sso_role_name", "--profile", profile_name],
            timeout=10,
        )
        if exit_code == 0:
            config["role_name"] = stdout.strip()

    except Exception as e:
        logger.debug(
            "profile sso config read failed",
            extra={
                "event": "profile_sso_config_failed",
                "profile": profile_name,
                "error": str(e),
            },
        )

    return config
