import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import NotSupportedError
from .core.config import get_settings
from .core.database import create_tables, AsyncSessionLocal, engine
from .api.routes import listings, market, performance, internal, references, scenarios, thresholds, intelligence, auth, billing, admin
from .models import scenario   # noqa: F401 — registers scenarios_rules with Base
from .models import threshold  # noqa: F401 — registers threshold_configs with Base
from .models import import_batch, listing_report, keyword_report, manual_listing_report, manual_keyword_report  # noqa: F401 — register with Base
from .models import thumbnail_knowledge  # noqa: F401 — registers thumbnail_knowledge with Base
from .models import user, subscription, credit, payment  # noqa: F401 — registers auth/payment models with Base
from .services import performance_service, reporting_etl, crawler_ops

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
            await crawler_ops.ensure_crawler_tables(session)
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
app.include_router(market.router, prefix="/api/v1")
app.include_router(performance.router, prefix="/api/v1")
app.include_router(internal.router, prefix="/api/v1")
app.include_router(references.router, prefix="/api/v1")
app.include_router(scenarios.router,   prefix="/api/v1")
app.include_router(thresholds.router,  prefix="/api/v1")
app.include_router(intelligence.router, prefix="/api/v1/intelligence", tags=["intelligence"])
app.include_router(auth.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


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
_docs_dir = Path(__file__).resolve().parents[2] / "docs"
if _docs_dir.exists():
    app.mount("/md-docs", StaticFiles(directory=str(_docs_dir)), name="docs")

# Extension download — served with octet-stream so Chrome doesn't block .xpi
_ext_xpi = Path(__file__).resolve().parents[2] / "extension-keyword-main" / "Archive.pxi"

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
_frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if _frontend_dir.exists():
    # Explicit route: /app → app.html (portal, requires auth)
    @app.get("/app")
    async def serve_app():
        return FileResponse(str(_frontend_dir / "app.html"))

    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
