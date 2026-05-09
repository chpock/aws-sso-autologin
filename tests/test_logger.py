"""Tests for logger module."""

import json
import logging
import sys

from aws_sso_autologin.logger import get_logger, set_debug_mode


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
