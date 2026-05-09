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
from datetime import datetime, timedelta
from enum import Enum
from typing import List, NamedTuple, Optional, Tuple

from aws_sso_autologin.constants import SESSION_DURATION_SECONDS
from aws_sso_autologin.errors import AWSCliError
from aws_sso_autologin.logger import get_logger

logger = get_logger(__name__)


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
    expires_at: Optional[datetime]
    error_message: Optional[str]


class ProfileInfo(NamedTuple):
    """Information about an AWS profile.
    
    Attributes:
        name: Profile name
        is_sso: Whether this is an SSO profile
        sso_start_url: SSO start URL (if SSO profile)
        sso_region: SSO region (if SSO profile)
    """
    name: str
    is_sso: bool = False
    sso_start_url: Optional[str] = None
    sso_region: Optional[str] = None


def _run_aws_command(
    command: List[str],
    timeout: int = 30,
    capture_output: bool = True,
) -> Tuple[int, str, str]:
    """Run an AWS CLI command with proper error handling.
    
    Args:
        command: Command arguments (without 'aws')
        timeout: Command timeout in seconds
        capture_output: Whether to capture stdout/stderr
        
    Returns:
        Tuple of (exit_code, stdout, stderr)
        
    Raises:
        AWSCliError: If command execution fails
    """
    full_command = ["aws"] + command
    
    try:
        logger.debug(f"Running AWS command: {' '.join(full_command)}")
        
        result = subprocess.run(
            full_command,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
        )
        
        stdout = result.stdout if result.stdout else ""
        stderr = result.stderr if result.stderr else ""
        
        if result.returncode != 0:
            logger.debug(f"AWS command failed with code {result.returncode}: {stderr[:200]}")
        
        return result.returncode, stdout, stderr
        
    except subprocess.TimeoutExpired:
        error_msg = f"AWS command timed out after {timeout}s"
        logger.error(error_msg)
        raise AWSCliError(error_msg)
    except FileNotFoundError:
        error_msg = "AWS CLI not found. Please ensure 'aws' is installed and in PATH"
        logger.error(error_msg)
        raise AWSCliError(error_msg)
    except Exception as e:
        error_msg = f"Failed to run AWS command: {e}"
        logger.error(error_msg)
        raise AWSCliError(error_msg)


def check_session_valid(profile: str) -> Tuple[bool, Optional[datetime], Optional[str]]:
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
        )
        
        if exit_code == 0:
            # Session is valid - parse response to get account info
            try:
                data = json.loads(stdout)
                account = data.get("Account", "unknown")
                arn = data.get("Arn", "unknown")
                logger.debug(f"Session valid for profile '{profile}': account={account}")
                
                # Estimate expiration as now + session duration
                # Note: Actual expiration may vary based on SSO configuration
                expires_at = datetime.now() + timedelta(seconds=SESSION_DURATION_SECONDS)
                
                return True, expires_at, None
            except json.JSONDecodeError:
                # Response wasn't valid JSON, but command succeeded
                logger.debug(f"Session valid for profile '{profile}' (non-JSON response)")
                expires_at = datetime.now() + timedelta(seconds=SESSION_DURATION_SECONDS)
                return True, expires_at, None
        else:
            # Session is invalid or expired
            error_msg = stderr.strip() if stderr else "Unknown error"
            logger.debug(f"Session invalid for profile '{profile}': {error_msg[:200]}")
            
            # Check if this is an SSO expiration error
            if _is_sso_expired_error(error_msg):
                return False, None, "SSO session expired"
            else:
                return False, None, error_msg
                
    except AWSCliError as e:
        logger.error(f"Failed to check session for profile '{profile}': {e}")
        return False, None, str(e)
    except Exception as e:
        logger.error(f"Unexpected error checking session for '{profile}': {e}")
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
    browser: Optional[str | list[str]] = None,
    timeout: int = 180,
) -> Tuple[bool, str]:
    """Run AWS SSO login for a profile.
    
    Args:
        profile: AWS profile name to log in
        browser: Optional browser command override
        timeout: Login timeout in seconds (default 3 minutes)
        
    Returns:
        Tuple of (success: bool, error_message: str)
    """
    wrapper_path: Optional[str] = None
    wrapper_dir: Optional[str] = None

    try:
        command = ["sso", "login", "--profile", profile]

        env = None
        if browser:
            env = os.environ.copy()
            wrapper_path, wrapper_dir = _create_browser_wrapper(browser)
            _validate_wrapper_path(wrapper_path)
            env["BROWSER"] = wrapper_path
            logger.debug("Using browser wrapper for profile '%s': %s", profile, wrapper_path)

        logger.info(f"Starting SSO login for profile '{profile}'")

        full_command = ["aws"] + command
        result = subprocess.run(
            full_command,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            logger.info(f"SSO login successful for profile '{profile}'")
            return True, ""

        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        if wrapper_path and result.returncode in (126, 127):
            metadata = _wrapper_metadata(wrapper_path)
            error_msg = (
                "Browser wrapper failed to execute. "
                f"{error_msg}. {metadata}"
            )

        logger.error(f"SSO login failed for profile '{profile}': {error_msg[:200]}")
        return False, error_msg

    except subprocess.TimeoutExpired:
        error_msg = f"SSO login timed out after {timeout}s"
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


def _cleanup_browser_wrapper(wrapper_path: Optional[str], wrapper_dir: Optional[str]) -> None:
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


def discover_profiles() -> List[ProfileInfo]:
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
            logger.error(f"Failed to list profiles: {stderr[:200]}")
            return profiles
        
        # Parse profile names (one per line)
        profile_names = [line.strip() for line in stdout.split("\n") if line.strip()]
        logger.debug(f"Found {len(profile_names)} AWS profiles")
        
        # Check each profile for SSO configuration
        for name in profile_names:
            try:
                profile_info = _get_profile_info(name)
                if profile_info:
                    profiles.append(profile_info)
            except Exception as e:
                logger.debug(f"Failed to get info for profile '{name}': {e}")
                continue
        
        logger.info(f"Discovered {len(profiles)} SSO profiles")
        return profiles
        
    except AWSCliError as e:
        logger.error(f"Failed to discover profiles: {e}")
        return profiles
    except Exception as e:
        logger.error(f"Unexpected error discovering profiles: {e}")
        return profiles


def _get_profile_info(profile_name: str) -> Optional[ProfileInfo]:
    """Get profile information, returning None if not an SSO profile.
    
    Args:
        profile_name: Name of the profile
        
    Returns:
        ProfileInfo if SSO profile, None otherwise
    """
    try:
        # Check if profile has SSO configuration
        exit_code, stdout, stderr = _run_aws_command(
            ["configure", "get", "sso_start_url", "--profile", profile_name],
            timeout=10,
        )
        
        if exit_code != 0 or not stdout.strip():
            # No SSO start URL, not an SSO profile
            return None
        
        sso_start_url = stdout.strip()
        
        # Get SSO region
        exit_code, stdout, _ = _run_aws_command(
            ["configure", "get", "sso_region", "--profile", profile_name],
            timeout=10,
        )
        sso_region = stdout.strip() if exit_code == 0 else None
        
        return ProfileInfo(
            name=profile_name,
            is_sso=True,
            sso_start_url=sso_start_url,
            sso_region=sso_region,
        )
        
    except Exception as e:
        logger.debug(f"Error checking profile '{profile_name}': {e}")
        return None


def is_sso_profile(profile_name: str) -> bool:
    """Check if a profile is configured for SSO.
    
    Args:
        profile_name: Name of the profile to check
        
    Returns:
        True if the profile has SSO configuration
    """
    try:
        exit_code, stdout, _ = _run_aws_command(
            ["configure", "get", "sso_start_url", "--profile", profile_name],
            timeout=10,
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
        # Get SSO start URL
        exit_code, stdout, _ = _run_aws_command(
            ["configure", "get", "sso_start_url", "--profile", profile_name],
            timeout=10,
        )
        if exit_code == 0:
            config["start_url"] = stdout.strip()
        
        # Get SSO region
        exit_code, stdout, _ = _run_aws_command(
            ["configure", "get", "sso_region", "--profile", profile_name],
            timeout=10,
        )
        if exit_code == 0:
            config["region"] = stdout.strip()
        
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
        logger.debug(f"Error getting SSO config for '{profile_name}': {e}")
    
    return config
