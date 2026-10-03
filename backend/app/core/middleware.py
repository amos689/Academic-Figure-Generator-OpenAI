"""Middleware configuration for the FastAPI application."""

import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings
from app.core.upload_limit import UploadLimitMiddleware

logger = logging.getLogger(__name__)


class LocalMutationMiddleware(BaseHTTPMiddleware):
    """CORS alone does not stop another website submitting a local multipart form."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            allowed = set(get_settings().CORS_ORIGINS)
            allowed.add(f"{request.url.scheme}://{request.url.netloc}")
            if origin is not None and origin not in allowed:
                return JSONResponse({"detail": "Untrusted request origin"}, status_code=403)
        return await call_next(request)


def setup_cors(app: FastAPI) -> None:
    """Add CORS middleware using origins from settings."""
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each request with method, path, status code, and duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %d  (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


def setup_middleware(app: FastAPI) -> None:
    """Register all middleware on the application."""
    setup_cors(app)
    app.add_middleware(
        UploadLimitMiddleware, max_bytes=(2 * get_settings().MAX_UPLOAD_SIZE_MB + 1) * 1024 * 1024
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(LocalMutationMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_settings().ALLOWED_HOSTS)
