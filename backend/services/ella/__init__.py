"""Ella realtime subsystem — reflex rules, live presence, deep judge.

Tier 0 (reflex): deterministic <100ms reactions, no LLM.
Tier 1 (live): persistent realtime-model session, interruptions.
Tier 2 (judge): per-beat accumulator, authoritative verdict.
Tools: the theatre operations her model may invoke.
"""

from backend.services.ella.judge import (
    DIMENSIONS,
    AccumulatedBeat,
    BeatUpdate,
    EllaJudgeAccumulator,
)
from backend.services.ella.live import (
    PROVIDER_CONFIGS,
    EllaLiveSession,
    FakeLiveTransport,
    LiveTransport,
    provider_status,
)
from backend.services.ella.tools import (
    ELLA_TOOLS,
    EllaTool,
    get_tool,
    implemented_tools,
    planned_tools,
)

__all__ = [
    "DIMENSIONS",
    "AccumulatedBeat",
    "BeatUpdate",
    "EllaJudgeAccumulator",
    "PROVIDER_CONFIGS",
    "EllaLiveSession",
    "FakeLiveTransport",
    "LiveTransport",
    "provider_status",
    "ELLA_TOOLS",
    "EllaTool",
    "get_tool",
    "implemented_tools",
    "planned_tools",
]
