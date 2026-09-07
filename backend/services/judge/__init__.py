"""Three-judge panel: Ella (real) + ChatGPT (wrong) + Stream (audience)."""

from backend.services.judge.panel import (
    JUDGE_VOICES,
    GUEST_JUDGES,
    CHATGPT_PROSODY_RATE,
    JudgePanel,
    JudgeScore,
    PanelResult,
    aggregate_stream,
    generate_panel_argument,
    judge_voice_line,
    pick_guest_judge,
)

__all__ = [
    "JUDGE_VOICES",
    "GUEST_JUDGES",
    "CHATGPT_PROSODY_RATE",
    "JudgePanel",
    "JudgeScore",
    "PanelResult",
    "aggregate_stream",
    "generate_panel_argument",
    "judge_voice_line",
    "pick_guest_judge",
]
