import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings

logger = logging.getLogger("freak_town")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
WEBAPP_DIR = Path(__file__).parent.parent / "apps" / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables. Shutdown: dispose engine."""
    from backend.db import engine, Base
    from backend.models import (  # noqa: F401 — ensure all models are imported
        User, Comedian, ActVersion, Submission, Episode, Appearance,
        ShowEvent, AudienceSession, CrowdBucket, JudgeRun,
        InterviewState, GenerationRun, MediaAsset, SponsorCampaign,
    )
    from backend.auth import APIKey  # noqa: F401

    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database ready.")

    yield

    logger.info("Shutting down.")
    await engine.dispose()


app = FastAPI(
    title="Freak Town",
    description="A live talent show for artificial personalities",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ────────────────────────────────────────────────────────

from backend.routes import admin, audience, comedians, episodes, mcp, stage, motions, dressing_room, green_room, shows, judge, sound, launchpad, potchain, intake  # noqa: E402

app.include_router(comedians.router, prefix="/v1/comedians", tags=["comedians"])
app.include_router(episodes.router, prefix="/v1/episodes", tags=["episodes"])
app.include_router(audience.router, prefix="/v1", tags=["audience"])
app.include_router(stage.router, prefix="/v1/ws", tags=["stage"])
app.include_router(admin.router, prefix="/v1/admin", tags=["admin"])
app.include_router(mcp.router, prefix="/v1", tags=["mcp"])
app.include_router(motions.router, prefix="/v1", tags=["motions"])
app.include_router(dressing_room.router, prefix="/v1", tags=["dressing-room"])
app.include_router(green_room.router, prefix="/v1", tags=["green-room"])
app.include_router(shows.router, prefix="/v1", tags=["shows"])
app.include_router(judge.router, prefix="/v1", tags=["judge"])
app.include_router(sound.router, prefix="/v1", tags=["sound"])
app.include_router(launchpad.router, prefix="/v1", tags=["launchpad"])
app.include_router(potchain.router, prefix="/v1", tags=["potchain"])
app.include_router(intake.router, prefix="/v1", tags=["intake"])


# ── API Info ───────────────────────────────────────────────────────────

@app.get("/api")
async def api_info():
    return {
        "name": "Freak Town",
        "description": "A live talent show for artificial personalities",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "green_room": "/v1/green-room/characters",
            "episodes": "/v1/episodes/live",
            "shows": "/v1/shows",
        },
    }


# ── Health ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Frontend ───────────────────────────────────────────────────────────

# Serve the production React app from apps/web/dist (built with: cd apps/web && npm run build)
# Falls back to legacy frontend/ if the build doesn't exist yet.
SERVE_DIR = WEBAPP_DIR if WEBAPP_DIR.exists() else FRONTEND_DIR


@app.get("/")
async def root():
    """Serve the React app (or legacy HTML) as the main UI."""
    index = SERVE_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "name": "Freak Town",
        "description": "A live talent show for artificial personalities",
        "version": "0.1.0",
        "api": {
            "docs": "/docs",
            "mcp_tools": "/v1/mcp/tools",
            "health": "/health",
            "green_room": "/v1/green-room/characters",
        },
    }


@app.get("/app")
async def serve_frontend():
    index = SERVE_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return FileResponse(FRONTEND_DIR / "index.html")


# Mount built React app assets (JS/CSS/images) — this MUST come after API routes
# so /v1/* is never caught by the SPA static mount.
if SERVE_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(SERVE_DIR / "assets")), name="webapp-assets")


# SPA catch-all: any non-API GET that hasn't been matched gets index.html
# (React Router handles client-side routing).
@app.get("/{path:path}")
async def spa_catchall(path: str):
    # Don't catch API routes or docs
    if path.startswith("v1/") or path.startswith("docs") or path.startswith("redoc") or path.startswith("openapi"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "not found"}, status_code=404)
    index = SERVE_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    from fastapi.responses import JSONResponse
    return JSONResponse({"error": "not found"}, status_code=404)
