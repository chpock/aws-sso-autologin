"""Tests for AWS module."""

import os
import stat
import subprocess
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from aws_sso_autologin.aws import (
    ProfileInfo,
    SessionCheckResult,
    SessionStatus,
    check_session_valid,
    discover_profiles,
    run_sso_login,
)
from aws_sso_autologin.errors import AWSCliError


def test_check_session_valid_returns_tuple():
    from aws_sso_autologin.aws import check_session_valid

    result = check_session_valid("test-profile")
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_session_check_result_namedtuple():
    """Test SessionCheckResult is a named tuple with expected fields."""
    result = SessionCheckResult(
        is_valid=True,
        expires_at=datetime.now(),
        error_message=None,
    )
    assert result.is_valid is True
    assert result.expires_at is not None
    assert result.error_message is None


def test_profile_info_namedtuple():
    """Test ProfileInfo is a named tuple with expected fields."""
    profile = ProfileInfo(
        name="test-profile",
        is_sso=True,
        sso_start_url="https://example.com",
        sso_region="us-east-1",
    )
    assert profile.name == "test-profile"
    assert profile.is_sso is True
    assert profile.sso_start_url == "https://example.com"
    assert profile.sso_region == "us-east-1"


def test_session_status_enum():
    """Test SessionStatus enum has expected values."""
    assert SessionStatus.UNKNOWN.value == "unknown"
    assert SessionStatus.VALID.value == "valid"
    assert SessionStatus.EXPIRED.value == "expired"
    assert SessionStatus.INVALID.value == "invalid"
    assert SessionStatus.ERROR.value == "error"


def test_check_session_valid_returns_session_check_result():
    """Test check_session_valid returns SessionCheckResult fields."""
    result = check_session_valid("test-profile")
    assert len(result) == 3
    # Result should be (is_valid: bool, expires_at: Optional[datetime],"
    # error: Optional[str])
    assert isinstance(result[0], bool)
    # expires_at is either datetime or None
    assert result[1] is None or isinstance(result[1], datetime)
    # error is either str or None
    assert result[2] is None or isinstance(result[2], str)


def test_check_session_valid_with_invalid_profile():
    """Test check_session_valid handles non-existent profile."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("Profile not found")
        result = check_session_valid("nonexistent-profile")
        assert result[0] is False  # not valid
        assert result[2] is not None  # has error message


def test_run_sso_login_exists():
    """Test run_sso_login function exists and is callable."""
    from aws_sso_autologin.aws import run_sso_login

    assert callable(run_sso_login)


def test_discover_profiles_exists():
    """Test discover_profiles function exists and is callable."""
    from aws_sso_autologin.aws import discover_profiles

    assert callable(discover_profiles)


def test_discover_profiles_returns_list():
    """Test discover_profiles returns a list."""
    result = discover_profiles()
    assert isinstance(result, list)


def test_aws_cli_error_class():
    """Test AWSCliError can be raised and caught."""
    error = AWSCliError("Test AWS error")
    assert str(error) == "Test AWS error"
    assert isinstance(error, Exception)


def test_run_sso_login_accepts_profile():
    """Test run_sso_login accepts profile parameter."""
    with patch("aws_sso_autologin.aws._run_subprocess_with_escalation") as mock_run:
        mock_run.return_value = (0, "", "")
        run_sso_login("test-profile")
        mock_run.assert_called_once()
        command = mock_run.call_args.args[0]
        assert command[:4] == ["aws", "sso", "login", "--profile"]
        assert command[4] == "test-profile"


def test_check_session_valid_calls_aws_sts():
    """Test check_session_valid calls aws sts get-caller-identity."""
    with patch("aws_sso_autologin.aws._run_subprocess_with_escalation") as mock_run:
        mock_run.return_value = (
            0,
            '{"Account": "123456789", "Arn": "arn:aws:sts::123456789:assumed-role"'
            '":test"}',
            "",
        )
        check_session_valid("test-profile")
        mock_run.assert_called_once()
        command = mock_run.call_args.args[0]
        assert command[:3] == ["aws", "sts", "get-caller-identity"]


def test_discover_profiles_returns_profile_info():
    """Test discover_profiles returns list of ProfileInfo."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"profiles": [{"name": "test", "sso": true}]}',
            stderr="",
        )
        result = discover_profiles()
        assert isinstance(result, list)


def test_profile_info_defaults():
    """Test ProfileInfo has sensible defaults."""
    profile = ProfileInfo(name="test")
    assert profile.is_sso is False
    assert profile.sso_start_url is None
    assert profile.sso_region is None


def test_is_sso_profile_exists():
    """Test is_sso_profile function exists and is callable."""
    from aws_sso_autologin.aws import is_sso_profile

    assert callable(is_sso_profile)


def test_get_profile_sso_config_exists():
    """Test get_profile_sso_config function exists and is callable."""
    from aws_sso_autologin.aws import get_profile_sso_config

    assert callable(get_profile_sso_config)


def test_run_sso_login_browser_override_uses_secure_wrapper():
    wrapper_paths = []

    def fake_run(command, timeout=0, env=None):
        assert command[:4] == ["aws", "sso", "login", "--profile"]
        wrapper_path = env["BROWSER"]
        wrapper_paths.append(wrapper_path)
        assert os.path.exists(wrapper_path)
        mode = stat.S_IMODE(os.stat(wrapper_path).st_mode)
        assert mode == 0o700
        return (0, "", "")

    with patch(
        "aws_sso_autologin.aws._run_subprocess_with_escalation", side_effect=fake_run
    ):
        success, error = run_sso_login("test-profile", browser="firefox --new-window")

    assert success is True
    assert error == ""
    assert len(wrapper_paths) == 1
    assert not os.path.exists(wrapper_paths[0])


def test_run_sso_login_wrapper_failure_reports_diagnostics():
    def fake_run(command, timeout=0, env=None):
        return (126, "", "permission denied")

    with patch(
        "aws_sso_autologin.aws._run_subprocess_with_escalation", side_effect=fake_run
    ):
        success, error = run_sso_login("test-profile", browser="firefox")

    assert success is False
    assert "wrapper" in error.lower()
    assert "permissions" in error.lower()


def test_timeout_escalation_terminates_then_kills():
    from aws_sso_autologin.aws import _run_subprocess_with_escalation

    process = MagicMock()
    process.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd=["aws"], timeout=1),
        subprocess.TimeoutExpired(cmd=["aws"], timeout=3),
        ("", ""),
    ]

    with patch("subprocess.Popen", return_value=process):
        with pytest.raises(AWSCliError) as error:
            _run_subprocess_with_escalation(["aws", "sts"], timeout=1)

    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert "force kill" in str(error.value)


def test_run_aws_command_logs_failed_event_on_non_zero_exit():
    from aws_sso_autologin import aws

    with patch("aws_sso_autologin.aws._run_subprocess_with_escalation") as mock_run:
        mock_run.return_value = (1, "", "boom")
        with patch.object(aws.logger, "info") as mock_info:
            aws._run_aws_command(["sts", "get-caller-identity"], timeout=5)

    extra = mock_info.call_args.kwargs["extra"]
    assert extra["event"] == "aws_command_failed"
    assert extra["status"] == "failed"
    assert extra["command"] == ["aws", "sts", "get-caller-identity"]
    assert extra["exit_code"] == 1
