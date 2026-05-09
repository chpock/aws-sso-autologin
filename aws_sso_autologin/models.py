"""Data models for AWS SSO Autologin."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RenewalStatus(Enum):
    """Status of a session renewal check."""

    NOT_NEEDED = "not_needed"
    TRIGGERED = "triggered"
    UNKNOWN = "unknown"


class SessionFailureType(Enum):
    """Classifier outcome for failed session checks."""

    NONE = "none"
    EXPIRED_OR_INVALID = "expired_or_invalid"
    PERMISSION_DENIED = "permission_denied"
    OTHER = "other"
    TIMEOUT = "timeout"
    CHECK_ERROR = "check_error"


@dataclass
class ProfileConfig:
    """Configuration for an AWS SSO profile."""

    name: str
    region: Optional[str] = None
    sso_start_url: Optional[str] = None
    sso_region: Optional[str] = None
    sso_account_id: Optional[str] = None
    sso_role_name: Optional[str] = None


@dataclass
class SessionInfo:
    """Information about an AWS SSO session."""

    profile_name: str
    is_active: bool
    seconds_remaining: Optional[int] = None
    expiration_time: Optional[str] = None
    failure_type: SessionFailureType = SessionFailureType.NONE
    error_message: Optional[str] = None


@dataclass
class HealthStatus:
    """Health status for a profile."""

    profile_name: str
    is_healthy: bool
    last_check: float
    message: str = ""


@dataclass
class ClassificationResult:
    """Result of classifying CLI output."""

    status: str
    confidence: float
    details: dict = field(default_factory=dict)
