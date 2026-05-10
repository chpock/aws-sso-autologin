# tests/conftest.py
"""
Pytest configuration and fixtures for AWS SSO Autologin tests.

Provides daemon policy enforcement and test environment setup.
"""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "requires_daemon: mark test as requiring daemon/event loop"
        " (must include rationale docstring)",
    )


def pytest_collection_modifyitems(config, items):
    """
    Validate daemon test markers.

    Called after collection, before test execution.
    """
    for item in items:
        marker = item.get_closest_marker("requires_daemon")
        if marker is not None:
            # Validate rationale is present
            rationale = _extract_rationale(item)
            if not rationale:
                # Flag tests missing rationale
                item.add_marker(
                    pytest.mark.xfail(
                        reason=(
                            "Missing rationale: add docstring explaining"
                            " why daemon is required"
                        ),
                        run=False,
                    )
                )


def _extract_rationale(item) -> str:
    """
    Extract rationale from test function docstring.

    Returns:
        Rationale text if found, empty string otherwise.
    """
    if item.function.__doc__:
        doc = item.function.__doc__.strip()
        # Must have meaningful length to be considered a rationale
        if len(doc) > 20 and (
            "rationale" in doc.lower()
            or "requires" in doc.lower()
            or "test" in doc.lower()
        ):
            return doc
    return ""


@pytest.fixture(autouse=True)
def enforce_daemon_policy(request):
    """
    Auto-use fixture that sets up test environment.

    Ensures PYTEST_CURRENT_TEST is set so mode_policy detects automation context.
    """
    # PYTEST_CURRENT_TEST is automatically set by pytest
    # This fixture ensures any test-specific setup happens
    yield


@pytest.fixture
def mock_automation_context(monkeypatch):
    """Fixture to mock automation context for testing."""

    def _set_context(**env_vars):
        for key, value in env_vars.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)

    return _set_context
