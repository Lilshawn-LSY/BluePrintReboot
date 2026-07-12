from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.dependencies import ReadModelUnavailable
from api.routes import router
from config.contact import APP_VERSION


UNAVAILABLE_DETAIL = "Read model is temporarily unavailable."


def create_app() -> FastAPI:
    application = FastAPI(title="BluePrintReboot Read-Only API", version=APP_VERSION)

    @application.exception_handler(ReadModelUnavailable)
    async def read_model_unavailable_handler(
        _request: Request,
        _exception: ReadModelUnavailable,
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": UNAVAILABLE_DETAIL})

    application.include_router(router)
    return application


app = create_app()
