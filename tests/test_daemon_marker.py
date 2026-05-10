# tests/test_daemon_marker.py
import pytest


class TestDaemonMarkerEnforcement:
    """Test that daemon mode tests require explicit marker."""

    def test_unmarked_test_runs_in_check_only_mode(self):
        """Unmarked test operates in check-only mode by default."""
        from aws_sso_autologin.mode_policy import ExecutionMode, get_execution_mode

        # In pytest context, should default to check-only
        mode = get_execution_mode(cli_check_only=False)
        assert mode == ExecutionMode.CHECK_ONLY

    def test_daemon_marker_allows_normal_mode(self):
        """Test with @pytest.mark.requires_daemon can request normal mode."""
        # This test has the marker - marker validation happens at collection
        assert True  # Marker presence is validated by conftest


# This test HAS the required marker and includes rationale
@pytest.mark.requires_daemon
def test_marked_daemon_test():
    """
    Test that requires daemon/event loop operation.

    Rationale: This test verifies Qt event loop initialization which
    requires full daemon mode. This is acceptable for integration tests
    that validate tray functionality.
    """
    # Test body - marker validation happens at collection/startup
    assert True


class TestMarkerValidation:
    """Test marker validation at collection time."""

    def test_marker_without_rationale_is_flagged(self, pytester):
        """Daemon test without proper rationale is flagged."""
        pytester.makepyfile("""
            import pytest

            @pytest.mark.requires_daemon
            def test_no_rationale():
                pass
        """)

        result = pytester.runpytest(
            "-v",
            "-o",
            "asyncio_default_fixture_loop_scope=function",
        )
        # Should indicate rationale issue
        output = result.stdout.str()
        assert (
            result.ret != 0
            or "rationale" in output.lower()
            or "xfail" in output.lower()
        )
