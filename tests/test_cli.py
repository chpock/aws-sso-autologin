"""Tests for CLI executor behavior."""

from unittest.mock import patch

from aws_sso_autologin.cli import CLIExecutor


def test_execute_login_delegates_to_secure_runner_with_spec_timeout():
    executor = CLIExecutor()

    with patch("aws_sso_autologin.cli.run_sso_login", return_value=(True, "")) as mock_run:
        stdout, stderr, returncode = executor.execute_login("example")

    assert (stdout, stderr, returncode) == ("", "", 0)
    mock_run.assert_called_once_with(profile="example", browser=None, timeout=180)


def test_execute_login_maps_runner_failure_to_nonzero_returncode():
    executor = CLIExecutor()

    with patch(
        "aws_sso_autologin.cli.run_sso_login",
        return_value=(False, "wrapper execution failed"),
    ) as mock_run:
        stdout, stderr, returncode = executor.execute_login("example")

    assert stdout == ""
    assert stderr == "wrapper execution failed"
    assert returncode == 1
    mock_run.assert_called_once_with(profile="example", browser=None, timeout=180)
