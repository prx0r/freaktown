import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings

logger = logging.getLogger("freak_town")

# NOTE (migration): this FastAPI app is API-only infrastructure. It must NOT
# serve product HTML — no SPA root, no Green Room, no creator UI. Product
# surfaces live in the Flask shell (temporary) and contracts/ (canonical).



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

from backend.routes import admin, audience, episodes, motions, shows, judge, sound, intake  # noqa: E402

app.include_router(episodes.router, prefix="/v1/episodes", tags=["episodes"])
app.include_router(audience.router, prefix="/v1", tags=["audience"])
app.include_router(admin.router, prefix="/v1/admin", tags=["admin"])
app.include_router(motions.router, prefix="/v1", tags=["motions"])
app.include_router(shows.router, prefix="/v1", tags=["shows"])
app.include_router(judge.router, prefix="/v1", tags=["judge"])
app.include_router(sound.router, prefix="/v1", tags=["sound"])
app.include_router(intake.router, prefix="/v1", tags=["intake"])


# ── API Info ───────────────────────────────────────────────────────────

@app.get("/api")
async def api_info():
    return {
        "name": "Freak Town infrastructure API",
        "description": "Execution backend: intake, episodes, shows, judges, media metadata",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "intake": "/v1/intake/bundle",
            "episodes": "/v1/episodes/live",
            "shows": "/v1/shows",
        },
    }


# ── Health ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    """API index. Product HTML is Freak Town-owned and served elsewhere."""
    return {"name": "Freak Town infrastructure API", "docs": "/docs",
            "health": "/health", "intake": "/v1/intake/bundle"}
    index = SERVE_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    from fastapi.responses import JSONResponse
    return JSONResponse({"error": "not found"}, status_code=404)
