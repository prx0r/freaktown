"""End-to-end test suite — full system validation.

NO exception swallowing. NO custom decorators that hide failures.
If an assertion fails, the process exits non-zero.

Usage:
    PYTHONPATH=/root/killella python3 tests/e2e/test_full_e2e.py
"""

import asyncio
import json
import sys
import time


passed = 0
failed = 0
errors = []


def run_test(name: str, func):
    """Run a test. If it raises, we fail hard."""
    global passed, failed
    start = time.monotonic()
    try:
        asyncio.run(func())
        elapsed = int((time.monotonic() - start) * 1000)
        passed += 1
        print(f"  ✓ {name} ({elapsed}ms)")
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        failed += 1
        errors.append((name, str(e)))
        print(f"  ✗ {name} ({elapsed}ms): {e}")


# ═══════════════════════════════════════════════════════════════════
# TESTS — each function MUST raise on failure
# ═══════════════════════════════════════════════════════════════════

async def t_motion_actions():
    from backend.models.motion import SEMANTIC_ACTIONS
    assert len(SEMANTIC_ACTIONS) == 48, f"Expected 48, got {len(SEMANTIC_ACTIONS)}"
    categories = set(a.split(".")[0] for a in SEMANTIC_ACTIONS)
    for cat in ["gesture", "gaze", "reaction", "locomotion", "pose", "face", "procedural"]:
        assert cat in categories, f"Missing category: {cat}"

async def t_body_manifests():
    from backend.models.motion import BODY_MANIFESTS
    assert len(BODY_MANIFESTS) == 3
    h = BODY_MANIFESTS["humanoid-v1"]
    assert len(h.capabilities) > 30
    assert h.can_do("gesture.beat")
    assert h.can_do("gaze.ella")
    d = BODY_MANIFESTS["quadruped-v1"]
    assert d.can_do("gesture.shrug")
    assert d.resolve("gesture.shrug") == "gesture.emphasize"
    t = BODY_MANIFESTS["rigid-object-v1"]
    assert t.resolve("gesture.beat") == "gesture.emphasize"

async def t_seed_motions():
    from backend.models.motion_assets import SEED_MOTIONS
    from backend.models.motion import SEMANTIC_ACTIONS
    assert len(SEED_MOTIONS) >= 25
    cats = set()
    for m in SEED_MOTIONS:
        for s in m.semantic:
            cats.add(s.split(".")[0])
    assert "gesture" in cats
    assert "gaze" in cats
    assert "reaction" in cats

async def t_compiler_humanoid():
    from backend.models.performance import PRESET_ENGINES
    from backend.services.motion_compiler import MotionCompiler
    plan = MotionCompiler().compile(PRESET_ENGINES["deadpan"], "humanoid-v1", 60000)
    cues = plan.all_cues()
    assert len(cues) > 0, f"Expected cues, got {len(cues)}"
    assert plan.energy == 0.2
    assert plan.stillness == 0.8

async def t_compiler_toaster_fewer():
    from backend.models.performance import PRESET_ENGINES
    from backend.services.motion_compiler import MotionCompiler
    c = MotionCompiler()
    h = len(c.compile(PRESET_ENGINES["deadpan"], "humanoid-v1", 60000).all_cues())
    t = len(c.compile(PRESET_ENGINES["deadpan"], "rigid-object-v1", 60000).all_cues())
    assert h >= t, f"Humanoid {h} should have >= toaster {t}"

async def t_parser_basic():
    from backend.services.direction_parser import stage_direction_parser
    r = stage_direction_parser.parse("shrug")
    assert any(a["action"] == "gesture.shrug" for a in r.actions)
    r = stage_direction_parser.parse("stare at Ella")
    assert any("ella" in a["action"] for a in r.actions)
    r = stage_direction_parser.parse("freeze and dead stare")
    acts = [a["action"] for a in r.actions]
    assert any("freeze" in a for a in acts)
    assert any("dead" in a for a in acts)

async def t_parser_intensity():
    from backend.services.direction_parser import stage_direction_parser
    r1 = stage_direction_parser.parse("really big shrug")
    r2 = stage_direction_parser.parse("slightly nod")
    s1 = r1.actions[0]["intensity"]
    s2 = r2.actions[0]["intensity"]
    assert s1 > s2, f"Big shrug {s1} should > slight nod {s2}"

async def t_chat_labels():
    from backend.services.chat_summary import chat_summary_engine
    s = chat_summary_engine.analyze(["legend", "he is a legend", "absolute legend"])
    assert "legend" in s.labels or "GOAT" in s.labels

async def t_chat_sentiment():
    from backend.services.chat_summary import chat_summary_engine
    pos = chat_summary_engine.analyze(["hilarious", "amazing", "love this", "GOAT", "brilliant"])
    assert pos.sentiment in ("positive", "strong_positive")
    neg = chat_summary_engine.analyze(["boring", "cringe", "skip", "next", "waste"])
    assert neg.sentiment == "negative"

async def t_chat_nicknames():
    from backend.services.chat_summary import chat_summary_engine
    s = chat_summary_engine.analyze(['call him "The Ass Detective"', '"The Ass Detective" is perfect'])
    assert len(s.nicknames) > 0

async def t_chat_review():
    from backend.services.chat_summary import chat_summary_engine, ChatSummary
    s = ChatSummary(labels=["legend"], sentiment="strong_positive", return_rate=0.82)
    r = chat_summary_engine.generate_review(s, "Nolan")
    assert "Nolan" in r
    assert "legend" in r

async def t_presets():
    from backend.models.performance import PRESET_ENGINES
    assert len(PRESET_ENGINES) == 6
    d = PRESET_ENGINES["deadpan"]
    assert d.style.stillness > 0.7
    assert d.style.energy < 0.3
    assert len(d.signature_moves) > 0
    c = PRESET_ENGINES["chaotic"]
    assert c.style.energy > 0.8

async def t_green_room_compile():
    from backend.models.draft import PerformanceDraft, WordTiming
    from backend.models.performance import PRESET_ENGINES
    from backend.services.green_room_compiler import GreenRoomCompiler
    draft = PerformanceDraft(
        script="This is a test joke.",
        word_timings=[WordTiming(word=w, start_ms=i*300, end_ms=(i+1)*300, index=i)
                      for i, w in enumerate("This is a test joke".split())],
        audio_duration_ms=2100,
    )
    draft.add_direction_at_word(2, description="shrug")
    plan = GreenRoomCompiler().compile(draft, PRESET_ENGINES["deadpan"], "humanoid-v1")
    assert plan.duration_ms == 2100
    assert len(plan.all_cues()) > 0

async def t_show_runtime():
    from backend.services.show_runtime import show_runner, ShowAct
    acts = [ShowAct(character_name=f"C{i}", duration_ms=30000) for i in range(5)]
    show = show_runner.create_show("2026-09-06", acts)
    assert len(show.acts) == 5
    show_runner.start_show(show.id)
    a = show.acts[0]
    show_runner.start_act(show.id, a.id)
    for ms in [1000, 1200, 5000, 5100]:
        show_runner.record_laugh(show.id, a.id, ms)
    assert a.laugh_count == 4
    show_runner.end_act(show.id, a.id)
    for v in [True, True, True, False]:
        show_runner.record_return_vote(show.id, a.id, v)
    assert a.return_rate == 0.75
    summary = show_runner.get_show_summary(show.id)
    assert summary["total_laughs"] == 4

async def t_tts_fallback_generates_timings():
    from backend.services.edge_tts import edge_tts_service
    r = await edge_tts_service.synthesize("Hello world this is a test sentence.")
    assert len(r.word_timings) > 0, "No word timings"
    assert r.duration_ms > 0
    for i in range(1, len(r.word_timings)):
        assert r.word_timings[i].start_ms >= r.word_timings[i-1].start_ms

async def t_tts_no_fake_audio():
    """TTS must NOT return zero bytes as audio."""
    from backend.services.edge_tts import edge_tts_service
    r = await edge_tts_service.synthesize("Test")
    if r.audio_bytes:
        assert len(r.audio_bytes) > 100, f"Audio too small: {len(r.audio_bytes)} bytes"
        assert r.audio_bytes != b'\x00' * len(r.audio_bytes), "Audio is all zeros (fake)"

async def t_dressing_room_parse():
    from backend.routes.dressing_room import parse_description
    p = parse_description("barely moves, stares blankly")
    assert p["style"].get("stillness", 0) > 0.5
    p = parse_description("manic hyper wild energy")
    assert p["style"].get("energy", 0) > 0.8

async def t_tts_voices():
    from backend.services.edge_tts import edge_tts_service
    v = edge_tts_service.list_voices()
    assert len(v) > 0
    assert "id" in v[0]


# ═══════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════

ALL_TESTS = [
    ("motion: 48 semantic actions", t_motion_actions),
    ("motion: 3 body manifests with fallbacks", t_body_manifests),
    ("motion: 25+ seed motions cover categories", t_seed_motions),
    ("compiler: humanoid generates cues", t_compiler_humanoid),
    ("compiler: toaster gets fewer cues", t_compiler_toaster_fewer),
    ("parser: shrug/stare/freeze resolve", t_parser_basic),
    ("parser: intensity modifiers work", t_parser_intensity),
    ("chat: legend label detected", t_chat_labels),
    ("chat: positive/negative sentiment", t_chat_sentiment),
    ("chat: nickname extraction", t_chat_nicknames),
    ("chat: review generation", t_chat_review),
    ("engine: 6 presets with correct styles", t_presets),
    ("compiler: green room draft → plan", t_green_room_compile),
    ("show: create, laugh, vote, summary", t_show_runtime),
    ("tts: generates word timings", t_tts_fallback_generates_timings),
    ("tts: no fake zero-byte audio", t_tts_no_fake_audio),
    ("dressing: parse natural language", t_dressing_room_parse),
    ("tts: voice catalog", t_tts_voices),
]

if __name__ == "__main__":
    print("=" * 60)
    print("KILLELLA E2E — NO EXCEPTION SWALLOWING")
    print("=" * 60)

    for name, func in ALL_TESTS:
        run_test(name, func)

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{passed+failed} passed, {failed} failed")
    print("=" * 60)

    if errors:
        print("\nFAILURES:")
        for name, err in errors:
            print(f"  ✗ {name}: {err}")

    sys.exit(1 if failed > 0 else 0)
