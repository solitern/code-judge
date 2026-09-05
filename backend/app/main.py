"""FastAPI application entrypoint."""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import admin, health, public
from .config import ensure_data_dir, get_settings
from .db import Base, SessionLocal, engine
from .models import AdminUser, Problem, Solution, TestCase, Week, WeekSnapshot  # noqa: F401
from .services.admin import ensure_admin
from .services.runner_client import close_runner_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")

settings = get_settings()
ensure_data_dir(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_admin(db)
    try:
        yield
    finally:
        await close_runner_client()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS for development only (Vite dev server).  In production the frontend
    # is served from the same origin.
    if settings.allowed_origin:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.allowed_origin],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def valid_request_origin(request: Request) -> bool:
        if not settings.allowed_origin:
            return True
        source = request.headers.get("origin") or request.headers.get("referer")
        if not source:
            return True
        expected = urlsplit(settings.allowed_origin)
        actual = urlsplit(source)
        return (actual.scheme, actual.netloc) == (expected.scheme, expected.netloc)

    @app.middleware("http")
    async def csrf_middleware(request: Request, call_next):
        """Double-submit CSRF protection for admin mutation endpoints.

        Login is exempt because no session/csrf cookie exists yet.
        """
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        path = request.url.path
        if path.startswith("/api/admin") and not path.endswith("/login"):
            csrf_cookie = request.cookies.get("csrf_token")
            header_token = request.headers.get("x-csrf-token")
            if not csrf_cookie or not header_token or not hmac.compare_digest(csrf_cookie, header_token):
                return JSONResponse(status_code=403, content={"detail": "CSRF 校验失败"})
            if not valid_request_origin(request):
                return JSONResponse(status_code=403, content={"detail": "非法来源"})
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        path = request.url.path
        if request.method in ("GET", "HEAD"):
            if path.startswith("/assets/") and response.status_code < 400:
                # Vite assets contain a content hash, so immutable caching is safe.
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            elif not path.startswith("/api/"):
                # SPA routes all return index.html. It must never outlive a
                # deployment or it may reference lazy-loaded chunks that no
                # longer exist in the new image.
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
        return response

    app.include_router(health.router)
    app.include_router(public.router, prefix=settings.api_prefix)
    app.include_router(admin.router, prefix=settings.api_prefix)

    # Serve the built Vue frontend (Docker image copies it to /app/static).
    dist = Path(settings.frontend_dist).resolve()
    if dist.exists() and (dist / "index.html").exists():
        from fastapi.responses import FileResponse

        assets_dir = dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/")
        def frontend_index():
            return FileResponse(str(dist / "index.html"))

        @app.get("/{full_path:path}")
        def frontend_spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")
            try:
                candidate = (dist / full_path).resolve()
            except (OSError, RuntimeError):
                raise HTTPException(status_code=404, detail="Not Found") from None
            if not candidate.is_relative_to(dist):
                raise HTTPException(status_code=404, detail="Not Found")
            if candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(dist / "index.html"))

    return app


app = create_app()
