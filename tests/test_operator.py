"""Tests for the operator module."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from aws_sso_autologin.models import ProfileConfig, RenewalStatus, SessionInfo
from aws_sso_autologin.operator import (
    CHECK_INTERVAL_SECONDS,
    HEARTBEAT_TIMEOUT_SECONDS,
    LOGIN_LOCK_SECONDS,
    RENEWAL_THRESHOLD_SECONDS,
    HealthOperator,
    LoginOperator,
    LoginResult,
    LoginStatus,
    SessionOperator,
)


# ==================== HealthOperator Tests ====================


def test_health_operator_init():
    """Test HealthOperator initialization."""
    from aws_sso_autologin.operator import HealthOperator

    operator = HealthOperator()
    assert operator is not None
    assert operator._profiles == []
    assert not operator._running


def test_health_operator_register_profiles():
    """Test registering profiles with HealthOperator."""
    operator = HealthOperator()
    profiles = [
        ProfileConfig(name="profile1"),
        ProfileConfig(name="profile2"),
    ]
    operator.register_profiles(profiles)
    assert operator._profiles == profiles


def test_health_operator_heartbeat_initial():
    """Test initial heartbeat state."""
    operator = HealthOperator()
    assert operator.is_heartbeat_valid()


def test_health_operator_heartbeat_expired():
    """Test heartbeat expiration."""
    operator = HealthOperator()
    # Simulate old heartbeat
    operator._last_heartbeat = time.time() - HEARTBEAT_TIMEOUT_SECONDS - 1
    assert not operator.is_heartbeat_valid()


def test_health_operator_heartbeat_valid():
    """Test valid heartbeat within timeout."""
    operator = HealthOperator()
    operator._last_heartbeat = time.time() - 60  # 1 minute ago
    assert operator.is_heartbeat_valid()


def test_health_operator_force_check():
    """Test forced check of all profiles."""
    mock_checker = MagicMock()
    mock_checker.get_session_info.return_value = SessionInfo(
        profile_name="test",
        is_active=True,
        seconds_remaining=3600,
    )

    operator = HealthOperator(checker=mock_checker)
    profiles = [ProfileConfig(name="profile1")]
    operator.register_profiles(profiles)

    with patch.object(operator._session_operator, "check_and_renew") as mock_check:
        mock_check.return_value = RenewalStatus.NOT_NEEDED
        results = operator.force_check()

    assert "profile1" in results
    assert results["profile1"] == RenewalStatus.NOT_NEEDED


def test_health_operator_set_status_callback():
    """Test setting status callback."""
    operator = HealthOperator()
    callback = MagicMock()
    operator.set_status_callback(callback)
    assert operator._on_status_change == callback


def test_health_operator_start_stop():
    """Test starting and stopping the operator."""
    operator = HealthOperator()

    with patch.object(operator, "_monitor_loop") as mock_loop:
        operator.start()
        assert operator._running
        operator.stop()
        assert not operator._running


# ==================== SessionOperator Tests ====================


def test_session_operator_init():
    """Test SessionOperator initialization."""
    operator = SessionOperator()
    assert operator is not None
    assert operator._checker is not None
    assert operator._login_operator is not None


def test_session_operator_check_and_renew_active_session():
    """Test check_and_renew with active session not needing renewal."""
    mock_checker = MagicMock()
    mock_checker.get_session_info.return_value = SessionInfo(
        profile_name="test",
        is_active=True,
        seconds_remaining=3600,  # 1 hour remaining
    )

    operator = SessionOperator(checker=mock_checker)
    profile = ProfileConfig(name="test")

    with patch.object(operator._login_operator, "enqueue") as mock_enqueue:
        status = operator.check_and_renew(profile)

    assert status == RenewalStatus.NOT_NEEDED
    mock_enqueue.assert_not_called()


def test_session_operator_check_and_renew_threshold():
    """Test check_and_renew when at threshold (50% = 30 min)."""
    mock_checker = MagicMock()
    mock_checker.get_session_info.return_value = SessionInfo(
        profile_name="test",
        is_active=True,
        seconds_remaining=RENEWAL_THRESHOLD_SECONDS,  # Exactly at threshold
    )

    operator = SessionOperator(checker=mock_checker)
    profile = ProfileConfig(name="test")

    with patch.object(operator._login_operator, "enqueue") as mock_enqueue:
        mock_enqueue.return_value = LoginStatus.PENDING
        status = operator.check_and_renew(profile)

    assert status == RenewalStatus.TRIGGERED
    mock_enqueue.assert_called_once_with("test")


def test_session_operator_check_and_renew_below_threshold():
    """Test check_and_renew when below threshold."""
    mock_checker = MagicMock()
    mock_checker.get_session_info.return_value = SessionInfo(
        profile_name="test",
        is_active=True,
        seconds_remaining=1000,  # Less than 30 min
    )

    operator = SessionOperator(checker=mock_checker)
    profile = ProfileConfig(name="test")

    with patch.object(operator._login_operator, "enqueue") as mock_enqueue:
        mock_enqueue.return_value = LoginStatus.PENDING
        status = operator.check_and_renew(profile)

    assert status == RenewalStatus.TRIGGERED
    mock_enqueue.assert_called_once_with("test")


def test_session_operator_check_and_renew_inactive():
    """Test check_and_renew with inactive session."""
    mock_checker = MagicMock()
    mock_checker.get_session_info.return_value = SessionInfo(
        profile_name="test",
        is_active=False,
        seconds_remaining=0,
    )

    operator = SessionOperator(checker=mock_checker)
    profile = ProfileConfig(name="test")

    with patch.object(operator._login_operator, "enqueue") as mock_enqueue:
        mock_enqueue.return_value = LoginStatus.PENDING
        status = operator.check_and_renew(profile)

    assert status == RenewalStatus.TRIGGERED
    mock_enqueue.assert_called_once_with("test")


def test_session_operator_check_and_renew_unknown_time():
    """Test check_and_renew when remaining time is unknown."""
    mock_checker = MagicMock()
    mock_checker.get_session_info.return_value = SessionInfo(
        profile_name="test",
        is_active=True,
        seconds_remaining=None,
    )

    operator = SessionOperator(checker=mock_checker)
    profile = ProfileConfig(name="test")

    with patch.object(operator._login_operator, "enqueue") as mock_enqueue:
        status = operator.check_and_renew(profile)

    assert status == RenewalStatus.UNKNOWN
    mock_enqueue.assert_not_called()


def test_session_operator_get_profiles_needing_renewal():
    """Test getting all profiles needing renewal."""
    mock_checker = MagicMock()
    mock_checker.get_session_info.side_effect = [
        SessionInfo("p1", True, 3600),  # Not needed
        SessionInfo("p2", True, 1000),  # Below threshold
        SessionInfo("p3", False, 0),  # Inactive
    ]

    operator = SessionOperator(checker=mock_checker)
    profiles = [
        ProfileConfig(name="p1"),
        ProfileConfig(name="p2"),
        ProfileConfig(name="p3"),
    ]

    needs_renewal = operator.get_all_profiles_needing_renewal(profiles)

    assert "p1" not in needs_renewal
    assert "p2" in needs_renewal
    assert "p3" in needs_renewal


# ==================== LoginOperator Tests ====================


def test_login_operator_init():
    """Test LoginOperator initialization."""
    operator = LoginOperator()
    assert operator is not None
    assert operator._queue == []
    assert not operator._processing


def test_login_operator_enqueue_new_profile():
    """Test enqueuing a new profile."""
    operator = LoginOperator()
    status = operator.enqueue("profile1")
    assert status == LoginStatus.PENDING
    assert "profile1" in operator._queue


def test_login_operator_enqueue_duplicate():
    """Test enqueuing same profile twice only adds once."""
    operator = LoginOperator()
    operator.enqueue("profile1")
    operator.enqueue("profile1")
    assert operator._queue.count("profile1") == 1


def test_login_operator_enqueue_locked():
    """Test enqueuing when profile is locked."""
    operator = LoginOperator()
    # Manually set lock
    operator._profile_locks["profile1"] = time.time()

    status = operator.enqueue("profile1")
    assert status == LoginStatus.LOCKED


def test_login_operator_profile_lock_expires():
    """Test that profile lock expires after 8 minutes."""
    operator = LoginOperator()
    # Set lock in the past (more than 8 minutes ago)
    operator._profile_locks["profile1"] = (
        time.time() - LOGIN_LOCK_SECONDS - 1
    )

    assert not operator._is_profile_locked("profile1")


def test_login_operator_profile_lock_valid():
    """Test that profile lock is valid within 8 minutes."""
    operator = LoginOperator()
    # Set lock recently
    operator._profile_locks["profile1"] = time.time() - 60  # 1 minute ago

    assert operator._is_profile_locked("profile1")


def test_login_operator_classify_success():
    """Test classifying successful login output."""
    operator = LoginOperator()
    status = operator._classify_output("Success", "", 0)
    assert status == LoginStatus.SUCCESS


def test_login_operator_classify_already_logged_in():
    """Test classifying 'already logged in' output."""
    operator = LoginOperator()
    status = operator._classify_output("", "You are already logged in", 1)
    assert status == LoginStatus.SUCCESS


def test_login_operator_classify_failure():
    """Test classifying failed login output."""
    operator = LoginOperator()
    status = operator._classify_output("", "Authentication failed", 1)
    assert status == LoginStatus.FAILURE


def test_login_operator_wait_for_completion_empty():
    """Test wait_for_completion when not processing."""
    operator = LoginOperator()
    result = operator.wait_for_completion(timeout=1)
    assert result is True


def test_login_operator_acquire_and_release_lock():
    """Test acquiring and releasing profile lock."""
    operator = LoginOperator()

    # Acquire lock
    acquired = operator._acquire_profile_lock("profile1")
    assert acquired is True
    assert "profile1" in operator._profile_locks

    # Try to acquire again (should fail)
    acquired = operator._acquire_profile_lock("profile1")
    assert acquired is False

    # Release lock
    operator._release_profile_lock("profile1")
    assert "profile1" not in operator._profile_locks


# ==================== Constants Tests ====================


def test_check_interval_constant():
    """Test that check interval is 30 seconds."""
    assert CHECK_INTERVAL_SECONDS == 30


def test_heartbeat_timeout_constant():
    """Test that heartbeat timeout is 5 minutes (300 seconds)."""
    assert HEARTBEAT_TIMEOUT_SECONDS == 300


def test_renewal_threshold_constant():
    """Test that renewal threshold is 30 minutes (1800 seconds)."""
    assert RENEWAL_THRESHOLD_SECONDS == 1800


def test_login_lock_constant():
    """Test that login lock is 8 minutes (480 seconds)."""
    assert LOGIN_LOCK_SECONDS == 480
