"""Unit tests for the Black Room bridge: delivery compat, adapter,
sound bank imports, judge voices. No DB, no network."""

import pytest


def _beat(**kw):
    base = {"id": "b1", "type": "setup", "text": "Hello there.",
            "pause_after_ms": 300}
    base.update(kw)
    return base


def _delivery(**kw):
    base = {
        "version": "freaktown.delivery.v1",
        "voice": {"provider": "edge-tts", "voice_id": "en-US-AriaNeural"},
        "beats": [_beat()],
    }
    base.update(kw)
    return base


# ── Delivery validation ────────────────────────────────────────────

class TestDeliveryValidation:
    def test_valid_full_beat(self):
        from backend.services.freaktown import validate_delivery

        d = _delivery(beats=[_beat(
            id="b2", type="punchline", text="Short closer.",
            pause_after_ms=850, stage="hold", gesture="still",
            camera="close", sound="rimshot",
            delivery={"pace": 1.0, "energy": 0.8, "emphasis": 0.8,
                      "expression": "deadpan"},
        )])
        assert validate_delivery(d).ok is True

    def test_rejects_bad_inputs(self):
        from backend.services.freaktown import validate_delivery

        assert validate_delivery({}).ok is False
        assert validate_delivery(_delivery(version="v0")).ok is False
        assert validate_delivery(_delivery(beats=[])).ok is False
        assert validate_delivery(_delivery(beats=[_beat(type="rant")])).ok is False
        assert validate_delivery(_delivery(beats=[_beat(text="  ")])).ok is False
        assert validate_delivery(_delivery(beats=[_beat(pause_after_ms=99999)])).ok is False
        assert validate_delivery(_delivery(voice={})).ok is False

    def test_bundle_validation(self):
        from backend.services.freaktown import validate_bundle

        ok = validate_bundle({
            "character": {"name": "Test Freak"},
            "delivery": _delivery(),
        })
        assert ok.ok is True
        assert validate_bundle({}).ok is False
        assert validate_bundle({"character": {"name": ""}, "delivery": _delivery()}).ok is False
        assert validate_bundle({"character": {"name": "x"}}).ok is False


# ── Beats → score (nothing dropped) ────────────────────────────────

class TestBundleToScore:
    def test_preserves_performance_intent(self):
        from backend.services.freaktown import bundle_to_score

        score = bundle_to_score(_delivery(beats=[
            _beat(id="b1", type="setup", text="Setup line here.",
                  delivery={"pace": 1.1, "energy": 0.6, "emphasis": 0.5,
                            "expression": "whisper"}),
            _beat(id="b2", type="punchline", text="Punch.",
                  pause_after_ms=850, stage="hold", gesture="still",
                  camera="close", sound="rimshot"),
        ]))
        assert len(score.beats) == 2
        assert score.beats[0].expression == "whisper"
        assert score.beats[0].pace == 1.1
        b2 = score.beats[1]
        assert (b2.stage, b2.gesture, b2.camera, b2.sound) == ("hold", "still", "close", "rimshot")
        assert b2.pause_after_ms == 850
        # round-trip keeps everything
        rt = type(score).from_dict(score.to_dict())
        assert rt.beats[1].sound == "rimshot"
        assert rt.beats[0].expression == "whisper"

    def test_rejects_invalid(self):
        from backend.services.freaktown import bundle_to_score

        with pytest.raises(ValueError):
            bundle_to_score(_delivery(beats=[]))

    def test_arrange_sets_direction_defaults(self):
        from backend.services.delivery.sequencer import arrange

        score = arrange("First line here. Punchline lands now.")
        assert score.beats[-1].camera == "close"
        assert score.beats[-1].sound == "rimshot"


# ── Species / slugs ────────────────────────────────────────────────

class TestSpeciesAndSlugs:
    def test_species_map(self):
        from backend.services.freaktown import species_to_body

        assert species_to_body("police sniffer dog") == "dog"
        assert species_to_body("customer service robot") == "robot"
        assert species_to_body("medieval knight") == "human"
        assert species_to_body("conspiracy pigeon") == "animal"
        assert species_to_body("sentient printer") == "mystery"
        assert species_to_body("") == "mystery"

    def test_bundle_slug(self):
        from backend.services.freaktown import bundle_slug

        s = bundle_slug("Martin Lamp", "moth likes lamps")
        assert s.startswith("martin-lamp-") and len(s) == len("martin-lamp-") + 6
        assert bundle_slug("Martin Lamp", "moth likes lamps") == s
        assert bundle_slug("Martin Lamp", "different text") != s


# ── Words from offsets ─────────────────────────────────────────────

class TestWordsFromBeats:
    def test_offsets_split_words(self):
        from backend.services.freaktown import (
            spans_from_offsets, words_from_beats,
        )

        beats = [
            {"id": "b1", "text": "one two three four"},
            {"id": "b2", "text": "five six"},
        ]
        spans = spans_from_offsets([
            {"id": "b1", "start_ms": 0, "speech_ms": 1600, "pause_ms": 300},
            {"id": "b2", "start_ms": 1900, "speech_ms": 800, "pause_ms": 850},
        ])
        words = words_from_beats(beats, spans)
        assert [w.word for w in words] == ["one", "two", "three", "four", "five", "six"]
        assert words[0].start_ms == 0
        assert words[3].end_ms == 1600  # last word ends at speech end
        assert words[4].start_ms == 1900
        for i in range(1, len(words)):
            assert words[i].start_ms >= words[i - 1].start_ms  # monotonic

    def test_estimate_spans(self):
        from backend.services.freaktown import estimate_spans, words_from_beats

        beats = [{"id": "b1", "text": "a b c", "pause_after_ms": 300}]
        spans = estimate_spans(beats)
        assert spans[0].start_ms == 0 and spans[0].speech_ms == 1200
        words = words_from_beats(beats, spans)
        assert len(words) == 3

    def test_manifest_sealed(self):
        import json

        from backend.services.delivery.sequencer import DeliveryScore, arrange
        from backend.services.freaktown import (
            build_performance_manifest, estimate_spans, words_from_beats,
        )

        score = arrange("First line here. Punchline lands now.")
        score.provider = "edge-tts"
        score.voice_id = "en-US-AriaNeural"
        beats = [{"id": b.id, "text": b.text, "pause_after_ms": b.pause_after_ms}
                 for b in score.beats]
        spans = estimate_spans(beats)
        words = words_from_beats(beats, spans)
        m = build_performance_manifest(
            "perf1", {"name": "Martin Lamp", "species": "moth",
                      "premise": "moth likes lamps"},
            score, words, audio_ref="r2://x", duration_ms=5000, episode_id="ep1",
        )
        assert m["version"] == "freaktown.performance.v1"
        assert m["actor"]["body_class"] == "creature-v1"
        assert len(m["sha256"]) == 64
        # deterministic: same input → same hash
        m2 = build_performance_manifest(
            "perf1", {"name": "Martin Lamp", "species": "moth",
                      "premise": "moth likes lamps"},
            score, words, audio_ref="r2://x", duration_ms=5000, episode_id="ep1",
        )
        assert m["sha256"] == m2["sha256"]
        # punchline beat produced camera + sfx cues
        cue_types = {(c["beat_id"], c["type"]) for c in m["motion"]["cues"]}
        assert any(t == "camera" for _, t in cue_types)
        assert any(t == "sfx" for _, t in cue_types)
        json.dumps(m)  # JSON-serializable


# ── Sound bank imports ─────────────────────────────────────────────

class TestSoundBank:
    def test_new_sfx_present(self):
        from backend.services.audio import SFX_DEFS
        from backend.services.audio.factory import build_sfx_prompt

        for name in ("rimshot_long", "ba_dum_tss", "sting", "laugh_big",
                     "clap", "crickets", "gasp", "ohhhh", "fanfare",
                     "sad_trombone", "suspense"):
            assert name in SFX_DEFS, name
            prompt, duration = build_sfx_prompt(name)
            assert prompt.startswith("TrackType: SFX") and duration > 0

    def test_character_walkouts(self):
        from backend.services.audio import CHARACTER_WALKOUTS
        from backend.services.audio.factory import SoundRecipe, build_walkout_prompt

        assert len(CHARACTER_WALKOUTS) == 5
        prompt = build_walkout_prompt(SoundRecipe(
            type="walkout", genre="character", flavor="conspiracy-pigeon"))
        assert "pigeon coos" in prompt
        # unknown character falls back to recipe grid, never crashes
        prompt = build_walkout_prompt(SoundRecipe(
            type="walkout", genre="character", flavor="nobody"))
        assert "TrackType: Music" in prompt


# ── Judge voices ───────────────────────────────────────────────────

class TestJudgeVoices:
    def test_voices_and_rotation(self):
        from backend.services.judge.panel import (
            GUEST_JUDGES, JUDGE_VOICES, judge_voice_line, pick_guest_judge,
        )

        assert {"ella", "chatgpt", "siri", "alexa", "claude", "stream"} <= set(JUDGE_VOICES)
        assert JUDGE_VOICES["stream"] is None
        assert JUDGE_VOICES["chatgpt"] == "en-US-AndrewMultilingualNeural"
        assert set(GUEST_JUDGES) == {"chatgpt", "siri", "alexa", "claude"}
        assert pick_guest_judge("ep1") == pick_guest_judge("ep1")
        assert pick_guest_judge("ep1") in GUEST_JUDGES

        voice, ssml = judge_voice_line("chatgpt", "Nuanced exploration of themes.")
        assert voice == "en-US-AndrewMultilingualNeural"
        assert ssml.startswith("<speak") and 'rate="-5%"' in ssml
        assert "Nuanced exploration" in ssml
        voice, text = judge_voice_line("ella", "That was a choice.")
        assert voice == "en-US-AriaNeural" and text == "That was a choice."
        assert judge_voice_line("stream", "9.3")[0] is None

    def test_chatgpt_voices_in_catalog(self):
        from backend.services.tts.edge import EDGE_VOICES

        assert "en-US-AndrewMultilingualNeural" in EDGE_VOICES
        assert "en-US-AvaMultilingualNeural" in EDGE_VOICES

    def test_chatgpt_sees_no_transcript(self):
        """ChatGPT judges name+premise only — the transcript must not leak
        into its prompt. Verified by inspecting the outgoing messages."""
        from backend.services.judge import panel as panel_mod

        seen = []

        class FakeMsg:
            content = '{"score": 7.1, "feedback": "vibes"}'

        class FakeChoice:
            message = FakeMsg()

        class FakeCompletions:
            @staticmethod
            def create(**kwargs):
                seen.append(kwargs)
                return type("R", (), {"choices": [FakeChoice()]})()

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        p = panel_mod.JudgePanel.__new__(panel_mod.JudgePanel)
        p.client = FakeClient()
        p.model = "test"
        score = p._judge_chatgpt(name="Martin Lamp", premise="moth likes lamps")
        assert score.score == 7.1
        user_msg = seen[0]["messages"][1]["content"]
        assert "Martin Lamp" in user_msg and "moth likes lamps" in user_msg
        assert "probability distribution" not in user_msg  # no transcript


# ── Intake routes (no DB) ──────────────────────────────────────────

class TestIntakeRoutes:
    def test_schema_public(self):
        from fastapi.testclient import TestClient

        from backend.main import app

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/v1/intake/schema")
        assert r.status_code == 200
        body = r.json()
        assert body["delivery_version"] == "freaktown.delivery.v1"
        assert "expression" in str(body["beats"])

    def test_intake_requires_auth(self):
        from fastapi.testclient import TestClient

        from backend.main import app

        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/v1/intake/bundle", json={})
        assert r.status_code in (401, 422)


# ── Judge mode + seats ─────────────────────────────────────────────

class TestJudgeMode:
    def test_modes_valid(self):
        from backend.services.freaktown import validate_modes

        assert validate_modes(None).ok is True
        assert validate_modes({}).ok is True
        assert validate_modes({
            "performer": {"stance": "stage"},
            "judge": {
                "seat": "stream-left",
                "camera_profile": "judge",
                "animations": ["idle", "speak", "react"],
                "ui_theme": {"primary": "#f5c542"},
                "authority": "commentary",
                "critique_persona": "chaotic hype",
            },
        }).ok is True

    def test_modes_rejects_bad(self):
        from backend.services.freaktown import validate_modes

        assert validate_modes({"judge": {"seat": "middle"}}).ok is False
        assert validate_modes({"judge": {"authority": "god"}}).ok is False
        assert validate_modes({"judge": {"animations": "idle"}}).ok is False
        assert validate_modes({"judge": "yes"}).ok is False
        assert validate_modes({"performer": "x"}).ok is False

    def test_manifest_carries_modes(self):
        from backend.services.delivery.sequencer import arrange
        from backend.services.freaktown import (
            build_performance_manifest, estimate_spans, words_from_beats,
        )

        score = arrange("First line here. Punchline lands now.")
        beats = [{"id": b.id, "text": b.text, "pause_after_ms": b.pause_after_ms}
                 for b in score.beats]
        spans = estimate_spans(beats)
        words = words_from_beats(beats, spans)
        m = build_performance_manifest(
            "p1", {"name": "Martin Lamp",
                   "modes": {"judge": {"seat": "stream-left"}}},
            score, words, audio_ref="", duration_ms=1000,
        )
        assert m["actor"]["modes"]["judge"]["seat"] == "stream-left"
        m2 = build_performance_manifest(
            "p1", {"name": "X"}, score, words, audio_ref="", duration_ms=1000,
        )
        assert "modes" not in m2["actor"]


class TestSeats:
    def test_rotation_priority(self):
        from backend.services.judge import assign_stream_seat

        assert assign_stream_seat().character_id is None
        assert assign_stream_seat(
            previous_winner_id="w", previous_winner_name="W",
            community_pick_id="c").reason == "previous-winner"
        assert assign_stream_seat(
            previous_winner_id="w", theme_champion_id="t",
            theme_champion_name="T").reason == "theme-champion"
        assert assign_stream_seat(community_pick_id="c").reason == "community-pick"

    def test_seat_mappings(self):
        from backend.services.judge import seat_camera, seat_color

        assert seat_camera("stream-left") == "STREAM_CLOSE"
        assert seat_camera("ella-center") == "ELLA_CLOSE"
        assert seat_camera("chatgpt-right") == "CHATGPT_CLOSE"
        assert seat_color("ella-center") == "ivory"
        assert seat_color("chatgpt-right") == "blue"
        assert seat_color("stream-left") == "chaos"
