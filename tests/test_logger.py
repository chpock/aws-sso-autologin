"""Tests for logger module."""

import json
import logging
import sys

from aws_sso_autologin.logger import (
    configure_logging,
    get_logger,
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
