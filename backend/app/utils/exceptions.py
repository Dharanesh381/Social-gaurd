"""Custom application exceptions."""

from typing import Any


class SocialGuardException(Exception):
    """Base exception class for Social Guard application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class PayloadValidationError(SocialGuardException):
    """Raised when an incoming social media post payload fails domain validation."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message=message, status_code=422, details=details)


class AnalysisPipelineError(SocialGuardException):
    """Raised when an analytical module or pipeline component fails execution."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message=message, status_code=500, details=details)
