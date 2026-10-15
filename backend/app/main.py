"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1 import audit_logs, bioage, patients
from app.core.config import get_settings
from app.core.logging import configure_logging

log = logging.getLogger("app.access")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="uSciTec BioAge AI API",
        version=__version__,
        description="Deterministic biological-age engine. Research use only; not a diagnostic.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # noqa: ANN202
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if incoming.isalnum() and len(incoming) <= 64 else uuid.uuid4().hex
        request.state.request_id = rid
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            route = request.scope.get("route")
            log.info(
                "request",
                extra={
                    "request_id": rid,
                    "method": request.method,
                    # route template (e.g. /patients/{patient_id}), never the query string
                    "route": getattr(route, "path", "unmatched"),
                    "status_code": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )

    @app.exception_handler(HTTPException)
    async def http_exc(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", **detail},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def schema_exc(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "code": "SCHEMA_" + str(e.get("type", "invalid")).upper(),
                "field": ".".join(str(p) for p in e.get("loc", ())[1:]),
                "message": e.get("msg", "invalid"),
                "severity": "error",
            }
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "status": "rejected",
                "code": "SCHEMA_VALIDATION_FAILED",
                "message": "请求格式不正确",
                "errors": errors,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("app.error").error(
            "unhandled exception",
            extra={"request_id": getattr(request.state, "request_id", None), "event": type(exc).__name__},
        )
        return JSONResponse(
            status_code=500,
            content={"status": "error", "code": "INTERNAL_ERROR", "message": "服务器内部错误"},
        )

    @app.get("/api/v1/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    for r in (bioage.router, patients.router, audit_logs.router):
        app.include_router(r, prefix="/api/v1")
    return app


app = create_app()
