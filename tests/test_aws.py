"""Tests for AWS module."""

import logging
import os
import stat
import subprocess
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from aws_sso_autologin.aws import (
    ProfileInfo,
    discover_profiles,
    run_sso_login,
)
from aws_sso_autologin.errors import AWSCliError


def test_profile_info_namedtuple():
    """Test ProfileInfo is a named tuple with expected fields."""
    profile = ProfileInfo(
        name="test-profile",
        is_sso=True,
    )
    assert profile.name == "test-profile"
    assert profile.is_sso is True


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


def test_is_sso_profile_exists():
    """Test is_sso_profile function exists and is callable."""
    from aws_sso_autologin.aws import is_sso_profile

    assert callable(is_sso_profile)


def test_get_profile_sso_config_exists():
    """Test get_profile_sso_config function exists and is callable."""
    from aws_sso_autologin.aws import get_profile_sso_config

    assert callable(get_profile_sso_config)


def test_is_sso_profile_checks_sso_session_only():
    from aws_sso_autologin.aws import is_sso_profile

    with patch("aws_sso_autologin.aws._run_aws_command") as mock_run:
        mock_run.return_value = (0, "my-sso\n", "")

        assert is_sso_profile("test-profile") is True
        mock_run.assert_called_once_with(
            ["configure", "get", "sso_session", "--profile", "test-profile"],
            timeout=10,
            operation_context="check_sso_config",
        )


def test_get_profile_sso_config_reads_sso_values():
    from aws_sso_autologin.aws import get_profile_sso_config

    def side_effect(command, timeout=10, capture_output=True, operation_context=None):
        if command == ["configure", "get", "sso_session", "--profile", "test-profile"]:
            return (0, "my-sso\n", "")
        if command == [
            "configure",
            "get",
            "sso_account_id",
            "--profile",
            "test-profile",
        ]:
            return (0, "123456789012\n", "")
        if command == [
            "configure",
            "get",
            "sso_role_name",
            "--profile",
            "test-profile",
        ]:
            return (0, "ReadOnly\n", "")
        return (1, "", "")

    with patch("aws_sso_autologin.aws._run_aws_command", side_effect=side_effect):
        config = get_profile_sso_config("test-profile")

    assert config == {
        "session": "my-sso",
        "account_id": "123456789012",
        "role_name": "ReadOnly",
    }


def test_run_sso_login_browser_override_uses_secure_wrapper():
    wrapper_paths = []
    wrapper_scripts = []

    def fake_run(command, timeout=0, env=None, process_id=None):
        assert command[:4] == ["aws", "sso", "login", "--profile"]
        assert env is not None
        wrapper_path = env["BROWSER"]
        wrapper_paths.append(wrapper_path)
        assert os.path.exists(wrapper_path)
        with open(wrapper_path, encoding="utf-8") as handle:
            wrapper_scripts.append(handle.read())
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
    assert 'exec firefox --new-window "$@"' not in wrapper_scripts[0]
    assert (
        'nohup firefox --new-window "$@" </dev/null >/dev/null 2>&1 &'
        in wrapper_scripts[0]
    )
    assert "exit 0" in wrapper_scripts[0]
    assert not os.path.exists(wrapper_paths[0])


def test_run_sso_login_wrapper_failure_reports_diagnostics():
    def fake_run(command, timeout=0, env=None, process_id=None):
        return (126, "", "permission denied")

    with patch(
        "aws_sso_autologin.aws._run_subprocess_with_escalation", side_effect=fake_run
    ):
        success, error = run_sso_login("test-profile", browser="firefox")

    assert success is False
    assert "wrapper" in error.lower()
    assert "permissions" in error.lower()


def test_browser_wrapper_detaches_launched_process(tmp_path):
    from aws_sso_autologin.aws import _cleanup_browser_wrapper, _create_browser_wrapper

    marker_path = tmp_path / "started"
    done_path = tmp_path / "done"
    child_code = (
        "import pathlib, sys, time; "
        "pathlib.Path(sys.argv[1]).write_text('started'); "
        "time.sleep(1); "
        "pathlib.Path(sys.argv[2]).write_text('done')"
    )
    wrapper_path, wrapper_dir = _create_browser_wrapper(
        [sys.executable, "-c", child_code]
    )

    try:
        subprocess.run(
            [wrapper_path, str(marker_path), str(done_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )

        assert not done_path.exists()

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not done_path.exists():
            time.sleep(0.05)

        assert marker_path.read_text() == "started"
        assert done_path.read_text() == "done"
    finally:
        _cleanup_browser_wrapper(wrapper_path, wrapper_dir)


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


def test_timeout_logs_stdout_stderr_on_terminate(caplog):
    """Test stdout/stderr preview logging on timeout termination."""
    from aws_sso_autologin import aws

    caplog.set_level(logging.ERROR, logger="aws_sso_autologin.aws")
    process = MagicMock()
    process.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd=["aws"], timeout=1),
        ("stdout content", "stderr content"),
    ]

    with patch("aws_sso_autologin.aws._next_aws_process_id", return_value="timeout-a"):
        with patch("subprocess.Popen", return_value=process):
            with pytest.raises(AWSCliError):
                aws._run_subprocess_with_escalation(["aws", "sso", "login"], timeout=1)

    # Find the error log call for subprocess termination
    error_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "subprocess_failed"
    ]
    assert len(error_records) == 1

    record = error_records[0]
    assert record.name == "aws_sso_autologin.aws.timeout-a"
    assert record.reason == "timeout_terminated"
    # stdout_preview and stderr_preview should be logged (first 200 chars)
    assert record.stdout_preview == "stdout content"
    assert record.stderr_preview == "stderr content"


def test_timeout_force_kill_logs_stdout_stderr(caplog):
    """Test that stdout/stderr preview is logged when subprocess requires force kill."""
    from aws_sso_autologin import aws

    caplog.set_level(logging.ERROR, logger="aws_sso_autologin.aws")
    process = MagicMock()
    process.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd=["aws"], timeout=1),
        subprocess.TimeoutExpired(cmd=["aws"], timeout=3),
        ("stdout after kill", "stderr after kill"),
    ]

    with patch("aws_sso_autologin.aws._next_aws_process_id", return_value="timeout-b"):
        with patch("subprocess.Popen", return_value=process):
            with pytest.raises(AWSCliError):
                aws._run_subprocess_with_escalation(["aws", "sso", "login"], timeout=1)

    # Find the error log call for force kill
    error_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "subprocess_failed"
    ]
    assert len(error_records) == 1

    record = error_records[0]
    assert record.name == "aws_sso_autologin.aws.timeout-b"
    assert record.reason == "timeout_force_kill"
    # stdout_preview and stderr_preview should be logged (first 200 chars)
    assert record.stdout_preview == "stdout after kill"
    assert record.stderr_preview == "stderr after kill"


def test_run_aws_command_logs_failed_event_on_non_zero_exit(caplog):
    from aws_sso_autologin import aws

    caplog.set_level(logging.INFO, logger="aws_sso_autologin.aws")
    with patch("aws_sso_autologin.aws._run_subprocess_with_escalation") as mock_run:
        mock_run.return_value = (1, "", "boom")
        with patch(
            "aws_sso_autologin.aws._next_aws_process_id", return_value="failed-1"
        ):
            aws._run_aws_command(["sts", "get-caller-identity"], timeout=5)

    mock_run.assert_called_once_with(
        ["aws", "sts", "get-caller-identity"],
        timeout=5,
        env=None,
        process_id="failed-1",
    )
    failed_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "aws_command_failed"
    ]
    assert len(failed_records) == 1
    record = failed_records[0]
    assert record.name == "aws_sso_autologin.aws.failed-1"
    assert record.status == "failed"
    assert record.command == ["aws", "sts", "get-caller-identity"]
    assert record.exit_code == 1


def test_running_subprocess_logs_output_or_still_running_each_interval(caplog):
    from aws_sso_autologin import aws

    caplog.set_level(5, logger="aws_sso_autologin.aws")
    process = MagicMock()
    process.returncode = 0
    process.communicate.side_effect = [
        subprocess.TimeoutExpired(
            cmd=["aws"], timeout=1, output="first chunk", stderr=""
        ),
        subprocess.TimeoutExpired(
            cmd=["aws"], timeout=1, output="first chunk", stderr=""
        ),
        ("first chunk", "done"),
    ]

    with patch("aws_sso_autologin.aws._next_aws_process_id", return_value="trace-1"):
        with patch("subprocess.Popen", return_value=process):
            result = aws._run_subprocess_with_escalation(["aws", "sts"], timeout=3)

    assert result == (0, "first chunk", "done")

    process_records = [
        record
        for record in caplog.records
        if record.name == "aws_sso_autologin.aws.trace-1"
    ]
    running_output = [
        record
        for record in process_records
        if getattr(record, "event", None) == "subprocess_running_output"
    ]
    still_running = [
        record
        for record in process_records
        if getattr(record, "event", None) == "subprocess_still_running"
    ]

    assert len(running_output) == 2
    assert running_output[0].stdout == "first chunk"
    assert running_output[0].stderr == ""
    assert running_output[1].stdout == ""
    assert running_output[1].stderr == "done"
    assert len(still_running) == 1
    assert still_running[0].getMessage() == "<...still running...>"


def test_completed_subprocess_does_not_repeat_already_logged_output(caplog):
    from aws_sso_autologin import aws

    caplog.set_level(5, logger="aws_sso_autologin.aws")
    process = MagicMock()
    process.returncode = 0
    process.communicate.side_effect = [
        subprocess.TimeoutExpired(
            cmd=["aws"], timeout=1, output="already logged", stderr=""
        ),
        ("already logged", ""),
    ]

    with patch("aws_sso_autologin.aws._next_aws_process_id", return_value="trace-2"):
        with patch("subprocess.Popen", return_value=process):
            result = aws._run_subprocess_with_escalation(["aws", "sts"], timeout=2)

    assert result == (0, "already logged", "")

    running_output = [
        record
        for record in caplog.records
        if record.name == "aws_sso_autologin.aws.trace-2"
        and getattr(record, "event", None) == "subprocess_running_output"
    ]

    assert [record.stdout for record in running_output] == ["already logged"]
