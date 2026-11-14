"""
exceptions.py — Custom exceptions for the astronomy module
============================================================

Provides a clear exception hierarchy so callers can distinguish
between network failures, API errors, and parse failures.
"""


class AstronomyError(Exception):
    """Base exception for the astronomy module."""
    pass


class HorizonsAPIError(AstronomyError):
    """
    Raised when the JPL Horizons API returns an unexpected HTTP status
    or an error message inside its response body.

    Attributes:
        status_code : HTTP status code (if available)
        body        : Raw response body (truncated)
    """

    def __init__(self, message: str, status_code: int | None = None,
                 body: str = "") -> None:
        self.status_code = status_code
        self.body = body[:2000]  # Truncate to avoid giant tracebacks
        detail = f" [HTTP {status_code}]" if status_code else ""
        super().__init__(f"{message}{detail}")


class HorizonsParseError(AstronomyError):
    """
    Raised when the Horizons response text cannot be parsed — missing
    $$SOE/$$EOE markers, unexpected column layout, etc.
    """
    pass


class HorizonsConnectionError(AstronomyError):
    """
    Raised when the HTTP request to Horizons fails due to network
    issues (timeout, DNS failure, connection refused, etc.).
    """
    pass


class InvalidCoordinateError(AstronomyError):
    """
    Raised when the caller supplies coordinates outside valid bounds
    (latitude, longitude, altitude) before we even hit the network.
    """
    pass


class InvalidDateError(AstronomyError):
    """
    Raised when the caller supplies a date/time that is out of the
    Horizons supported range or is otherwise malformed.
    """
    pass

