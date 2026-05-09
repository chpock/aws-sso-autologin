"""AWS SSO Autologin - System tray app for automatic AWS SSO session refresh."""

try:
    from aws_sso_autologin._version import __version__

    VERSION_SOURCE = "embedded"
except ImportError:
    __version__ = "0.0.0"
    VERSION_SOURCE = "default"

__all__ = [
    "__version__",
    "VERSION_SOURCE",
    "constants",
    "errors",
    "logger",
    "tray",
    "classifier",
    "operator",
    "service",
    "aws",
]
