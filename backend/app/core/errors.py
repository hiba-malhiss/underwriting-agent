"""The app's base exceptions. Every module's own exceptions inherit from one of these.

Each carries its HTTP status code, so one global handler (error_handlers.py) can answer for all
of them, and core never needs to know which modules exist. A module adds a new error by
subclassing; nothing here changes (open/closed).
"""


class AppError(Exception):
    status_code = 500

    def public_message(self) -> str:
        """What the client is told. Defaults to the error's own message; override to hide
        internal details."""
        return str(self)


class BadRequestError(AppError):
    """The client sent something we don't accept."""

    status_code = 400


class ConflictError(AppError):
    """The request clashes with the current state (e.g. someone saved at the same time)."""

    status_code = 409


class BadGatewayError(AppError):
    """An external service (e.g. Azure) failed."""

    status_code = 502


class ServiceUnavailableError(AppError):
    """The app isn't set up correctly to do this right now (config, sign-in, permissions)."""

    status_code = 503
