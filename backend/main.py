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

from backend.routes import admin, audience, comedians, episodes, mcp, stage, motions, dressing_room, green_room, shows  # noqa: E402

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

@app.get("/")
async def root():
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
    return FileResponse(FRONTEND_DIR / "index.html")


# Mount static files last (catch-all)
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
