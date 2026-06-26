"""Core exception types."""


class DymoCoreError(Exception):
    """Base exception for the core package."""


class ConfigurationError(DymoCoreError):
    """Raised when required settings are invalid or missing."""

