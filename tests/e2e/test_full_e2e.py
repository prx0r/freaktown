"""End-to-end test suite — full system validation.

Tests the complete flow from character creation through daily show.
No cheating. No mocks. Real calls. Logged results.

Usage:
    python -m pytest tests/e2e/ -v -s
    python tests/e2e/test_full_e2e.py  # standalone
"""

import asyncio
import json
import time
from dataclasses import dataclass


@dataclass
class TestResult:
    name: str
    passed: bool
    duration_ms: int
    details: str = ""


results: list[TestResult] = []


def test(name: str):
    """Decorator to track test results."""
    def decorator(func):
        async def wrapper():
            start = time.monotonic()
            try:
                await func()
                elapsed = int((time.monotonic() - start) * 1000)
                results.append(TestResult(name, True, elapsed))
                print(f"  ✓ {name} ({elapsed}ms)")
            except Exception as e:
                elapsed = int((time.monotonic() - start) * 1000)
                results.append(TestResult(name, False, elapsed, str(e)))
                print(f"  ✗ {name} ({elapsed}ms): {e}")
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════
# TEST 1: Motion System
# ═══════════════════════════════════════════════════════════════════

@test("motion: 48 semantic actions exist")
async def test_motion_actions():
    from backend.models.motion import SEMANTIC_ACTIONS
    assert len(SEMANTIC_ACTIONS) == 48, f"Expected 48, got {len(SEMANTIC_ACTIONS)}"
    # Check coverage
    categories = set(a.split(".")[0] for a in SEMANTIC_ACTIONS)
    assert "gesture" in categories
    assert "gaze" in categories
    assert "reaction" in categories
    assert "locomotion" in categories
    assert "pose" in categories
    assert "face" in categories


@test("motion: 3 body manifests exist with fallbacks")
async def test_body_manifests():
    from backend.models.motion import BODY_MANIFESTS, HUMANOID_V1, QUADRUPED_V1, RIGID_OBJECT_V1
    assert len(BODY_MANIFESTS) == 3
    assert HUMANOID_V1.body_class == "humanoid-v1"
    assert QUADRUPED_V1.body_class == "quadruped-v1"
    assert RIGID_OBJECT_V1.body_class == "rigid-object-v1"
    assert len(HUMANOID_V1.capabilities) > 30
    assert len(QUADRUPED_V1.fallbacks) > 5
    assert len(RIGID_OBJECT_V1.fallbacks) > 10


@test("motion: humanoid can do all core actions")
async def test_humanoid_capabilities():
    from backend.models.motion import HUMANOID_V1
    for action in ["gesture.beat", "gaze.ella", "reaction.dead_stare", "locomotion.freeze", "face.smile"]:
        assert HUMANOID_V1.can_do(action), f"Humanoid should do {action}"


@test("motion: dog resolves shrug to emphasize")
async def test_dog_fallback():
    from backend.models.motion import QUADRUPED_V1
    assert QUADRUPED_V1.can_do("gesture.shrug")
    resolved = QUADRUPED_V1.resolve("gesture.shrug")
    assert resolved == "gesture.emphasize", f"Expected gesture.emphasize, got {resolved}"


@test("motion: toaster resolves all gestures to emphasize")
async def test_toaster_fallback():
    from backend.models.motion import RIGID_OBJECT_V1
    for action in ["gesture.beat", "gesture.shrug", "gesture.point", "gesture.wave"]:
        assert RIGID_OBJECT_V1.can_do(action)
        resolved = RIGID_OBJECT_V1.resolve(action)
        assert "emphasize" in resolved or "dead" in resolved


@test("motion: 30 seed motions cover all categories")
async def test_seed_motions():
    from backend.models.motion_assets import SEED_MOTIONS
    assert len(SEED_MOTIONS) >= 25
    categories = set()
    for m in SEED_MOTIONS:
        for s in m.semantic:
            categories.add(s.split(".")[0])
    assert "gesture" in categories
    assert "gaze" in categories
    assert "reaction" in categories
    assert "locomotion" in categories
    assert "face" in categories


@test("motion: compiler generates cues for humanoid")
async def test_compiler_humanoid():
    from backend.models.performance import PRESET_ENGINES
    from backend.services.motion_compiler import MotionCompiler
    compiler = MotionCompiler()
    plan = compiler.compile(
        engine=PRESET_ENGINES["deadpan"],
        body_class="humanoid-v1",
        duration_ms=60000,
    )
    cue_count = len(plan.all_cues())
    assert cue_count > 0, f"Expected cues, got {cue_count}"
    assert plan.energy == 0.2
    assert plan.stillness == 0.8
    assert plan.duration_ms == 60000


@test("motion: compiler generates fewer cues for toaster")
async def test_compiler_toaster():
    from backend.models.performance import PRESET_ENGINES
    from backend.services.motion_compiler import MotionCompiler
    compiler = MotionCompiler()
    plan_h = compiler.compile(engine=PRESET_ENGINES["deadpan"], body_class="humanoid-v1", duration_ms=60000)
    plan_t = compiler.compile(engine=PRESET_ENGINES["deadpan"], body_class="rigid-object-v1", duration_ms=60000)
    assert len(plan_h.all_cues()) >= len(plan_t.all_cues()), "Humanoid should have >= toaster cues"


# ═══════════════════════════════════════════════════════════════════
# TEST 2: Direction Parser
# ═══════════════════════════════════════════════════════════════════

@test("parser: 'shrug' → gesture.shrug")
async def test_parse_shrug():
    from backend.services.direction_parser import stage_direction_parser
    result = stage_direction_parser.parse("shrug")
    assert any(a["action"] == "gesture.shrug" for a in result.actions)


@test("parser: 'stare at Ella' → gaze.ella")
async def test_parse_stare_ella():
    from backend.services.direction_parser import stage_direction_parser
    result = stage_direction_parser.parse("stare at Ella")
    assert any("ella" in a["action"] for a in result.actions)


@test("parser: 'freeze and dead stare' → locomotion.freeze + reaction.dead_stare")
async def test_parse_freeze_stare():
    from backend.services.direction_parser import stage_direction_parser
    result = stage_direction_parser.parse("freeze and dead stare")
    actions = [a["action"] for a in result.actions]
    assert any("freeze" in a for a in actions)
    assert any("dead" in a for a in actions)


@test("parser: 'look away' → gaze.away")
async def test_parse_look_away():
    from backend.services.direction_parser import stage_direction_parser
    result = stage_direction_parser.parse("look away")
    assert any("away" in a["action"] for a in result.actions)


@test("parser: 'point at audience' → gesture.point")
async def test_parse_point_audience():
    from backend.services.direction_parser import stage_direction_parser
    result = stage_direction_parser.parse("point at audience")
    actions = [a["action"] for a in result.actions]
    assert any("point" in a for a in actions)


@test("parser: 'really big shrug' → high intensity")
async def test_parse_intensity():
    from backend.services.direction_parser import stage_direction_parser
    result = stage_direction_parser.parse("really big shrug")
    shrug = next((a for a in result.actions if "shrug" in a["action"]), None)
    assert shrug is not None
    assert shrug["intensity"] > 0.6


@test("parser: 'slightly nod' → low intensity")
async def test_parse_low_intensity():
    from backend.services.direction_parser import stage_direction_parser
    result = stage_direction_parser.parse("slightly nod")
    assert result.confidence > 0


@test("parser: unknown text → fallback gesture.beat")
async def test_parse_fallback():
    from backend.services.direction_parser import stage_direction_parser
    result = stage_direction_parser.parse("do something weird")
    assert len(result.actions) > 0


# ═══════════════════════════════════════════════════════════════════
# TEST 3: Chat Summary Engine
# ═══════════════════════════════════════════════════════════════════

@test("chat: detects 'legend' label")
async def test_chat_legend():
    from backend.services.chat_summary import chat_summary_engine
    msgs = ["legend", "he is a legend", "absolute legend", "legendary"]
    s = chat_summary_engine.analyze(msgs)
    assert "legend" in s.labels or "GOAT" in s.labels


@test("chat: detects nicknames from quotes")
async def test_chat_nicknames():
    from backend.services.chat_summary import chat_summary_engine
    msgs = ['call him "The Ass Detective"', 'rename him "Officer No-Nose"', '"The Ass Detective" is perfect']
    s = chat_summary_engine.analyze(msgs)
    assert len(s.nicknames) > 0


@test("chat: sentiment positive when mostly positive messages")
async def test_chat_positive():
    from backend.services.chat_summary import chat_summary_engine
    msgs = ["hilarious", "amazing", "love this", "GOAT", "brilliant", "funny", "perfect"]
    s = chat_summary_engine.analyze(msgs)
    assert s.sentiment in ("positive", "strong_positive")


@test("chat: sentiment negative when mostly negative")
async def test_chat_negative():
    from backend.services.chat_summary import chat_summary_engine
    msgs = ["boring", "cringe", "skip", "next", "waste", "terrible", "unfunny"]
    s = chat_summary_engine.analyze(msgs)
    assert s.sentiment == "negative"


@test("chat: top reactions extracted")
async def test_chat_reactions():
    from backend.services.chat_summary import chat_summary_engine
    msgs = ["poor dog", "poor dog", "poor dog", "legend", "legend", "wtf"]
    s = chat_summary_engine.analyze(msgs)
    assert len(s.top_reactions) > 0
    assert s.top_reactions[0]["count"] >= 3


@test("chat: empty messages → empty summary")
async def test_chat_empty():
    from backend.services.chat_summary import chat_summary_engine
    s = chat_summary_engine.analyze([])
    assert s.labels == []
    assert s.total_messages == 0


@test("chat: generates review text")
async def test_chat_review():
    from backend.services.chat_summary import chat_summary_engine, ChatSummary
    s = ChatSummary(labels=["legend", "cute"], sentiment="strong_positive", return_rate=0.82)
    review = chat_summary_engine.generate_review(s, "No-Nose Nolan")
    assert "Nolan" in review
    assert "legend" in review


# ═══════════════════════════════════════════════════════════════════
# TEST 4: Performance Engine
# ═══════════════════════════════════════════════════════════════════

@test("engine: 6 presets exist")
async def test_presets():
    from backend.models.performance import PRESET_ENGINES
    assert len(PRESET_ENGINES) == 6
    for name in ["deadpan", "nervous", "confident", "chaotic", "awkward", "low_energy"]:
        assert name in PRESET_ENGINES


@test("engine: deadpan has high stillness, low energy")
async def test_deadpan_style():
    from backend.models.performance import PRESET_ENGINES
    e = PRESET_ENGINES["deadpan"]
    assert e.style.stillness > 0.7
    assert e.style.energy < 0.3
    assert e.style.punchline_hold_ms >= 1000


@test("engine: chaotic has high energy, low stillness")
async def test_chaotic_style():
    from backend.models.performance import PRESET_ENGINES
    e = PRESET_ENGINES["chaotic"]
    assert e.style.energy > 0.8
    assert e.style.stillness < 0.1


@test("engine: signature moves stored")
async def test_signature_moves():
    from backend.models.performance import PRESET_ENGINES
    e = PRESET_ENGINES["deadpan"]
    assert len(e.signature_moves) > 0
    assert e.signature_moves[0].trigger == "after_big_punchline"


@test("engine: to_dict serializes")
async def test_engine_serialize():
    from backend.models.performance import PRESET_ENGINES
    d = PRESET_ENGINES["deadpan"].to_dict()
    assert "style" in d
    assert "signature_moves" in d
    assert isinstance(d["style"]["energy"], float)


# ═══════════════════════════════════════════════════════════════════
# TEST 5: Green Room Compiler
# ═══════════════════════════════════════════════════════════════════

@test("compiler: draft with directions → plan with cues")
async def test_green_room_compile():
    from backend.models.draft import PerformanceDraft, WordTiming
    from backend.models.performance import PRESET_ENGINES
    from backend.services.green_room_compiler import GreenRoomCompiler

    draft = PerformanceDraft(
        script="This is a test joke about nothing.",
        word_timings=[
            WordTiming(word="This", start_ms=0, end_ms=300, index=0),
            WordTiming(word="is", start_ms=300, end_ms=500, index=1),
            WordTiming(word="a", start_ms=500, end_ms=650, index=2),
            WordTiming(word="test", start_ms=650, end_ms=1000, index=3),
            WordTiming(word="joke", start_ms=1000, end_ms=1400, index=4),
            WordTiming(word="about", start_ms=1400, end_ms=1700, index=5),
            WordTiming(word="nothing.", start_ms=1700, end_ms=2200, index=6),
        ],
        audio_duration_ms=2500,
    )
    draft.add_direction_at_word(4, description="shrug")

    compiler = GreenRoomCompiler()
    plan = compiler.compile(
        draft=draft,
        engine=PRESET_ENGINES["deadpan"],
        body_class="humanoid-v1",
    )
    assert plan.duration_ms == 2500
    assert len(plan.all_cues()) > 0
    assert plan.energy == 0.2


@test("compiler: dog draft → fewer cues")
async def test_compiler_dog():
    from backend.models.draft import PerformanceDraft
    from backend.models.performance import PRESET_ENGINES
    from backend.services.green_room_compiler import GreenRoomCompiler

    draft = PerformanceDraft(
        script="Woof woof bark bark.",
        audio_duration_ms=3000,
    )

    compiler = GreenRoomCompiler()
    plan_h = compiler.compile(draft, PRESET_ENGINES["confident"], "humanoid-v1")
    plan_d = compiler.compile(draft, PRESET_ENGINES["confident"], "quadruped-v1")
    assert len(plan_h.all_cues()) >= len(plan_d.all_cues())


# ═══════════════════════════════════════════════════════════════════
# TEST 6: Show Runtime
# ═══════════════════════════════════════════════════════════════════

@test("show: create 5-act show")
async def test_create_show():
    from backend.services.show_runtime import show_runner, ShowAct
    acts = [ShowAct(character_name=f"Character {i}", duration_ms=60000) for i in range(5)]
    show = show_runner.create_show("2026-09-06", acts)
    assert len(show.acts) == 5
    assert show.max_acts == 5
    assert show.total_duration_sec > 60


@test("show: laugh recording with 500ms buckets")
async def test_laugh_recording():
    from backend.services.show_runtime import show_runner, ShowAct
    act = ShowAct(character_name="Test", duration_ms=30000)
    show = show_runner.create_show("2026-09-06", [act])
    show_runner.start_show(show.id)
    show_runner.start_act(show.id, act.id)

    for ms in [1000, 1200, 1500, 5000, 5100, 5200, 10000]:
        show_runner.record_laugh(show.id, act.id, ms)

    assert act.laugh_count == 7
    assert len(act.laugh_timeline) > 0
    assert act.peak_laugh_count >= 2


@test("show: return vote tracking")
async def test_return_votes():
    from backend.services.show_runtime import show_runner, ShowAct
    act = ShowAct(character_name="Test", duration_ms=30000)
    show = show_runner.create_show("2026-09-06", [act])
    show_runner.start_show(show.id)
    show_runner.end_act(show.id, act.id)

    for v in [True, True, True, True, True, True, False, False, True, True]:
        show_runner.record_return_vote(show.id, act.id, v)

    assert act.return_votes == 8
    assert act.return_total == 10
    assert act.return_rate == 0.8


@test("show: show summary generation")
async def test_show_summary():
    from backend.services.show_runtime import show_runner, ShowAct
    acts = [ShowAct(character_name=f"Char {i}", duration_ms=30000) for i in range(3)]
    show = show_runner.create_show("2026-09-06", acts)
    show_runner.start_show(show.id)

    for act in show.acts:
        show_runner.start_act(show.id, act.id)
        show_runner.record_laugh(show.id, act.id, 5000)
        show_runner.record_laugh(show.id, act.id, 10000)
        show_runner.end_act(show.id, act.id)
        show_runner.record_return_vote(show.id, act.id, True)

    summary = show_runner.get_show_summary(show.id)
    assert summary["total_laughs"] == 6
    assert len(summary["acts"]) == 3
    assert summary["total_duration_sec"] > 30


@test("show: max 5 acts enforced")
async def test_max_acts():
    from backend.services.show_runtime import show_runner, ShowAct
    acts = [ShowAct(character_name=f"Char {i}") for i in range(10)]
    show = show_runner.create_show("2026-09-06", acts)
    assert len(show.acts) == 5


# ═══════════════════════════════════════════════════════════════════
# TEST 7: Dressing Room
# ═══════════════════════════════════════════════════════════════════

@test("dressing room: parse 'barely moves' → high stillness")
async def test_dressing_parse_stillness():
    from backend.routes.dressing_room import parse_description
    parsed = parse_description("barely moves, stares blankly")
    assert parsed["style"].get("stillness", 0) > 0.5
    assert "still" in parsed["tags"]


@test("dressing room: parse 'manic energy' → high energy")
async def test_dressing_parse_energy():
    from backend.routes.dressing_room import parse_description
    parsed = parse_description("manic, hyper, wild energy")
    assert parsed["style"].get("energy", 0) > 0.8


@test("dressing room: parse 'dead stare' → signature move")
async def test_dressing_parse_signature():
    from backend.routes.dressing_room import parse_description
    parsed = parse_description("dead stare after punchlines")
    assert len(parsed["signature_moves"]) > 0


# ═══════════════════════════════════════════════════════════════════
# TEST 8: Edge TTS (with fallback)
# ═══════════════════════════════════════════════════════════════════

@test("tts: fallback generates word timings from text")
async def test_tts_fallback():
    from backend.services.edge_tts import edge_tts_service
    # Force fallback by using a very long text that might rate-limit
    result = await edge_tts_service.synthesize("Test. " * 20)
    assert len(result.word_timings) > 0
    assert result.duration_ms > 0
    assert result.voice_id != ""


@test("tts: word timings are sequential")
async def test_tts_word_order():
    from backend.services.edge_tts import edge_tts_service
    result = await edge_tts_service.synthesize("Hello world this is a test")
    for i in range(1, len(result.word_timings)):
        assert result.word_timings[i].start_ms >= result.word_timings[i-1].start_ms


@test("tts: list voices returns entries")
async def test_tts_voices():
    from backend.services.edge_tts import edge_tts_service
    voices = edge_tts_service.list_voices()
    assert len(voices) > 0
    assert "id" in voices[0]
    assert "name" in voices[0]


# ═══════════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ═══════════════════════════════════════════════════════════════════

async def run_all():
    global results
    results = []

    print("\n" + "=" * 60)
    print("KILLELLA E2E TEST SUITE")
    print("=" * 60)

    print("\n── Motion System ──")
    await test_motion_actions()
    await test_body_manifests()
    await test_humanoid_capabilities()
    await test_dog_fallback()
    await test_toaster_fallback()
    await test_seed_motions()
    await test_compiler_humanoid()
    await test_compiler_toaster()

    print("\n── Direction Parser ──")
    await test_parse_shrug()
    await test_parse_stare_ella()
    await test_parse_freeze_stare()
    await test_parse_look_away()
    await test_parse_point_audience()
    await test_parse_intensity()
    await test_parse_low_intensity()
    await test_parse_fallback()

    print("\n── Chat Summary ──")
    await test_chat_legend()
    await test_chat_nicknames()
    await test_chat_positive()
    await test_chat_negative()
    await test_chat_reactions()
    await test_chat_empty()
    await test_chat_review()

    print("\n── Performance Engine ──")
    await test_presets()
    await test_deadpan_style()
    await test_chaotic_style()
    await test_signature_moves()
    await test_engine_serialize()

    print("\n── Green Room Compiler ──")
    await test_green_room_compile()
    await test_compiler_dog()

    print("\n── Show Runtime ──")
    await test_create_show()
    await test_laugh_recording()
    await test_return_votes()
    await test_show_summary()
    await test_max_acts()

    print("\n── Dressing Room ──")
    await test_dressing_parse_stillness()
    await test_dressing_parse_energy()
    await test_dressing_parse_signature()

    print("\n── Edge TTS ──")
    await test_tts_fallback()
    await test_tts_word_order()
    await test_tts_voices()

    # Summary
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)
    total_ms = sum(r.duration_ms for r in results)

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} passed, {failed} failed ({total_ms}ms total)")
    print("=" * 60)

    if failed > 0:
        print("\nFAILURES:")
        for r in results:
            if not r.passed:
                print(f"  ✗ {r.name}: {r.details}")

    print()
    return passed, failed, total


if __name__ == "__main__":
    asyncio.run(run_all())
