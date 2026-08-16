from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.dependencies import ReadModelUnavailable
from api.routes import router
from config.contact import APP_VERSION


UNAVAILABLE_DETAIL = "Read model is temporarily unavailable."
INVALID_REQUEST_DETAIL = "Request validation failed."


def create_app() -> FastAPI:
    application = FastAPI(title="BluePrintReboot Local API", version=APP_VERSION)

    @application.exception_handler(ReadModelUnavailable)
    async def read_model_unavailable_handler(
        _request: Request,
        _exception: ReadModelUnavailable,
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": UNAVAILABLE_DETAIL})

    @application.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        exception: RequestValidationError,
    ) -> JSONResponse:
        reader_command = (
            request.url.path.endswith("/metadata")
            or request.url.path.endswith("/tags")
            or request.url.path.endswith("/reading-note")
            or (
                request.method in {"POST", "PATCH"}
                and "/note-blocks" in request.url.path
                and request.url.path.startswith("/papers/")
            )
        )
        project_command = (
            request.method in {"POST", "PATCH", "DELETE"}
            and (
                request.url.path == "/projects"
                or request.url.path.startswith("/projects/")
            )
        )
        if not (reader_command or project_command):
            return await request_validation_exception_handler(request, exception)
        return JSONResponse(
            status_code=422,
            content={"detail": INVALID_REQUEST_DETAIL},
        )

    application.include_router(router)
    return application


app = create_app()
