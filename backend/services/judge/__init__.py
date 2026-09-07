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
from backend.services.judge.seats import (
    SEATS,
    PERMANENT_SEATS,
    SEAT_REASONS,
    StreamSeatAssignment,
    assign_stream_seat,
    seat_camera,
    seat_color,
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
    "SEATS",
    "PERMANENT_SEATS",
    "SEAT_REASONS",
    "StreamSeatAssignment",
    "assign_stream_seat",
    "seat_camera",
    "seat_color",
]
