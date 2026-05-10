# tests/test_watchdog.py
import time
from unittest.mock import patch

import pytest

from aws_sso_autologin.watchdog import AutomationWatchdog, WatchdogTimeout


class TestAutomationWatchdog:
    """Test watchdog timeout behavior for automation safety."""
    
    def test_watchdog_not_armed_outside_automation(self):
        """Watchdog does not arm when not in automation context."""
        with patch.dict("os.environ", {}, clear=True):
            watchdog = AutomationWatchdog(timeout_seconds=1)
            assert watchdog.is_armed is False
    
    def test_watchdog_arms_in_automation_context(self):
        """Watchdog arms automatically when CI/AI_AGENT detected."""
        with patch.dict("os.environ", {"CI": "true"}, clear=True):
            watchdog = AutomationWatchdog(timeout_seconds=60)
            assert watchdog.is_armed is True
    
    def test_watchdog_respects_explicit_disable_env(self):
        """AWS_SSO_AUTOLOGIN_WATCHDOG=0 disables watchdog even in automation."""
        with patch.dict("os.environ", {
            "CI": "true",
            "AWS_SSO_AUTOLOGIN_WATCHDOG": "0",
        }, clear=True):
            watchdog = AutomationWatchdog(timeout_seconds=60)
            assert watchdog.is_armed is False
    
    def test_watchdog_can_be_explicitly_enabled(self):
        """AWS_SSO_AUTOLOGIN_WATCHDOG=1 enables watchdog even outside automation."""
        with patch.dict("os.environ", {"AWS_SSO_AUTOLOGIN_WATCHDOG": "1"}, clear=True):
            watchdog = AutomationWatchdog(timeout_seconds=60)
            assert watchdog.is_armed is True
    
    def test_watchdog_timeout_value_from_env(self):
        """AWS_SSO_AUTOLOGIN_TIMEOUT overrides default timeout."""
        with patch.dict("os.environ", {
            "CI": "true",
            "AWS_SSO_AUTOLOGIN_TIMEOUT": "120",
        }, clear=True):
            watchdog = AutomationWatchdog()  # No explicit timeout
            assert watchdog.timeout_seconds == 120
    
    def test_watchdog_uses_default_timeout_when_env_not_set(self):
        """Default 60 second timeout used when no env override."""
        with patch.dict("os.environ", {"CI": "true"}, clear=True):
            watchdog = AutomationWatchdog()
            assert watchdog.timeout_seconds == 60
    
    def test_watchdog_raises_on_timeout(self):
        """Watchdog raises WatchdogTimeout when time expires."""
        with patch.dict("os.environ", {"CI": "true"}, clear=True):
            watchdog = AutomationWatchdog(timeout_seconds=0)  # Immediate timeout
            watchdog.arm()
            
            with pytest.raises(WatchdogTimeout):
                watchdog.check()  # Should raise immediately
    
    def test_watchdog_disarm_prevents_timeout(self):
        """Disarming watchdog prevents timeout exception."""
        with patch.dict("os.environ", {"CI": "true"}, clear=True):
            watchdog = AutomationWatchdog(timeout_seconds=0)
            watchdog.arm()
            watchdog.disarm()
            
            # Should not raise even with 0 timeout
            watchdog.check()
    
    def test_context_manager_arms_and_disarms(self):
        """Context manager properly arms on enter and disarms on exit."""
        with patch.dict("os.environ", {"CI": "true"}, clear=True):
            watchdog = AutomationWatchdog(timeout_seconds=60)
            
            with watchdog:
                assert watchdog.is_armed is True
            
            assert watchdog.is_armed is False


class TestWatchdogIntegration:
    """Integration tests for watchdog with real time tracking."""
    
    def test_watchdog_emits_structured_log_on_timeout(self, caplog):
        """Watchdog emits event=agent_watchdog_timeout on timeout."""
        import logging
        
        with patch.dict("os.environ", {"CI": "true"}, clear=True):
            caplog.set_level(logging.INFO)
            
            watchdog = AutomationWatchdog(timeout_seconds=0)
            
            with pytest.raises(WatchdogTimeout):
                with watchdog:
                    time.sleep(0.05)
                    watchdog.check()
            
            timeout_records = [
                r for r in caplog.records if getattr(r, "event", "") == "watchdog_timeout"
            ]
            assert timeout_records
            assert timeout_records[-1].__dict__.get("exit_code") == 124
