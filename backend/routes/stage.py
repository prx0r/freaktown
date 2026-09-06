"""Stage routes — re-exports the stage WebSocket from audience module."""

from fastapi import APIRouter
from backend.routes.audience import stage_ws  # noqa: F401

router = APIRouter()
