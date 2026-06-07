import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path


def _resource_root() -> Path:
    """Directory that holds frontend/, docs/, extension files and .env.

    Works in three modes:
      - dev:        the project dir (backend/app/main.py -> parents[2])
      - PyInstaller: the bundle's extraction dir (sys._MEIPASS)
      - override:   ETSY_RESOURCE_ROOT env (set by the desktop launcher)
    """
    override = os.environ.get("ETSY_RESOURCE_ROOT")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[2]


RESOURCE_ROOT = _resource_root()
from fastapi import FastAPI, Request
from fastapi.responses import Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import NotSupportedError
from .core.config import get_settings
from .core.database import create_tables, AsyncSessionLocal, engine
from .api.routes import listings, performance, internal, scenarios, thresholds, auth, settings as settings_routes, optimization_log
from .models import scenario   # noqa: F401 — registers scenarios_rules with Base
from .models import optimization_log as optimization_log_model  # noqa: F401 — registers optimization_log with Base
from .models import threshold  # noqa: F401 — registers threshold_configs with Base
from .models import listing_report, keyword_report, manual_listing_report, manual_keyword_report  # noqa: F401 — register with Base
from .models import user  # noqa: F401 — registers users table with Base
from .services import performance_service, reporting_etl

logger = logging.getLogger(__name__)
settings = get_settings()


class RetryOnInvalidCacheMiddleware(BaseHTTPMiddleware):
    """Retry request once if asyncpg InvalidCachedStatementError fires.

    Multipart/file-upload requests are excluded: the body stream is already
    consumed after the first attempt and cannot be replayed, causing a 500.
    """
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except NotSupportedError as e:
            if "InvalidCachedStatementError" in str(e):
                content_type = request.headers.get("content-type", "")
                if "multipart/form-data" in content_type:
                    # Cannot retry — body stream already consumed
                    raise
                logger.warning("InvalidCachedStatementError on %s %s — retrying once", request.method, request.url.path)
                return await call_next(request)
            raise

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path in ('/', '/app') or request.url.path.endswith(('.html', '.js', '.css')):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


async def _background_init():
    """Run DB init tasks after app is already serving traffic."""
    try:
        await create_tables()
        async with AsyncSessionLocal() as session:
            await performance_service.seed_scenarios(session)
            await reporting_etl.ensure_reporting_tables(session)
    except Exception as exc:
        logger.warning("Background init failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Yield immediately so Render port scan succeeds, then init DB in background
    asyncio.create_task(_background_init())
    yield


app = FastAPI(
    title="Etsy Listing Manager API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RetryOnInvalidCacheMiddleware)
app.add_middleware(NoCacheMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(listings.router, prefix="/api/v1")
app.include_router(performance.router, prefix="/api/v1")
app.include_router(internal.router, prefix="/api/v1")
app.include_router(scenarios.router,   prefix="/api/v1")
app.include_router(thresholds.router,  prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(settings_routes.router, prefix="/api/v1")
app.include_router(optimization_log.router, prefix="/api/v1")


@app.get("/favicon.ico")
async def favicon():
    return Response(content=None, status_code=204)


# Redirect common misspellings: /etsymate.html -> /etseemate.html
@app.get("/etsymate.html")
@app.get("/etsyMate.html")
async def redirect_etsymate():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/etseemate.html", status_code=301)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.APP_ENV}


# Serve docs/ markdown files at /md-docs/ to avoid prefix clash with /docs.html
_docs_dir = RESOURCE_ROOT / "docs"
if _docs_dir.exists():
    app.mount("/md-docs", StaticFiles(directory=str(_docs_dir)), name="docs")

# Extension download — served with octet-stream so Chrome doesn't block .xpi
_ext_xpi = RESOURCE_ROOT / "extension-keyword-main" / "Archive.pxi"

@app.get("/extension/download")
async def download_extension():
    if not _ext_xpi.exists():
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(404, "Extension file not found")
    return FileResponse(
        path=str(_ext_xpi),
        media_type="application/octet-stream",
        filename="EtseeMate-extension.xpi",
    )

# Serve frontend static files — must be AFTER API routes
_frontend_dir = RESOURCE_ROOT / "frontend"
if _frontend_dir.exists():
    from fastapi.responses import HTMLResponse

    @app.get("/app")
    async def serve_app():
        # In desktop mode there is no login: inject a sentinel token so app.html's
        # bootstrap doesn't redirect to the landing/login page. (The backend
        # ignores the token value when DESKTOP_MODE=1.)
        if os.environ.get("DESKTOP_MODE") == "1":
            html = (_frontend_dir / "app.html").read_text(encoding="utf-8")
            inject = "<script>try{sessionStorage.setItem('Getify_token','desktop')}catch(e){}</script>"
            html = html.replace("<body>", "<body>\n" + inject, 1)
            return HTMLResponse(html)
        return FileResponse(str(_frontend_dir / "app.html"))

    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
