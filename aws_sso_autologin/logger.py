"""Logging utilities."""

import json
import logging
import sys
from typing import Optional, Set

# Track all loggers created by get_logger
_created_loggers: Set[logging.Logger] = set()


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
        level = logging.INFO
    
    logger.setLevel(level)
    
    # Only add handler if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        
        formatter = StructuredFormatter()
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
