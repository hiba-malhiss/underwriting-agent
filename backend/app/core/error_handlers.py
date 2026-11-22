"""Global error handling: one place that turns the app's exceptions into HTTP responses.

Like Spring's @ControllerAdvice / @ExceptionHandler: routes just raise (no try/except). Every
app exception is an AppError that carries its own status code and client message, so a single
handler serves them all, and this file never imports a feature module.

Responses keep FastAPI's usual shape, {"detail": "..."}, which the frontend shows as is.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import AppError


async def _handle_app_error(_: Request, error: AppError) -> JSONResponse:
    return JSONResponse({"detail": error.public_message()}, status_code=error.status_code)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
