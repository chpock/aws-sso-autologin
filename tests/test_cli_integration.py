"""
Integration tests for CLI with mode policy and watchdog.
"""

from unittest.mock import patch


class TestCLIIntegration:
    """Test CLI integrates mode policy correctly."""

    def test_check_only_flag_forces_safe_mode(self):
        """--check-only forces check-only mode regardless of context."""
        from aws_sso_autologin.mode_policy import ExecutionMode, get_execution_mode

        mode = get_execution_mode(cli_check_only=True)
        assert mode == ExecutionMode.CHECK_ONLY

    def test_no_flag_in_automation_uses_check_only(self):
        """No flag in automation context uses check-only."""
        import os

        with patch.dict(os.environ, {"CI": "true"}, clear=False):
            from aws_sso_autologin.mode_policy import ExecutionMode, get_execution_mode

            mode = get_execution_mode(cli_check_only=False)
            assert mode == ExecutionMode.CHECK_ONLY

    def test_no_flag_interactive_uses_normal(self):
        """No flag in interactive context uses normal mode."""
        import os

        # Clear automation vars completely to simulate interactive mode
        with patch.dict(os.environ, {}, clear=True):
            from aws_sso_autologin.mode_policy import ExecutionMode, get_execution_mode

            mode = get_execution_mode(cli_check_only=False)
            assert mode == ExecutionMode.NORMAL


class TestMainEntrypoint:
    """Test main entrypoint integrates watchdog."""

    def test_main_imports_watchdog(self):
        """Main module imports AutomationWatchdog for integration."""
        from aws_sso_autologin.__main__ import AutomationWatchdog
        from aws_sso_autologin.watchdog import AutomationWatchdog as RealWatchdog

        # Verify it's the same class
        assert AutomationWatchdog is RealWatchdog

    def test_main_entrypoint_exists(self):
        """Main entrypoint function exists for policy enforcement."""
        from aws_sso_autologin.__main__ import main_entrypoint

        # Verify function exists and is callable
        assert callable(main_entrypoint)

    def test_run_functions_exist(self):
        """Run mode functions exist for mode-based execution."""
        from aws_sso_autologin.__main__ import run_check_only, run_normal, run_with_mode

        # Verify functions exist and are callable
        assert callable(run_with_mode)
        assert callable(run_check_only)
        assert callable(run_normal)
