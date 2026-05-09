"""Tests for constants module."""

from aws_sso_autologin.constants import (
    SESSION_DURATION_SECONDS,
    CHECK_INTERVAL_SECONDS,
    RENEWAL_THRESHOLD_PERCENT,
    RENEWAL_THRESHOLD_SECONDS,
    CLASSIFIER_MAX_TOKENS_PER_SAMPLE,
    CLASSIFIER_MAX_SAMPLES_PER_STREAM,
    CLASSIFIER_MAX_STREAMS,
    CLASSIFIER_MEMORY_KIB_PER_STREAM,
    CLASSIFIER_MEMORY_MIB_TOTAL,
    MAX_PROFILES_IN_ROOT_MENU,
    MAX_SUBMENU_PROFILES,
    MAX_TOTAL_PROFILES,
    TOOLTIP_THROTTLE_SECONDS,
    STATUS_WINDOW_REFRESH_MS,
    HEARTBEAT_TIMEOUT_SECONDS,
)
from aws_sso_autologin.errors import (
    AutologinError,
    TokenizationError,
    ClassificationError,
    CorpusError,
    OperatorError,
    AWSCliError,
    TrayHostError,
)


def test_session_duration_constant():
    assert SESSION_DURATION_SECONDS == 3600


def test_check_interval_constant():
    assert CHECK_INTERVAL_SECONDS == 30


def test_renewal_threshold_percent():
    assert RENEWAL_THRESHOLD_PERCENT == 0.5


def test_renewal_threshold_seconds():
    assert RENEWAL_THRESHOLD_SECONDS == 1800


def test_classifier_token_limits():
    assert CLASSIFIER_MAX_TOKENS_PER_SAMPLE == 64
    assert CLASSIFIER_MAX_SAMPLES_PER_STREAM == 768
    assert CLASSIFIER_MAX_STREAMS == 3


def test_classifier_memory_budget():
    # Verify memory calculations are reasonable (~48 KiB per stream)
    assert 40 <= CLASSIFIER_MEMORY_KIB_PER_STREAM <= 60
    # Verify total is consistent with per-stream × streams
    expected_total_mib = CLASSIFIER_MEMORY_KIB_PER_STREAM * CLASSIFIER_MAX_STREAMS / 1024
    assert CLASSIFIER_MEMORY_MIB_TOTAL == expected_total_mib


def test_profile_limits():
    assert MAX_PROFILES_IN_ROOT_MENU == 25
    assert MAX_SUBMENU_PROFILES == 25
    assert MAX_TOTAL_PROFILES == 100


def test_ui_timing_constants():
    assert TOOLTIP_THROTTLE_SECONDS == 5
    assert STATUS_WINDOW_REFRESH_MS == 1000
    assert HEARTBEAT_TIMEOUT_SECONDS == 300


def test_error_hierarchy():
    assert issubclass(TokenizationError, AutologinError)
    assert issubclass(ClassificationError, AutologinError)
    assert issubclass(CorpusError, AutologinError)
    assert issubclass(OperatorError, AutologinError)
    assert issubclass(AWSCliError, AutologinError)
    assert issubclass(TrayHostError, AutologinError)
