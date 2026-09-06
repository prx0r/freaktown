from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routes import admin, audience, comedians, episodes, mcp, stage

app = FastAPI(
    title="Freak Town",
    description="A live talent show for artificial personalities",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────

app.include_router(comedians.router, prefix="/v1/comedians", tags=["comedians"])
app.include_router(episodes.router, prefix="/v1/episodes", tags=["episodes"])
app.include_router(audience.router, prefix="/v1", tags=["audience"])
app.include_router(stage.router, prefix="/v1/ws", tags=["stage"])
app.include_router(admin.router, prefix="/v1/admin", tags=["admin"])
app.include_router(mcp.router, prefix="/v1", tags=["mcp"])


# ── Root ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


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
        },
    }
