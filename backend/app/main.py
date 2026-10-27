"""FastAPI application entrypoint."""

import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api import router
from app.config import get_settings

settings = get_settings()
app = FastAPI(
    title="Booker TPV API",
    version="1.0.0",
    docs_url="/api/docs" if settings.app_env != "production" else None,
    redoc_url="/api/redoc" if settings.app_env != "production" else None,
    openapi_url="/api/openapi.json" if settings.app_env != "production" else None,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret.get_secret_value(),
    session_cookie="booker_session",
    max_age=settings.session_max_age_seconds,
    same_site="strict",
    https_only=settings.cookie_secure and settings.app_env != "test",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)
app.include_router(router)
logger = logging.getLogger("booker_tpv")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@app.middleware("http")
async def request_logging(request: Request, call_next):
    """Attach a request identifier and log outcome without sensitive payloads."""
    request_id = str(uuid4())
    if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
        origin = request.headers.get("origin")
        if origin is not None and origin != settings.allowed_origin:
            return JSONResponse(
                status_code=403,
                media_type="application/problem+json",
                content={"type": "about:blank", "title": "Acceso denegado", "status": 403, "detail": "Origen no permitido"},
                headers={"X-Request-ID": request_id, **SECURITY_HEADERS},
            )
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    response.headers["X-Request-ID"] = request_id
    logger.info("request_id=%s method=%s path=%s status_code=%s", request_id, request.method, request.url.path, response.status_code)
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return application errors using the same Problem Details media type."""
    del request
    titles = {400: "Petición no válida", 401: "No autenticado", 403: "Acceso denegado", 404: "No encontrado", 409: "Conflicto", 422: "Petición no válida"}
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content=jsonable_encoder({
            "type": "about:blank",
            "title": titles.get(exc.status_code, "Error de solicitud"),
            "status": exc.status_code,
            "detail": exc.detail,
        }),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return validation failures in a stable, client-safe format."""
    del request
    return JSONResponse(
        status_code=422,
        media_type="application/problem+json",
        content=jsonable_encoder({"type": "about:blank", "title": "Petición no válida", "status": 422, "detail": exc.errors()}),
    )