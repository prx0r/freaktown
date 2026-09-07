"""Wire contract mirror tests — same golden JSON as the Zod suite.

backend/contracts.py (Pydantic) must accept/reject exactly what
apps/web/src/contracts/show.ts accepts/rejects. If these drift, the
runtimes drift.
"""

import pytest
from pydantic import ValidationError

from backend.contracts import (
    CameraCutPayloadV1,
    CharacterModesV1,
    CrowdUpdateV1,
    JudgeReactPayloadV1,
    PanelSeatPayloadV1,
    PerformancePreloadPayloadV1,
    ReactionRawV1,
    ShowEventV1,
    SnapshotV1,
)

EVENT = {
    "seq": 943,
    "type": "camera.cut",
    "actor": "control",
    "payload": {"camera": "COMIC_CLOSE"},
    "created_at": "2026-09-07T19:00:00.000Z",
}

REACTION = {
    "seq": 101,
    "event_id": "123e4567-e89b-12d3-a456-426614174000",
    "episode_id": "ep1",
    "performance_id": "perf1",
    "session_id": "sess1",
    "client_seq": 81,
    "type": "reaction",
    "reaction": "laugh",
    "set_time_ms": 18322,
    "server_received_at": "2026-09-07T19:00:18.322Z",
    "source": "freaktown_web",
}


class TestContractsMirror:
    def test_event_ok(self):
        assert ShowEventV1(**EVENT).seq == 943

    def test_event_rejects_camel_timestamps(self):
        bad = {k: v for k, v in EVENT.items() if k != "created_at"}
        bad["createdAt"] = "2026-09-07T19:00:00.000Z"
        with pytest.raises(ValidationError):
            ShowEventV1(**bad)

    def test_reaction_ok(self):
        assert ReactionRawV1(**REACTION).client_seq == 81

    def test_reaction_rejects_bad_seq(self):
        with pytest.raises(ValidationError):
            ReactionRawV1(**{**REACTION, "client_seq": 0})

    def test_reaction_rejects_unknown_type(self):
        with pytest.raises(ValidationError):
            ReactionRawV1(**{**REACTION, "reaction": "scream"})

    def test_snapshot_ok(self):
        s = SnapshotV1(episode_id="ep1", phase="set_active",
                       active_appearance_id="a1", seq=42, is_paused=False)
        assert s.phase == "set_active"

    def test_crowd_ok(self):
        c = CrowdUpdateV1(laugh_events=10, claps=2, boos=0,
                          crickets=0, groans=1, unique_laughers=4)
        assert c.unique_laughers == 4

    def test_camera_cut_ok_and_strict(self):
        assert CameraCutPayloadV1(camera="COMIC_CLOSE",
                                  source="human_director").camera == "COMIC_CLOSE"
        with pytest.raises(ValidationError):
            CameraCutPayloadV1(camera="CLOSEUP", source="human_director")

    def test_preload_requires_urls(self):
        assert PerformancePreloadPayloadV1(
            performance_id="p", avatar_url="https://x/y.glb",
            audio_url="https://x/y.wav", plan={}).performance_id == "p"
        with pytest.raises(ValidationError):
            PerformancePreloadPayloadV1(performance_id="p", audio_url="u", plan={})

    def test_judge_cameras_accepted(self):
        assert CameraCutPayloadV1(camera="CHATGPT_CLOSE",
                                  source="human_director").camera == "CHATGPT_CLOSE"
        assert CameraCutPayloadV1(camera="STREAM_CLOSE",
                                  source="human_director").camera == "STREAM_CLOSE"

    def test_judge_react_vocabulary(self):
        assert JudgeReactPayloadV1(judge="ella", reaction="iris_narrow").reaction == "iris_narrow"
        with pytest.raises(ValidationError):
            JudgeReactPayloadV1(judge="ella", reaction="fireworks")

    def test_panel_seat(self):
        assert PanelSeatPayloadV1(seat="stream-left",
                                  character_id="c1").seat == "stream-left"
        with pytest.raises(ValidationError):
            PanelSeatPayloadV1(seat="middle", character_id="c1")

    def test_character_modes(self):
        m = CharacterModesV1(judge={"seat": "stream-left", "authority": "commentary"})
        assert m.judge is not None and m.judge.seat == "stream-left"
        with pytest.raises(ValidationError):
            CharacterModesV1(judge={"seat": "middle"})
