"""Logging utilities."""

import logging
import sys
from typing import Optional, Set

# Track all loggers created by get_logger
_created_loggers: Set[logging.Logger] = set()


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
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
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
