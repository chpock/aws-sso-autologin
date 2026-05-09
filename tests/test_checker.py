"""Tests for session checker classification behavior."""

from unittest.mock import MagicMock, patch

from aws_sso_autologin.checker import SessionChecker
from aws_sso_autologin.errors import AWSCliError
from aws_sso_autologin.models import ProfileConfig, SessionFailureType


def test_checker_marks_expired_invalid_failure_type():
    checker = SessionChecker(cli_path="aws")
    profile = ProfileConfig(name="team-prod")

    with patch("aws_sso_autologin.checker._run_subprocess_with_escalation") as mock_run:
        mock_run.return_value = (
            255,
            "",
            "The SSO session associated with this profile has expired.",
        )
        info = checker.get_session_info(profile)

    assert info.is_active is False
    assert info.failure_type == SessionFailureType.EXPIRED_OR_INVALID


def test_checker_marks_other_failure_type_for_non_expiry_errors():
    checker = SessionChecker(cli_path="aws")
    profile = ProfileConfig(name="team-dev")

    with patch("aws_sso_autologin.checker._run_subprocess_with_escalation") as mock_run:
        mock_run.return_value = (
            1,
            "",
            "Could not connect to endpoint URL",
        )
        info = checker.get_session_info(profile)

    assert info.is_active is False
    assert info.failure_type == SessionFailureType.OTHER


def test_checker_marks_timeout_failure_type():
    checker = SessionChecker(cli_path="aws")
    profile = ProfileConfig(name="team-test")

    with patch(
        "aws_sso_autologin.checker._run_subprocess_with_escalation",
        side_effect=AWSCliError("AWS command timed out after 10s and was terminated"),
    ):
        info = checker.get_session_info(profile)

    assert info.is_active is False
    assert info.failure_type == SessionFailureType.TIMEOUT
