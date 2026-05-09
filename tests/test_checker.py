"""Tests for session checker classification behavior."""

import subprocess
from unittest.mock import MagicMock, patch

from aws_sso_autologin.checker import SessionChecker
from aws_sso_autologin.models import ProfileConfig, SessionFailureType


def test_checker_marks_expired_invalid_failure_type():
    checker = SessionChecker(cli_path="aws")
    profile = ProfileConfig(name="team-prod")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=255,
            stdout="",
            stderr="The SSO session associated with this profile has expired.",
        )
        info = checker.get_session_info(profile)

    assert info.is_active is False
    assert info.failure_type == SessionFailureType.EXPIRED_OR_INVALID


def test_checker_marks_other_failure_type_for_non_expiry_errors():
    checker = SessionChecker(cli_path="aws")
    profile = ProfileConfig(name="team-dev")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Could not connect to endpoint URL",
        )
        info = checker.get_session_info(profile)

    assert info.is_active is False
    assert info.failure_type == SessionFailureType.OTHER


def test_checker_marks_timeout_failure_type():
    checker = SessionChecker(cli_path="aws")
    profile = ProfileConfig(name="team-test")

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("aws", 10)):
        info = checker.get_session_info(profile)

    assert info.is_active is False
    assert info.failure_type == SessionFailureType.TIMEOUT
