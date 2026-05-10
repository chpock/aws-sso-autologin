"""Tests for session checker classification behavior."""

from unittest.mock import patch

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


def test_checker_marks_permission_denied_failure_type():
    checker = SessionChecker(cli_path="aws")
    profile = ProfileConfig(name="team-sec")

    with patch("aws_sso_autologin.checker._run_subprocess_with_escalation") as mock_run:
        mock_run.return_value = (
            254,
            "",
            "AccessDenied: User is not authorized to perform sts:GetCallerIdentity",
        )
        info = checker.get_session_info(profile)

    assert info.is_active is False
    assert info.failure_type == SessionFailureType.PERMISSION_DENIED


def test_checker_emits_completed_event_for_active_session():
    from aws_sso_autologin import checker

    session_checker = SessionChecker(cli_path="aws")
    profile = ProfileConfig(name="team-active")

    with patch("aws_sso_autologin.checker._run_subprocess_with_escalation") as mock_run:
        mock_run.side_effect = [(0, "{}", ""), (0, "role", "")]
        with patch.object(checker.logger, "debug") as mock_debug:
            session_checker.get_session_info(profile)

    completed_calls = [
        call
        for call in mock_debug.call_args_list
        if call.kwargs.get("extra", {}).get("event") == "session_check_completed"
    ]
    assert completed_calls


def test_checker_emits_completed_event_for_inactive_session():
    from aws_sso_autologin import checker

    session_checker = SessionChecker(cli_path="aws")
    profile = ProfileConfig(name="team-inactive")

    with patch("aws_sso_autologin.checker._run_subprocess_with_escalation") as mock_run:
        mock_run.return_value = (255, "", "token has expired")
        with patch.object(checker.logger, "debug") as mock_debug:
            session_checker.get_session_info(profile)

    completed_calls = [
        call
        for call in mock_debug.call_args_list
        if call.kwargs.get("extra", {}).get("event") == "session_check_completed"
    ]
    assert completed_calls
