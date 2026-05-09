"""Exception classes for AWS SSO Autologin."""


class AutologinError(Exception):
    """Base exception for all autologin errors."""
    pass


class TokenizationError(AutologinError):
    """Error during log line tokenization."""
    pass


class ClassificationError(AutologinError):
    """Error during log line classification."""
    pass


class CorpusError(AutologinError):
    """Error in corpus operations."""
    pass


class OperatorError(AutologinError):
    """Error in operator execution."""
    pass


class AWSCliError(AutologinError):
    """Error executing AWS CLI command."""
    pass


class TrayHostError(AutologinError):
    """Error detecting or communicating with tray host."""
    pass
