"""Three-judge panel: Ella (real) + ChatGPT (wrong) + Stream (audience)."""

from backend.services.judge.panel import (
    JUDGE_VOICES,
    GUEST_JUDGES,
    JudgePanel,
    JudgeScore,
    PanelResult,
    aggregate_stream,
    generate_panel_argument,
    pick_guest_judge,
)

__all__ = [
    "JUDGE_VOICES",
    "GUEST_JUDGES",
    "JudgePanel",
    "JudgeScore",
    "PanelResult",
    "aggregate_stream",
    "generate_panel_argument",
    "pick_guest_judge",
]
