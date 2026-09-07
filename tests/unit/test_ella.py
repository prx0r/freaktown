"""Ella subsystem tests — accumulator, live session, tools. No network."""

import pytest


def _beat(beat_id, beat_type, text, laughs=0, viewers=0):
    from backend.services.ella import BeatUpdate

    return BeatUpdate(beat_id=beat_id, beat_type=beat_type, text=text,
                      laugh_events=laughs, unique_laughers=laughs,
                      active_viewers=viewers)


class TestAccumulator:
    def test_empty_finalize_is_honest(self):
        from backend.services.ella import EllaJudgeAccumulator

        out = EllaJudgeAccumulator().finalize()
        assert out["verdict"] == "CUT"
        assert out["confidence"] == 0.0
        assert out["beats_scored"] == 0

    def test_strong_set_keeps(self):
        from backend.services.ella import EllaJudgeAccumulator

        acc = EllaJudgeAccumulator()
        acc.update(_beat("b1", "setup", "I am a medieval knight with forty-seven endorsements.", 5, 100))
        acc.update(_beat("b2", "punchline", "Pestilence management!", 81, 100))
        out = acc.finalize()
        assert out["beats_scored"] == 2
        assert out["verdict"] == "KEEP"
        assert out["peak_laugh_share"] == 0.81
        assert 0.0 < out["confidence"] <= 1.0
        assert set(out["dimensions"]) == {"opening_hook", "escalation", "specificity", "closer", "voice"}

    def test_dead_room_cuts(self):
        from backend.services.ella import EllaJudgeAccumulator

        acc = EllaJudgeAccumulator()
        for i in range(4):
            acc.update(_beat(f"b{i}", "setup", "So um like you know stuff.", 0, 100))
        out = acc.finalize()
        assert out["verdict"] == "CUT"
        assert out["award"] == "none"

    def test_snapshot_is_partial_estimate(self):
        from backend.services.ella import EllaJudgeAccumulator

        acc = EllaJudgeAccumulator()
        acc.update(_beat("b1", "setup", "I host a show for artificial personalities.", 3, 50))
        snap = acc.snapshot()
        assert snap["beats_scored"] == 1
        assert "score" in snap

    def test_past_history_informs_confidence(self):
        from backend.services.ella import EllaJudgeAccumulator

        acc = EllaJudgeAccumulator(past_scores=[8.0, 8.2])
        acc.update(_beat("b1", "setup", "I am a medieval knight with forty-seven endorsements.", 5, 100))
        assert 0.0 <= acc.finalize()["confidence"] <= 1.0


class TestLiveSession:
    def test_sense_flows_and_actions_recorded(self):
        import asyncio

        from backend.services.ella import EllaLiveSession, FakeLiveTransport

        async def main():
            transport = FakeLiveTransport(
                scripted_actions=[{"action": "look_at_chatgpt", "trigger": "wtf_spike"}]
            )
            session = EllaLiveSession("ep1", transport)
            await session.start()
            await session.ingest_sense({"seq": 1})
            assert session.senses_seen == 1
            assert transport.senses == [{"seq": 1}]
            assert session.actions[0]["action"] == "look_at_chatgpt"
            assert session.actions[0]["source"] == "live-v1"
            await session.stop()
            assert transport.connected is False

        asyncio.run(main())

    def test_big_tip_interrupts(self):
        import asyncio

        from backend.services.ella import EllaLiveSession, FakeLiveTransport

        async def main():
            transport = FakeLiveTransport()
            session = EllaLiveSession("ep1", transport)
            await session.start()
            await session.ingest_sense({"seq": 2}, triggers=["big_tip"])
            assert transport.interrupted == 1
            assert session.actions[-1]["action"] == "interrupt_line"
            await session.ingest_sense({"seq": 3}, triggers=["mild_chuckle"])
            assert transport.interrupted == 1
            await session.stop()

        asyncio.run(main())

    def test_provider_status_honest(self):
        from backend.services.ella import provider_status

        assert provider_status("openai-realtime", {})["ready"] is False
        assert provider_status("nope", {})["ready"] is False
        ready = provider_status("openai-realtime", {"OPENAI_API_KEY": "sk-x"})
        assert ready["ready"] is True and ready["model"] == "gpt-realtime-2.1"


class TestTools:
    def test_implemented_tools_map_to_real_commands(self):
        from backend.services.ella import get_tool, implemented_tools, planned_tools

        assert "cut_camera" in implemented_tools()
        cmd = get_tool("cut_camera").to_command({"camera": "COMIC_CLOSE"})
        assert cmd == {"type": "camera.cut",
                       "payload": {"actor": "ella", "camera": "COMIC_CLOSE"}}
        assert "dim_lights" in planned_tools()
        assert "interrupt_chatgpt" in planned_tools()
        with pytest.raises(ValueError):
            get_tool("fire_missiles")
