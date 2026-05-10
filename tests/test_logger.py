"""Tests for logger module."""

import json
import logging
import sys

import pytest

from aws_sso_autologin import logger as logger_module
from aws_sso_autologin.logger import (
    configure_logging,
    get_logger,
    install_qt_message_handler,
    sanitize_trace_payload,
    set_debug_mode,
)


def test_get_logger_returns_logger():
    logger = get_logger("test_module")
    assert logger.name == "test_module"
    assert isinstance(logger, logging.Logger)


def test_get_logger_sets_level():
    logger = get_logger("test_level", level=logging.DEBUG)
    assert logger.level == logging.DEBUG


def test_logger_has_handler():
    logger = get_logger("test_handler")
    assert len(logger.handlers) > 0
    assert isinstance(logger.handlers[0], logging.StreamHandler)
    assert logger.handlers[0].stream is sys.stdout


def test_set_debug_mode():
    logger = get_logger("test_debug", level=logging.INFO)
    set_debug_mode(True)
    assert logger.level == logging.DEBUG
    set_debug_mode(False)
    assert logger.level == logging.INFO


def test_logger_uses_structured_json_formatter():
    configure_logging(level_name="info", log_format="json")
    logger = get_logger("test_structured")
    formatter = logger.handlers[0].formatter
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn="test.py",
        lno=1,
        msg="structured message",
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))
    assert payload["logger"] == "test_structured"
    assert payload["level"] == "INFO"
    assert payload["message"] == "structured message"
    assert "timestamp" in payload


def test_logger_includes_extra_fields_in_json_payload():
    configure_logging(level_name="info", log_format="json")
    logger = get_logger("test_extra")
    formatter = logger.handlers[0].formatter
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn="test.py",
        lno=1,
        msg="extra fields",
        args=(),
        exc_info=None,
        extra={"event": "tray_host_lost", "host": "GNOME"},
    )

    payload = json.loads(formatter.format(record))
    assert payload["event"] == "tray_host_lost"
    assert payload["host"] == "GNOME"


def test_configure_logging_sets_trace_level():
    configure_logging(level_name="trace", log_format="json")
    logger = get_logger("test_trace")
    assert logger.level == 5


def test_configure_logging_uses_text_formatter_by_default():
    configure_logging(level_name="info", log_format="text")
    logger = get_logger("test_text")
    formatter_name = logger.handlers[0].formatter.__class__.__name__
    assert formatter_name == "TextFormatter"


def test_text_formatter_includes_extra_fields():
    configure_logging(level_name="info", log_format="text")
    logger = get_logger("test_text_extra")
    formatter = logger.handlers[0].formatter
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn="test.py",
        lno=1,
        msg="test message",
        args=(),
        exc_info=None,
        extra={"profile": "my-profile", "user_id": "12345"},
    )

    formatted = formatter.format(record)
    assert "test message" in formatted
    assert "profile=my-profile" in formatted
    assert "user_id=12345" in formatted


def test_text_formatter_excludes_technical_metadata():
    """Technical metadata from trace-level logging should not appear in text output."""
    configure_logging(level_name="info", log_format="text")
    logger = get_logger("test_text_filter")
    formatter = logger.handlers[0].formatter
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn="test.py",
        lno=1,
        msg="command executed",
        args=(),
        exc_info=None,
        extra={
            "exit_code": 0,
            "stdout_payload_size_bytes": 1500,
            "stderr_payload_size_bytes": 0,
            "stdout_payload_truncated": True,
            "stderr_payload_truncated": False,
            "stdout_detail_unavailable_reason": None,
            "stdout": "full output here",
            "stderr": "",
        },
    )

    formatted = formatter.format(record)
    # Useful fields should be present
    assert "exit_code=0" in formatted
    # Technical metadata should be excluded
    assert "payload_size_bytes" not in formatted
    assert "payload_truncated" not in formatted
    assert "detail_unavailable_reason" not in formatted
    assert "stdout=" not in formatted
    assert "stderr=" not in formatted


def test_text_formatter_includes_env_overridden_and_redaction_flags():
    """env_overridden and redaction flags should appear in text output."""
    configure_logging(level_name="info", log_format="text")
    logger = get_logger("test_text_useful_flags")
    formatter = logger.handlers[0].formatter
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn="test.py",
        lno=1,
        msg="subprocess trace",
        args=(),
        exc_info=None,
        extra={
            "env_overridden": True,
            "stdout_redaction_applied": True,
            "stderr_redaction_applied": False,
        },
    )

    formatted = formatter.format(record)
    assert "env_overridden=True" in formatted
    assert "stdout_redaction_applied=True" in formatted
    assert "stderr_redaction_applied=False" in formatted


def test_text_formatter_excludes_event_field():
    """event field should be excluded from text output."""
    configure_logging(level_name="info", log_format="text")
    logger = get_logger("test_text_event_filter")
    formatter = logger.handlers[0].formatter
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn="test.py",
        lno=1,
        msg="login started",
        args=(),
        exc_info=None,
        extra={
            "event": "login_processing_started",
            "profile": "my-profile",
        },
    )

    formatted = formatter.format(record)
    # event should be excluded (internal technical field)
    assert "event=" not in formatted
    # profile should still be present
    assert "profile=my-profile" in formatted


def test_sanitize_trace_payload_redacts_json_token_fields():
    payload = '{"access_token":"abc123","refresh_token":"def456"}'

    sanitized = sanitize_trace_payload(payload)

    assert "abc123" not in sanitized["value"]
    assert "def456" not in sanitized["value"]
    assert "<redacted>" in sanitized["value"]
    assert sanitized["redaction_applied"] is True


def test_sanitize_trace_payload_redacts_bearer_authorization():
    payload = "Authorization: Bearer super-secret-token"

    sanitized = sanitize_trace_payload(payload)

    assert "super-secret-token" not in sanitized["value"]
    assert "Authorization" in sanitized["value"]
    assert "<redacted>" in sanitized["value"]
    assert sanitized["redaction_applied"] is True


def test_sanitize_trace_payload_redacts_additional_secret_keys():
    payload = '{"aws_session_token":"tok-123","client_secret":"super-secret"}'

    sanitized = sanitize_trace_payload(payload)

    assert "tok-123" not in sanitized["value"]
    assert "super-secret" not in sanitized["value"]
    assert sanitized["redaction_applied"] is True


def test_sanitize_trace_payload_redacts_aws_access_key_id_pattern():
    payload = "caller key is AKIAIOSFODNN7EXAMPLE"

    sanitized = sanitize_trace_payload(payload)

    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized["value"]
    assert sanitized["redaction_applied"] is True


def test_sanitize_trace_payload_redacts_presigned_url_signature():
    payload = "https://example.com?X-Amz-Signature=abcdef1234567890&X-Amz-Security-Token=tok123"

    sanitized = sanitize_trace_payload(payload)

    assert "abcdef1234567890" not in sanitized["value"]
    assert "tok123" not in sanitized["value"]
    assert sanitized["redaction_applied"] is True


def test_get_logger_detects_color_when_stdout_is_tty(monkeypatch):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    logger = get_logger("test_color_tty")

    formatter = logger.handlers[0].formatter
    assert formatter._use_color is True


def test_get_logger_detects_no_color_when_stdout_not_tty(monkeypatch):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

    logger = get_logger("test_color_notty")

    formatter = logger.handlers[0].formatter
    assert formatter._use_color is False


def test_install_qt_message_handler_returns_previous_handler(monkeypatch):
    previous_handler = object()

    monkeypatch.setattr(logger_module, "QtMsgType", object())

    def fake_install(handler):
        assert callable(handler)
        return previous_handler

    monkeypatch.setattr(logger_module, "qInstallMessageHandler", fake_install)

    returned_handler = install_qt_message_handler()

    assert returned_handler is previous_handler


def test_qt_warning_multiline_is_logged_line_by_line(capsys):
    qt_core = pytest.importorskip("PySide6.QtCore")
    q_warning = getattr(qt_core, "qWarning", None)
    if q_warning is None:
        pytest.skip("qWarning is unavailable in this PySide6 build")

    root_logger = logging.getLogger()
    original_level = root_logger.level
    original_handlers = list(root_logger.handlers)
    previous_qt_handler = None

    try:
        configure_logging(level_name="debug", log_format="text")
        previous_qt_handler = install_qt_message_handler()

        q_warning(
            "QObject: Cannot create children for a parent that is in a"
            " different thread.\n(Parent is QMenu(0x1), parent's thread"
            " is QThread(0x2), current thread is QThread(0x3)"
        )

        output = capsys.readouterr().out
        warning_lines = [
            line for line in output.splitlines() if "WARNING [PySide6.Qt]" in line
        ]

        assert len(warning_lines) == 2
        assert (
            "QObject: Cannot create children for a parent that is in a"
            in warning_lines[0]
        )
        assert (
            "(Parent is QMenu(0x1), parent's thread is QThread(0x2),"
            in warning_lines[1]
        )
    finally:
        qt_core.qInstallMessageHandler(previous_qt_handler)
        root_logger.handlers.clear()
        root_logger.handlers.extend(original_handlers)
        root_logger.setLevel(original_level)
