"""
Runtime mode detection for AI-safe execution.

Simplified design: --check-only flag forces safe mode; automation context
(CI, AI_AGENT, pytest) defaults to check-only; interactive use runs normal.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum, auto

from aws_sso_autologin.logger import get_logger


logger = get_logger(__name__)


class ExecutionMode(Enum):
    """Application execution modes."""
    CHECK_ONLY = auto()  # Bounded preflight/check, no daemon loop
    NORMAL = auto()  # Normal operation (daemon in interactive, check-only in automation)


@dataclass(frozen=True)
class AutomationContext:
    """Detected automation environment context."""
    is_automation: bool
    detected_signals: list[str]  # Which env vars triggered automation detection


def get_automation_context() -> AutomationContext:
    """
    Detect automation context from environment heuristics.
    
    Returns:
        AutomationContext with detection results.
    """
    automation_signals = []
    
    # Check known automation environment variables
    if os.environ.get("CI"):
        automation_signals.append("CI")
    if os.environ.get("AI_AGENT"):
        automation_signals.append("AI_AGENT")
    if os.environ.get("PYTEST_CURRENT_TEST"):
        automation_signals.append("PYTEST_CURRENT_TEST")
    
    context = AutomationContext(
        is_automation=len(automation_signals) > 0,
        detected_signals=automation_signals,
    )
    logger.debug(
        "automation context detected",
        extra={
            "event": "automation_context_detected",
            "is_automation": context.is_automation,
            "signals": context.detected_signals,
        },
    )
    return context


def get_execution_mode(cli_check_only: bool = False) -> ExecutionMode:
    """
    Determine execution mode using simplified logic.
    
    Logic:
    1. --check-only flag forces CHECK_ONLY mode (highest priority)
    2. Automation context (CI, AI_AGENT, pytest) defaults to CHECK_ONLY
    3. Interactive context runs NORMAL mode
    
    Args:
        cli_check_only: Whether --check-only flag was passed
    
    Returns:
        ExecutionMode appropriate for current context
    """
    # Level 1: CLI flag has highest precedence
    if cli_check_only:
        logger.info(
            "execution mode selected",
            extra={
                "event": "mode_selected",
                "mode": "check_only",
                "reason": "cli_flag",
            },
        )
        return ExecutionMode.CHECK_ONLY
    
    # Level 2: Automation context defaults to safe mode
    ctx = get_automation_context()
    if ctx.is_automation:
        logger.info(
            "execution mode selected",
            extra={
                "event": "mode_selected",
                "mode": "check_only",
                "reason": "automation_context",
                "signals": ctx.detected_signals,
            },
        )
        return ExecutionMode.CHECK_ONLY
    
    # Level 3: Interactive use - normal operation
    logger.info(
        "execution mode selected",
        extra={"event": "mode_selected", "mode": "normal", "reason": "interactive"},
    )
    return ExecutionMode.NORMAL
