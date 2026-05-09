# tests/test_mode_policy.py
import os
import pytest
from aws_sso_autologin.mode_policy import (
    ExecutionMode,
    get_execution_mode,
    AutomationContext,
    get_automation_context,
)


class TestExecutionModeDetection:
    """Test simplified mode detection: --check-only flag or automation context."""
    
    def test_cli_check_only_flag_returns_check_mode(self):
        """--check-only CLI flag forces check mode regardless of context."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("CI", "true")
            mode = get_execution_mode(cli_check_only=True)
            assert mode == ExecutionMode.CHECK_ONLY
    
    def test_automation_context_defaults_to_check_mode(self):
        """CI environment defaults to check-only mode."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("CI", "true")
            mode = get_execution_mode(cli_check_only=False)
            assert mode == ExecutionMode.CHECK_ONLY
    
    def test_ai_agent_context_defaults_to_check_mode(self):
        """AI_AGENT environment defaults to check-only mode."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("AI_AGENT", "true")
            mode = get_execution_mode(cli_check_only=False)
            assert mode == ExecutionMode.CHECK_ONLY
    
    def test_pytest_context_defaults_to_check_mode(self):
        """PYTEST_CURRENT_TEST presence defaults to check-only mode."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("PYTEST_CURRENT_TEST", "tests/test_foo.py::test_bar")
            mode = get_execution_mode(cli_check_only=False)
            assert mode == ExecutionMode.CHECK_ONLY
    
    def test_interactive_context_allows_daemon_mode(self):
        """No automation signals allows normal (daemon) operation."""
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("CI", raising=False)
            mp.delenv("AI_AGENT", raising=False)
            mp.delenv("PYTEST_CURRENT_TEST", raising=False)
            mode = get_execution_mode(cli_check_only=False)
            assert mode == ExecutionMode.NORMAL


class TestAutomationContext:
    """Test automation context detection heuristics."""
    
    def test_ci_env_detected(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("CI", "true")
            ctx = get_automation_context()
            assert ctx.is_automation is True
            assert "CI" in ctx.detected_signals
    
    def test_ai_agent_env_detected(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("AI_AGENT", "true")
            ctx = get_automation_context()
            assert ctx.is_automation is True
            assert "AI_AGENT" in ctx.detected_signals
    
    def test_no_automation_signals_returns_false(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("CI", raising=False)
            mp.delenv("AI_AGENT", raising=False)
            mp.delenv("PYTEST_CURRENT_TEST", raising=False)
            ctx = get_automation_context()
            assert ctx.is_automation is False
