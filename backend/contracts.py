"""Shared wire contracts — Python mirror of apps/web/src/contracts/show.ts.

snake_case on the wire, everywhere. Golden fixtures
(tests/unit/test_contracts.py) validate both sides against the same JSON.
"""

from typing import Literal
from pydantic import BaseModel, Field

CameraPreset = Literal[
    "WIDE_STAGE", "COMIC_MEDIUM", "COMIC_CLOSE",
    "SIDE_STAGE", "PANEL_WIDE", "ELLA_CLOSE",
    "CHATGPT_CLOSE", "STREAM_CLOSE",
]

CAMERA_NAMES = list(CameraPreset.__args__)

JudgeReaction = Literal[
    "iris_narrow", "nod", "flare", "stillness",
    "pulse", "thinking", "glow", "freeze",
    "jitter", "burst", "morph",
]

PanelSeat = Literal["stream-left", "ella-center", "chatgpt-right"]


class ShowEventV1(BaseModel):
    seq: int = Field(ge=0)
    type: str = Field(min_length=1)
    actor: str = ""
    payload: dict = Field(default_factory=dict)
    created_at: str
    effective_at: str | None = None


class ReactionRawV1(BaseModel):
    seq: int = Field(ge=0)
    event_id: str
    episode_id: str
    performance_id: str
    session_id: str
    client_seq: int = Field(gt=0)
    type: str = "reaction"
    reaction: Literal["laugh", "clap", "boo", "crickets", "groan", "love", "wtf"]
    set_time_ms: float = 0
    server_received_at: str
    source: str

    model_config = {"extra": "allow"}


class SnapshotV1(BaseModel):
    episode_id: str
    phase: str
    active_appearance_id: str | None = None
    seq: int = Field(ge=0)
    is_paused: bool = False


class CrowdUpdateV1(BaseModel):
    laugh_events: int = Field(ge=0)
    claps: int = Field(ge=0)
    boos: int = Field(ge=0)
    crickets: int = Field(ge=0)
    groans: int = Field(ge=0)
    unique_laughers: int = Field(ge=0)


class CameraCutPayloadV1(BaseModel):
    camera: CameraPreset
    performance_id: str | None = None
    set_time_ms: float | None = None
    source: str

    model_config = {"extra": "allow"}


class PerformancePreloadPayloadV1(BaseModel):
    performance_id: str
    avatar_url: str
    audio_url: str
    walkout_url: str | None = None
    plan: dict = Field(default_factory=dict)
    word_timings: list = Field(default_factory=list)
    episode_id: str | None = None

    model_config = {"extra": "allow"}


class EllaSenseV1(BaseModel):
    episode_id: str
    phase: str
    active_appearance_id: str | None = None
    seq: int = Field(ge=0)
    is_paused: bool = False
    set_time_ms: float | None = None
    crowd: CrowdUpdateV1
    pot_cents: int = Field(ge=0)
    updated_at: str

    model_config = {"extra": "allow"}


EllaActionSource = Literal["reflex-v1", "live-v1", "judge-v1"]


class EllaActionV1(BaseModel):
    set_time_ms: float | None = None
    trigger: str
    action: str
    latency_ms: float = Field(ge=0)
    source: EllaActionSource
    text: str | None = None

    model_config = {"extra": "allow"}


class JudgeReactPayloadV1(BaseModel):
    judge: str
    reaction: JudgeReaction
    performance_id: str | None = None
    set_time_ms: float | None = None

    model_config = {"extra": "allow"}


class PanelSeatPayloadV1(BaseModel):
    seat: PanelSeat
    character_id: str | None = None
    character_name: str | None = None
    reason: str | None = None

    model_config = {"extra": "allow"}


class JudgeModeV1(BaseModel):
    seat: PanelSeat | None = None
    camera_profile: str | None = None
    animations: list[str] | None = None
    ui_theme: dict | None = None
    authority: Literal["full", "commentary", "none"] | None = None
    critique_persona: str | None = None

    model_config = {"extra": "allow"}


class CharacterModesV1(BaseModel):
    performer: dict | None = None
    judge: JudgeModeV1 | None = None

    model_config = {"extra": "allow"}
