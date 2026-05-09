"""Logging utilities."""

import json
import logging
import re
import sys
from typing import Any, Optional, Set

# Track all loggers created by get_logger
_created_loggers: Set[logging.Logger] = set()

TRACE_LEVEL_NUM = 5
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")

_SECRET_KEYS = (
    "access_token",
    "refresh_token",
    "id_token",
    "session_token",
    "aws_session_token",
    "security_token",
    "x_amz_security_token",
    "client_secret",
    "secret",
    "password",
    "authorization",
    "aws_access_key_id",
    "aws_secret_access_key",
)

_JSON_SECRET_PAIR = re.compile(
    r'(?i)("(?:' + "|".join(_SECRET_KEYS) + r')"\s*:\s*)"[^"]*"'
)
_KV_SECRET_PAIR = re.compile(
    r"(?i)\b(" + "|".join(_SECRET_KEYS) + r")\b\s*[:=]\s*([^\s,;]+)"
)
_AUTH_BEARER = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([^\s,;]+)")
_AUTH_BASIC = re.compile(r"(?i)(authorization\s*:\s*basic\s+)([^\s,;]+)")
_AWS_ACCESS_KEY_ID = re.compile(r"\b(AKIA[0-9A-Z]{16})\b")
_AWS_URL_TOKEN = re.compile(
    r"(?i)\b(X-Amz-(Signature|Security-Token|Credential))=([^&\s]+)"
)


def sanitize_trace_payload(value: Any, max_len: int = 2000) -> dict[str, Any]:
    """Return safe trace payload metadata with redaction and truncation markers."""
    text = str(value or "")
    redacted = text
    redacted_applied = False
    updated = _JSON_SECRET_PAIR.sub(r'\1"<redacted>"', redacted)
    if updated != redacted:
        redacted_applied = True
    redacted = updated

    updated = _AUTH_BEARER.sub(r"\1<redacted>", redacted)
    if updated != redacted:
        redacted_applied = True
    redacted = updated

    updated = _AUTH_BASIC.sub(r"\1<redacted>", redacted)
    if updated != redacted:
        redacted_applied = True
    redacted = updated

    updated = _KV_SECRET_PAIR.sub(r"\1=<redacted>", redacted)
    if updated != redacted:
        redacted_applied = True
    redacted = updated

    updated = _AWS_ACCESS_KEY_ID.sub("<redacted>", redacted)
    if updated != redacted:
        redacted_applied = True
    redacted = updated

    updated = _AWS_URL_TOKEN.sub(r"\1=<redacted>", redacted)
    if updated != redacted:
        redacted_applied = True
    redacted = updated

    payload_size = len(redacted)
    truncated = payload_size > max_len
    safe_text = redacted[:max_len]

    result: dict[str, Any] = {
        "value": safe_text,
        "payload_size_bytes": payload_size,
        "payload_truncated": truncated,
        "redaction_applied": redacted_applied,
    }
    if not safe_text:
        result["detail_unavailable_reason"] = "empty_output"
    return result


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured stdout logs."""

    _BASE_FIELDS = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key in self._BASE_FIELDS or key.startswith("_"):
                continue
            payload[key] = value

        return json.dumps(payload, sort_keys=True)


class TextFormatter(logging.Formatter):
    """Human-readable formatter with optional ANSI colors."""

    COLORS = {
        "TRACE": "\033[37m",
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool) -> None:
        super().__init__()
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        if self._use_color and level in self.COLORS:
            level = f"{self.COLORS[level]}{level}{self.RESET}"
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        return f"{timestamp} {level} [{record.name}] {record.getMessage()}"


def parse_log_level(level_name: str) -> int:
    """Convert a log-level name to logging numeric level."""
    level = level_name.strip().lower()
    mapping = {
        "trace": TRACE_LEVEL_NUM,
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    return mapping[level]


def configure_logging(level_name: str = "info", log_format: str = "text") -> None:
    """Configure root logger format and level."""
    level = parse_log_level(level_name)
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if log_format == "json":
        handler.setFormatter(StructuredFormatter())
    else:
        use_color = bool(getattr(sys.stdout, "isatty", lambda: False)())
        handler.setFormatter(TextFormatter(use_color=use_color))

    root.handlers.clear()
    root.addHandler(handler)

    for logger in _created_loggers:
        logger.setLevel(level)
        logger.handlers.clear()
        logger.propagate = True


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get a logger with standard configuration.
    
    Args:
        name: Logger name
        level: Optional log level (defaults to INFO)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if level is None:
        level = logging.getLogger().level or logging.INFO
    
    logger.setLevel(level)
    
    logger.propagate = True

    # Only add handler if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        root_handlers = logging.getLogger().handlers
        if root_handlers and isinstance(root_handlers[0].formatter, StructuredFormatter):
            formatter = StructuredFormatter()
        else:
            formatter = TextFormatter(use_color=False)
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
    
    # Track this logger for debug mode updates
    _created_loggers.add(logger)
    
    return logger


def set_debug_mode(enabled: bool = True) -> None:
    """Enable or disable debug logging for all autologin loggers.
    
    Args:
        enabled: Whether to enable debug mode
    """
    level = logging.DEBUG if enabled else logging.INFO
    
    # Update all loggers created by get_logger
    for logger in _created_loggers:
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)
